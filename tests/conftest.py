"""Shared fixtures."""
from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path
from unittest.mock import patch

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

LOCATION = {"locationID": 123, "name": "Example Medical Centre"}
APPT_TYPES = [
    {"apptTypeID": 456, "name": "Standard appt."},
    {"apptTypeID": 457, "name": "Long appt."},
]


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def resources() -> list[dict]:
    """Mutable copy of the recorded EasyVisit resources; edit it between polls."""
    return copy.deepcopy(load("resources_sample.json")["Data"])


@pytest.fixture
def mock_api(resources):
    """Patch the EasyVisit client so nothing reaches the network."""

    async def get_resources(self, location_id, appt_type_id):
        return copy.deepcopy(resources)

    async def get_location(self, location_id):
        return dict(LOCATION)

    async def get_appointment_types(self, location_id):
        return list(APPT_TYPES)

    base = "custom_components.gp_availability.providers.easyvisit.EasyVisitApiClient"
    with (
        patch(f"{base}.get_resources", get_resources),
        patch(f"{base}.get_location", get_location),
        patch(f"{base}.get_appointment_types", get_appointment_types),
    ):
        yield resources


@pytest.fixture
def hotdoc_clinic() -> dict:
    """Anonymised clinic response: 3 doctors, Standard/Long/Telehealth reasons."""
    return copy.deepcopy(load("hotdoc_clinic.json"))


@pytest.fixture
def hotdoc_slots() -> dict:
    """Anonymised time_slots response, 29 Sep - 5 Oct 2026 (crosses DST on 4 Oct)."""
    return copy.deepcopy(load("hotdoc_time_slots.json"))


class FakeHotDoc:
    """Answers like HotDoc: only slots of the asked types, inside the window."""

    def __init__(self, clinic: dict, slots: dict) -> None:
        self.clinic = clinic
        self.slots = slots
        self.calls: list[tuple[dt.datetime, dt.datetime, list[tuple[str, str]]]] = []

    async def get_clinic(self, ref):
        return copy.deepcopy(self.clinic)

    async def get_time_slots(self, clinic_id, timezone, start, end, pairs):
        self.calls.append((start, end, list(pairs)))
        types = {a for a, _ in pairs}
        body = copy.deepcopy(self.slots)
        body["time_slots"] = [
            t
            for t in body["time_slots"]
            if t["availability_type_id"] in types
            and start <= dt.datetime.fromisoformat(t["start_time"]) < end
        ]
        return body

    def add_slot(self, availability_type_id: str, start: str, link: str | None = None) -> None:
        self.slots["time_slots"].append(
            {"start_time": start, "availability_type_id": availability_type_id, "link": link}
        )


@pytest.fixture
def mock_hotdoc(hotdoc_clinic, hotdoc_slots):
    fake = FakeHotDoc(hotdoc_clinic, hotdoc_slots)
    base = "custom_components.gp_availability.providers.hotdoc.HotDocApiClient"
    with (
        patch(f"{base}.get_clinic", lambda self, ref: fake.get_clinic(ref)),
        patch(
            f"{base}.get_time_slots",
            lambda self, *args: fake.get_time_slots(*args),
        ),
    ):
        yield fake
