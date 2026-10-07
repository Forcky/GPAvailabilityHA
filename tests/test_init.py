"""Coordinator, entities and notifications inside a real Home Assistant."""
from __future__ import annotations

from datetime import timedelta

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from homeassistant.core import HomeAssistant

from custom_components.gp_availability.const import (
    ANY_DOCTOR,
    CONF_APPT_TYPE_ID,
    CONF_APPT_TYPE_NAME,
    CONF_BOOKING_URL,
    CONF_NOTIFY_TARGETS,
    CONF_PRACTICE_ID,
    CONF_PRACTICE_NAME,
    CONF_PROVIDER,
    CONF_SCAN_INTERVAL,
    CONF_TIMEZONE,
    CONF_WATCHES,
    DOMAIN,
    EVENT_SLOT_AVAILABLE,
)

MORGAN = "sensor.alex_morgan"
ANY = "example_medical_centre"


def _add_slot(resources: list[dict], resource_id: int, when: str) -> None:
    doctor = next(r for r in resources if r["resourceId"] == resource_id)
    doctor["availableSlotDates"].insert(
        0,
        {
            "date": f"{when[:10]}T00:00:00",
            "slots": [{"resourceId": resource_id, "dateTime": when}],
            "timeZoneId": "Tasmania Standard Time",
        },
    )


def _remove_first_day(resources: list[dict], resource_id: int) -> None:
    doctor = next(r for r in resources if r["resourceId"] == resource_id)
    doctor["availableSlotDates"].pop(0)


@pytest.fixture
async def setup(hass: HomeAssistant, mock_api, freezer):
    await hass.config.async_set_time_zone("Australia/Hobart")
    freezer.move_to("2026-09-27T00:00:00+00:00")  # 10:00 in Hobart
    notify = async_mock_service(hass, "notify", "test_phone")
    events = async_capture_events(hass, EVENT_SLOT_AVAILABLE)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Example Medical Centre · Standard appt.",
        unique_id="easyvisit_123_456",
        data={
            CONF_PROVIDER: "easyvisit",
            CONF_PRACTICE_ID: "123",
            CONF_PRACTICE_NAME: "Example Medical Centre",
            CONF_TIMEZONE: None,
            CONF_BOOKING_URL: "https://web.easyvisit.com.au/booking/123/456",
            CONF_APPT_TYPE_ID: "456",
            CONF_APPT_TYPE_NAME: "Standard appt.",
        },
        options={
            CONF_WATCHES: {"2001": "Alex Morgan", ANY_DOCTOR: "Any doctor"},
            CONF_NOTIFY_TARGETS: ["notify.test_phone"],
            CONF_SCAN_INTERVAL: 5,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, notify, events, mock_api


async def _poll(hass: HomeAssistant, freezer) -> None:
    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_entities_reflect_availability(hass: HomeAssistant, setup):
    next_available = hass.states.get(f"{MORGAN}_next_available")
    assert next_available.state == "2026-10-26T02:45:00+00:00"  # 13:45 AEDT
    assert next_available.attributes["open_slots"] == 78
    assert next_available.attributes["manual_confirm"] is True
    assert hass.states.get(f"{MORGAN}_slots_before_cutoff").state == "0"
    assert hass.states.get("binary_sensor.alex_morgan_slot_before_cutoff").state == "off"
    assert hass.states.get("switch.alex_morgan_notifications").state == "on"
    assert hass.states.get("number.alex_morgan_cutoff").state == "14"

    # Any doctor defaults to 2 days (to 29 Sep); Dr Lee's first slot is 5 Oct.
    assert hass.states.get(f"number.any_doctor_at_{ANY}_cutoff").state == "2"
    assert hass.states.get(f"sensor.any_doctor_at_{ANY}_slots_before_cutoff").state == "0"
    assert hass.states.get(f"binary_sensor.any_doctor_at_{ANY}_slot_before_cutoff").state == "off"
    assert hass.states.get(f"sensor.any_doctor_at_{ANY}_next_available").attributes["open_slots"] == 83
    assert hass.states.get(f"switch.any_doctor_at_{ANY}_notifications").state == "off"
    assert hass.states.get(f"sensor.{ANY}_last_checked") is not None


async def test_first_poll_is_silent(hass: HomeAssistant, setup):
    _, notify, events, _ = setup
    assert notify == [] and events == []


async def test_new_slot_notifies_once_and_again_after_reopening(
    hass: HomeAssistant, setup, freezer
):
    _, notify, events, resources = setup
    _add_slot(resources, 2001, "2026-09-29T09:00:00")
    await _poll(hass, freezer)

    # Morgan notifies. Any doctor sees it too but is muted: event only.
    assert len(notify) == 1
    call = notify[0].data
    assert call["title"] == "Alex Morgan: 1 new slot by Sun 11 Oct"
    assert call["message"] == "Tue 29 Sep 09:00"
    assert call["data"]["clickAction"] == "https://web.easyvisit.com.au/booking/123/456"
    assert call["data"]["priority"] == "high"
    assert call["data"]["ttl"] == 0
    assert call["data"]["push"] == {"interruption-level": "time-sensitive"}
    assert "actions" not in call["data"]  # EasyVisit has no per-slot booking links
    assert {e.data["watch_id"] for e in events} == {"2001", ANY_DOCTOR}
    assert hass.states.get(f"{MORGAN}_slots_before_cutoff").state == "1"

    await _poll(hass, freezer)
    assert len(notify) == 1  # nothing new

    _remove_first_day(resources, 2001)  # someone booked it
    await _poll(hass, freezer)
    assert len(notify) == 1
    assert hass.states.get(f"{MORGAN}_slots_before_cutoff").state == "0"

    _add_slot(resources, 2001, "2026-09-29T09:00:00")  # cancelled again
    await _poll(hass, freezer)
    assert len(notify) == 2


async def test_switch_mutes_but_event_still_fires(hass: HomeAssistant, setup, freezer):
    _, notify, events, resources = setup
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.alex_morgan_notifications"}, blocking=True
    )
    _add_slot(resources, 2001, "2026-10-01T09:00:00")
    await _poll(hass, freezer)
    assert notify == []
    assert any(e.data["watch_id"] == "2001" for e in events)


