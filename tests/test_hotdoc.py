"""HotDoc provider against a mocked HTTP layer."""
from __future__ import annotations

import datetime as dt
import re
from itertools import pairwise
from zoneinfo import ZoneInfo

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.gp_availability.providers import ProviderError
from custom_components.gp_availability.providers.hotdoc import (
    HotDocProvider,
    appointment_types,
    type_map,
)

from .conftest import load

API = "https://www.hotdoc.com.au/api/patient"
SLOTS_RE = re.compile(r"^https://www\.hotdoc\.com\.au/api/patient/time_slots\?")
HOBART = ZoneInfo("Australia/Hobart")
UTC = dt.UTC


@pytest.fixture
def api(aioclient_mock, freezer):
    freezer.move_to("2026-09-28T14:00:00+00:00")  # 00:00 on 29 Sep in Hobart
    aioclient_mock.get(f"{API}/clinics/999", json=load("hotdoc_clinic.json"))
    aioclient_mock.get(SLOTS_RE, json=load("hotdoc_time_slots.json"))
    return aioclient_mock


def _slot_calls(api) -> list:
    return [url for _, url, _, _ in api.mock_calls if url.path.endswith("/time_slots")]


def test_appointment_types_and_type_map():
    clinic = load("hotdoc_clinic.json")
    assert [t.id for t in appointment_types(clinic)] == [
        "501:existing",
        "501:new",
        "502:existing",
        "503:existing",
    ]
    assert type_map(clinic, "501:existing") == {"41001": "3001", "41002": "3002", "41003": "3003"}
    # Dr Walsh's new-patient entry is deleted, so only Dr Nguyen remains.
    assert type_map(clinic, "501:new") == {"41008": "3001"}
    clinic["doctors"][0]["visible_on_hot_doc"] = False
    assert "41001" not in type_map(clinic, "501:existing")


async def test_request_shape(hass: HomeAssistant, api):
    provider = HotDocProvider(async_get_clientsession(hass))
    await provider.fetch("999", "501:existing", {"3001", "3003"}, dt.date(2026, 9, 29), HOBART)
    (url,) = _slot_calls(api)
    assert url.query["clinic_id"] == "999"
    assert url.query["timezone"] == "Australia/Hobart"
    assert url.query["start_time"] == "2026-09-28T14:00:00.000Z"
    assert url.query["end_time"] == "2026-10-05T14:00:00.000Z"
    assert url.query.getall("availability_type_ids[]") == ["41001", "41003"]
    assert url.query.getall("doctor_ids[]") == ["3001", "3003"]
    headers = api.mock_calls[-1][3]
    assert headers["Accept"] == "application/au.com.hotdoc.v5"


@pytest.mark.parametrize(
    ("until", "calls"),
    [
        (dt.date(2026, 9, 29), 1),  # today only
        (dt.date(2026, 10, 5), 1),  # exactly one week
        (dt.date(2026, 10, 12), 2),  # default 14-day cutoff
        (dt.date(2026, 11, 27), 9),  # the 60-day maximum
    ],
)
async def test_windows_cover_the_cutoff(hass: HomeAssistant, api, until, calls):
    provider = HotDocProvider(async_get_clientsession(hass))
    await provider.fetch("999", "501:existing", None, until, HOBART)
    urls = _slot_calls(api)
    assert len(urls) == calls
    # Contiguous 7-day windows; the clinic itself is fetched once.
    for prev, nxt in pairwise(urls):
        assert prev.query["end_time"] == nxt.query["start_time"]
    assert sum(1 for _, u, _, _ in api.mock_calls if u.path.endswith("/clinics/999")) == 1


async def test_slots_map_by_availability_type(hass: HomeAssistant, api):
    provider = HotDocProvider(async_get_clientsession(hass))
    # The recorded response also holds Dr Walsh's slots (41002); HotDoc answers
    # by availability type, so they must not be credited to anyone else.
    found = await provider.fetch("999", "501:existing", {"3001"}, dt.date(2026, 10, 12), HOBART)
    assert {s.resource_id for s in found.slots} == {"3001"}
    assert len(found.slots) == 7  # the same slots from both windows, once each
    first = found.slots[0]
    assert first.start == dt.datetime(2026, 9, 30, 11, 45, tzinfo=HOBART)
    assert first.resource_name == "Dr Casey Nguyen"
    assert first.url == (
        "https://www.hotdoc.com.au/request/consult/start"
        "?defaults=practice-example-medical-centre,practitioner-dr-casey-nguyen"
    )
    assert found.doctors["3001"].next_available == first.start
    assert found.doctors["3001"].url.endswith("/doctors/dr-casey-nguyen")


async def test_all_doctors_and_dst(hass: HomeAssistant, api):
    provider = HotDocProvider(async_get_clientsession(hass))
    found = await provider.fetch("999", "501:existing", None, dt.date(2026, 10, 5), HOBART)
    assert {s.resource_id for s in found.slots} == {"3001", "3002"}
    last = found.slots[-1]
    # 13:15 on 5 Oct is AEDT (+11) after the 4 Oct change.
    assert last.start.utcoffset() == dt.timedelta(hours=11)
    assert last.key.endswith("|2026-10-05T13:15:00")
    # Nothing in the window for Dr Brooks, but HotDoc reports the next time.
    assert found.doctors["3003"].next_available == dt.datetime(2026, 10, 13, 9, 30, tzinfo=HOBART)


async def test_no_matching_doctor_makes_no_slot_call(hass: HomeAssistant, api):
    provider = HotDocProvider(async_get_clientsession(hass))
    found = await provider.fetch("999", "501:new", {"3002"}, dt.date(2026, 10, 5), HOBART)
    assert found.slots == []
    assert _slot_calls(api) == []


async def test_http_500_raises(hass: HomeAssistant, aioclient_mock, freezer):
    freezer.move_to("2026-09-28T14:00:00+00:00")
    aioclient_mock.get(f"{API}/clinics/999", json=load("hotdoc_clinic.json"))
    aioclient_mock.get(SLOTS_RE, status=500, text="<html>We're sorry</html>")
    provider = HotDocProvider(async_get_clientsession(hass))
    with pytest.raises(ProviderError, match="500"):
        await provider.fetch("999", "501:existing", None, dt.date(2026, 10, 5), HOBART)


async def test_unknown_clinic_raises(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(f"{API}/clinics/nope", status=404, json={"error": "not found"})
    provider = HotDocProvider(async_get_clientsession(hass))
    with pytest.raises(ProviderError):
        await provider.get_practice("nope")


async def test_practice_lookup(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(f"{API}/clinics/example-medical-centre", json=load("hotdoc_clinic.json"))
    provider = HotDocProvider(async_get_clientsession(hass))
    practice = await provider.get_practice("example-medical-centre")
    assert practice.id == "999"
    assert practice.name == "Example Medical Centre"
    assert practice.timezone == "Australia/Hobart"
    assert practice.booking_url == (
        "https://www.hotdoc.com.au/medical-centres/kingston-TAS-7050/example-medical-centre/doctors"
    )
    # Cached under its numeric id too, so polling doesn't refetch it.
    assert (await provider.get_appointment_types("999"))[0].id == "501:existing"
    assert len(aioclient_mock.mock_calls) == 1