async def test_raising_cutoff_announces_slots_now_inside(hass: HomeAssistant, setup, freezer):
    _, notify, _, _ = setup
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.alex_morgan_cutoff", "value": 29},
        blocking=True,
    )
    await _poll(hass, freezer)
    assert len(notify) == 1
    assert notify[0].data["message"] == "Mon 26 Oct 13:45"


async def test_test_button_sends_current_slots(hass: HomeAssistant, setup):
    _, notify, _, _ = setup
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": f"number.any_doctor_at_{ANY}_cutoff", "value": 14},
        blocking=True,
    )
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": f"button.any_doctor_at_{ANY}_send_test_notification"},
        blocking=True,
    )
    assert len(notify) == 1
    assert notify[0].data["title"].startswith("[Test] Any doctor: 3 new slots")
    assert notify[0].data["message"].splitlines()[0] == "Sam Lee Mon 5 Oct 08:00"


async def test_settings_survive_reload(hass: HomeAssistant, setup):
    entry, _, _, _ = setup
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.alex_morgan_cutoff", "value": 21},
        blocking=True,
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.alex_morgan_preferred_days", "option": "wednesday"},
        blocking=True,
    )
    await hass.services.async_call(
        "time",
        "set_value",
        {"entity_id": "time.alex_morgan_preferred_earliest_time", "time": "09:30"},
        blocking=True,
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("select.alex_morgan_preferred_days").state == "wednesday"
    assert hass.states.get("time.alex_morgan_preferred_earliest_time").state == "09:30:00"
    assert hass.states.get("number.alex_morgan_cutoff").state == "21"


async def test_options_flow_removes_unwatched_doctor(hass: HomeAssistant, setup):
    from homeassistant.helpers import device_registry as dr

    entry, _, _, _ = setup
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_WATCHES: ["2001"], CONF_NOTIFY_TARGETS: ["notify.test_phone"], CONF_SCAN_INTERVAL: 10},
    )
    await hass.async_block_till_done()
    assert entry.options[CONF_WATCHES] == {"2001": "Alex Morgan"}
    assert entry.runtime_data.update_interval == timedelta(minutes=10)

    names = {d.name for d in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)}
    assert names == {"Example Medical Centre", "Alex Morgan"}
    assert hass.states.get(f"{MORGAN}_next_available") is not None


async def test_non_notify_target_is_never_called(hass: HomeAssistant, setup):
    """Even if options were edited by hand, only notify.* services are called."""
    from pytest_homeassistant_custom_component.common import async_mock_service

    entry, notify, _, _ = setup
    stop = async_mock_service(hass, "homeassistant", "restart")
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_NOTIFY_TARGETS: ["homeassistant.restart"]}
    )
    await hass.async_block_till_done()
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.alex_morgan_send_test_notification"},
        blocking=True,
    )
    assert stop == []


# ---- HotDoc ---------------------------------------------------------------

CASEY = "sensor.dr_casey_nguyen"
CASEY_URL = (
    "https://www.hotdoc.com.au/medical-centres/kingston-TAS-7050/"
    "example-medical-centre/doctors/dr-casey-nguyen"
)


@pytest.fixture
async def hotdoc(hass: HomeAssistant, mock_hotdoc, freezer):
    await hass.config.async_set_time_zone("Australia/Hobart")
    freezer.move_to("2026-09-28T14:00:00+00:00")  # 00:00 on 29 Sep in Hobart
    notify = async_mock_service(hass, "notify", "test_phone")
    events = async_capture_events(hass, EVENT_SLOT_AVAILABLE)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Example Medical Centre · Standard Appointment ( 1 issue ) (existing patients)",
        unique_id="hotdoc_999_501:existing",
        data={
            CONF_PROVIDER: "hotdoc",
            CONF_PRACTICE_ID: "999",
            CONF_PRACTICE_NAME: "Example Medical Centre",
            CONF_TIMEZONE: "Australia/Hobart",
            CONF_BOOKING_URL: "https://www.hotdoc.com.au/medical-centres/kingston-TAS-7050/example-medical-centre/doctors",
            CONF_APPT_TYPE_ID: "501:existing",
            CONF_APPT_TYPE_NAME: "Standard Appointment ( 1 issue ) (existing patients)",
        },
        options={
            CONF_WATCHES: {"3001": "Dr Casey Nguyen", "3003": "Dr Taylor Brooks"},
            CONF_NOTIFY_TARGETS: ["notify.test_phone"],
            CONF_SCAN_INTERVAL: 10,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, notify, events, mock_hotdoc


async def test_hotdoc_entities_and_requests(hass: HomeAssistant, hotdoc):
    _, notify, _, fake = hotdoc
    # 14-day cutoff = to the end of 13 Oct: three 7-day windows, only the
    # watched doctors' availability types (not Dr Walsh's 41002).
    assert len(fake.calls) == 3
    assert {a for a, _ in fake.calls[0][2]} == {"41001", "41003"}
    assert fake.calls[1][0] == fake.calls[0][1]  # windows are contiguous

    casey = hass.states.get(f"{CASEY}_next_available")
    assert casey.state == "2026-09-30T01:45:00+00:00"  # 11:45 AEST
    assert casey.attributes["booking_url"] == CASEY_URL
    assert casey.attributes["notes"] == "Special interest in women's health."
    assert "manual_confirm" not in casey.attributes
    assert hass.states.get(f"{CASEY}_slots_before_cutoff").state == "7"
    # Nothing fetched for Dr Brooks, but HotDoc says when the next one is.
    brooks = hass.states.get("sensor.dr_taylor_brooks_next_available")
    assert brooks.state == "2026-10-12T22:30:00+00:00"  # 09:30 AEDT on 13 Oct
    assert hass.states.get("binary_sensor.dr_taylor_brooks_slot_before_cutoff").state == "off"
    assert notify == []


async def test_hotdoc_new_slot_notifies(hass: HomeAssistant, hotdoc, freezer):
    _, notify, events, fake = hotdoc
    fake.add_slot("41003", "2026-10-06T09:00:00+11:00")  # Dr Brooks, a cancellation
    freezer.tick(timedelta(minutes=10, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(notify) == 1
    call = notify[0].data
    assert call["title"] == "Dr Taylor Brooks: 1 new slot by Tue 13 Oct"
    assert call["message"] == "Tue 6 Oct 09:00"
    assert call["data"]["clickAction"].endswith("/doctors/dr-taylor-brooks")
    assert [e.data["provider"] for e in events] == ["hotdoc"]
    assert events[0].data["watch_id"] == "3003"
    assert events[0].data["new_slots"][0]["start"] == "2026-10-06T09:00:00+11:00"


# ---- preferred window -------------------------------------------------------


async def _set(hass: HomeAssistant, domain: str, service: str, entity_id: str, **data) -> None:
    await hass.services.async_call(domain, service, {"entity_id": entity_id, **data}, blocking=True)
    await hass.async_block_till_done()


async def test_window_entities_default_to_anything(hass: HomeAssistant, setup):
    assert hass.states.get("select.alex_morgan_preferred_days").state == "any"
    assert hass.states.get("time.alex_morgan_preferred_earliest_time").state == "00:00:00"
    assert hass.states.get("time.alex_morgan_preferred_latest_time").state == "23:59:00"
    assert hass.states.get("date.alex_morgan_preferred_from_date").state == "unknown"
    assert hass.states.get("date.alex_morgan_preferred_until_date").state == "unknown"
    assert hass.states.get("button.alex_morgan_reset_preferred_window") is not None
    attrs = hass.states.get(f"{MORGAN}_slots_before_cutoff").attributes
    assert attrs["window"] == "Any time"
    assert attrs["cutoff"] == "2026-10-11"


async def test_preferred_day_filters_alerts(hass: HomeAssistant, setup, freezer):
    _, notify, _, resources = setup
    await _set(hass, "select", "select_option", "select.alex_morgan_preferred_days", option="wednesday")
    _add_slot(resources, 2001, "2026-09-29T09:00:00")  # a Tuesday
    await _poll(hass, freezer)
    assert notify == []
    assert hass.states.get(f"{MORGAN}_slots_before_cutoff").state == "0"
    _add_slot(resources, 2001, "2026-09-30T09:00:00")  # a Wednesday
    await _poll(hass, freezer)
    assert len(notify) == 1
    assert notify[0].data["message"] == "Wed 30 Sep 09:00"
    assert hass.states.get(f"{MORGAN}_slots_before_cutoff").attributes["window"] == "Wednesdays"


async def test_until_date_replaces_cutoff_and_reset_restores_it(
    hass: HomeAssistant, setup, freezer
):
    _, notify, _, _ = setup
    # Dr Morgan's first slot is 26 Oct 13:45, beyond the 14-day cutoff.
    await _set(hass, "date", "set_value", "date.alex_morgan_preferred_until_date", date="2026-10-26")
    assert len(notify) == 1
    assert notify[0].data["title"] == "Alex Morgan: 1 new slot by Mon 26 Oct"
    sensor = hass.states.get(f"{MORGAN}_slots_before_cutoff")
    assert sensor.state == "1"
    assert sensor.attributes["window"] == "until Mon 26 Oct"

    await _set(hass, "button", "press", "button.alex_morgan_reset_preferred_window")
    # The setting shows at once; the recheck waits out the refresh cooldown.
    assert hass.states.get("date.alex_morgan_preferred_until_date").state == "unknown"
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(f"{MORGAN}_slots_before_cutoff").state == "0"
    assert len(notify) == 1


async def test_earliest_time_filters(hass: HomeAssistant, setup, freezer):
    _, notify, _, resources = setup
    await _set(hass, "time", "set_value", "time.alex_morgan_preferred_earliest_time", time="10:00")
    _add_slot(resources, 2001, "2026-09-29T09:00:00")
    await _poll(hass, freezer)
    assert notify == []


# ---- pause checking (issue #7) and Book buttons -------------------------------


async def test_checking_switch_stops_all_requests(hass: HomeAssistant, hotdoc, freezer):
    entry, notify, _, fake = hotdoc
    calls = len(fake.calls)
    switch = "switch.example_medical_centre_checking"
    assert hass.states.get(switch).state == "on"

    await _set(hass, "switch", "turn_off", switch)
    for _ in range(3):
        freezer.tick(timedelta(minutes=10, seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    # Settings can still change while paused, without a check.
    await _set(hass, "number", "set_value", "number.dr_casey_nguyen_cutoff", value=7)
    assert len(fake.calls) == calls

    # Paused survives a reload (and a restart): not even the startup check runs.
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert len(fake.calls) == calls
    assert hass.states.get(switch).state == "off"

    await _set(hass, "switch", "turn_on", switch)
    assert len(fake.calls) > calls  # checked straight away
    assert hass.states.get(f"{CASEY}_next_available").state == "2026-09-30T01:45:00+00:00"


async def test_hotdoc_alert_opens_the_slot(hass: HomeAssistant, hotdoc, freezer):
    _, notify, events, fake = hotdoc
    link = "https://www.hotdoc.com.au/request/consult/start?defaults=practice-x,practitioner-dr-taylor-brooks,when-1"
    fake.add_slot("41003", "2026-10-06T09:00:00+11:00", link)
    fake.add_slot("41003", "2026-10-07T09:00:00+11:00")  # no link: no button
    freezer.tick(timedelta(minutes=10, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    data = notify[0].data["data"]
    assert data["clickAction"] == data["url"] == link
    assert data["actions"] == [{"action": "URI", "title": "Book Tue 6 Oct 09:00", "uri": link}]
    assert events[0].data["new_slots"][0]["booking_url"] == link
