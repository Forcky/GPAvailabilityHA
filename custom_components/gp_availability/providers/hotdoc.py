"""HotDoc (www.hotdoc.com.au), the most common GP booking site in Australia.

Two public endpoints, no login (see API.md):
- clinics/{slug|id}: doctors, reasons (appointment types) and doctor_reasons,
  which map (doctor, reason, new/existing patient) to an availability type.
- time_slots: open slots for a list of availability types, at most ~7 days
  per call (longer ranges return HTTP 500).
"""
from __future__ import annotations

import datetime as dt
import re
import time
import urllib.parse
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from ..slots import Slot
from .base import (
    USER_AGENT,
    ApptType,
    Availability,
    Doctor,
    ParsedInput,
    Practice,
    Provider,
    ProviderError,
    get_json,
)

SITE = "https://www.hotdoc.com.au"
API_BASE = f"{SITE}/api/patient"
EXAMPLE_URL = f"{SITE}/medical-centres/kingston-TAS-7050/example-medical-centre/doctors"

_HEADERS = {"Accept": "application/au.com.hotdoc.v5", "User-Agent": USER_AGENT}
WINDOW = dt.timedelta(days=7)
# Clinic data (doctors, reasons) changes rarely; slots are what we poll.
CLINIC_TTL = 6 * 3600  # seconds

_CLINIC_RE = re.compile(
    r"hotdoc\.com\.au/medical-centres/[^/?#]+/([a-z0-9-]+)(?:/doctors(?:/([a-z0-9-]+))?)?",
    re.IGNORECASE,
)
# The slot deep links: .../request/consult/start?defaults=practice-x,practitioner-y,...
_DEFAULTS_RE = re.compile(r"practice-([a-z0-9-]+)(?:,practitioner-([a-z0-9-]+))?", re.IGNORECASE)


class HotDocApiClient:
    """Client for HotDoc's patient API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def get_clinic(self, ref: str) -> dict[str, Any]:
        body = await get_json(
            self._session, f"{API_BASE}/clinics/{urllib.parse.quote(ref)}", _HEADERS
        )
        if not isinstance(body, dict) or not isinstance(body.get("clinic"), dict):
            raise ProviderError(f"Clinic {ref} not found")
        return body

    async def get_time_slots(
        self,
        clinic_id: str,
        timezone: str,
        start: dt.datetime,
        end: dt.datetime,
        pairs: list[tuple[str, str]],
    ) -> dict[str, Any]:
        """pairs = [(availability_type_id, doctor_id), ...]"""
        params: list[tuple[str, str]] = [
            ("start_time", _utc(start)),
            ("end_time", _utc(end)),
            ("timezone", timezone),
            ("clinic_id", clinic_id),
        ]
        params += [("availability_type_ids[]", a) for a, _ in pairs]
        params += [("doctor_ids[]", d) for _, d in pairs]
        body = await get_json(
            self._session,
            f"{API_BASE}/time_slots?{urllib.parse.urlencode(params)}",
            _HEADERS,
        )
        if not isinstance(body, dict) or not isinstance(body.get("time_slots"), list):
            raise ProviderError("time_slots: unexpected response")
        return body


def _utc(when: dt.datetime) -> str:
    return f"{when.astimezone(dt.UTC):%Y-%m-%dT%H:%M:%S}.000Z"


def _parse_time(text: str | None, tz: dt.tzinfo) -> dt.datetime | None:
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(tz)
    except ValueError:
        return None


def split_appt_type(appt_type_id: str) -> tuple[int, bool]:
    """'44085:existing' -> (44085, False); '44085:new' -> (44085, True)."""
    reason, _, who = appt_type_id.partition(":")
    return int(reason), who == "new"


def _doctors(clinic: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(d["id"]): d
        for d in clinic.get("doctors") or []
        if d.get("visible_on_hot_doc", True)
    }


def _doctor_reasons(clinic: dict[str, Any]) -> list[dict[str, Any]]:
    visible = _doctors(clinic)
    return [
        dr
        for dr in clinic.get("doctor_reasons") or []
        if not dr.get("deleted_at") and str(dr["doctor_id"]) in visible
    ]


def appointment_types(clinic: dict[str, Any]) -> list[ApptType]:
    """Each reason, once per patient kind (new/existing) that has a doctor."""
    offered = {(dr["reason_id"], bool(dr["is_for_new"])) for dr in _doctor_reasons(clinic)}
    reasons = sorted(
        (r for r in clinic.get("reasons") or [] if not r.get("deleted_at")),
        key=lambda r: (r.get("position") or 0, r["id"]),
    )
    types = []
    for reason in reasons:
        name = " ".join((reason.get("name") or f"Reason {reason['id']}").split())
        for for_new, who in ((False, "existing"), (True, "new")):
            if (reason["id"], for_new) in offered:
                types.append(ApptType(f"{reason['id']}:{who}", f"{name} ({who} patients)"))
    return types


def type_map(clinic: dict[str, Any], appt_type_id: str) -> dict[str, str]:
    """{availability_type_id: doctor_id} for one appointment type.

    Slots are matched to doctors through this map, not the doctor_ids sent:
    time_slots answers by availability type.
    """
    reason_id, for_new = split_appt_type(appt_type_id)
    return {
        str(dr["availability_type_id"]): str(dr["doctor_id"])
        for dr in _doctor_reasons(clinic)
        if dr["reason_id"] == reason_id and bool(dr["is_for_new"]) == for_new
    }


class HotDocProvider(Provider):
    key = "hotdoc"
    name = "HotDoc"
    # Be gentle: an undocumented API, and each check may take several calls.
    default_scan_interval = 10
    min_scan_interval = 5

    def __init__(self, session: aiohttp.ClientSession) -> None:
        super().__init__(session)
        self.client = HotDocApiClient(session)
        self._clinics: dict[str, tuple[float, dict[str, Any]]] = {}

    @staticmethod
    def parse_input(text: str) -> ParsedInput | None:
        """Accept a HotDoc clinic or doctor page link, or a booking link."""
        text = text.strip()
        if "hotdoc.com.au" not in text.lower():
            return None
        if match := _CLINIC_RE.search(text):
            return ParsedInput(practice=match.group(1).lower(), doctor=_lower(match.group(2)))
        if match := _DEFAULTS_RE.search(urllib.parse.unquote(text)):
            return ParsedInput(practice=match.group(1).lower(), doctor=_lower(match.group(2)))
        return None

    async def _clinic(self, ref: str, fresh: bool = False) -> dict[str, Any]:
        cached = self._clinics.get(ref)
        if cached and not fresh and time.monotonic() - cached[0] < CLINIC_TTL:
            return cached[1]
        clinic = await self.client.get_clinic(ref)
        self._clinics[ref] = self._clinics[str(clinic["clinic"]["id"])] = (
            time.monotonic(),
            clinic,
        )
        return clinic

    async def get_practice(self, ref: str) -> Practice:
        clinic = await self._clinic(ref, fresh=True)
        info = clinic["clinic"]
        return Practice(
            id=str(info["id"]),
            name=(info.get("name") or info.get("slug") or ref).strip(),
            timezone=info.get("timezone") or "Australia/Sydney",
            booking_url=SITE + (info.get("listing_path") or ""),
        )

    async def get_appointment_types(self, practice_id: str) -> list[ApptType]:
        return appointment_types(await self._clinic(practice_id))

    async def get_doctors(self, practice_id: str, appt_type_id: str) -> list[Doctor]:
        # One 7-day call also gives each doctor's next_available for the labels.
        clinic = await self._clinic(practice_id)
        tz = ZoneInfo(clinic["clinic"].get("timezone") or "Australia/Sydney")
        today = dt.datetime.now(tz).date()
        found = await self.fetch(practice_id, appt_type_id, None, today, tz)
        return sorted(found.doctors.values(), key=lambda d: d.name)

    async def fetch(
        self,
        practice_id: str,
        appt_type_id: str,
        doctor_ids: set[str] | None,
        until: dt.date,
        default_tz: dt.tzinfo,
    ) -> Availability:
        clinic = await self._clinic(practice_id)
        tzname = clinic["clinic"].get("timezone") or "Australia/Sydney"
        tz = ZoneInfo(tzname)
        people = _doctors(clinic)
        types = type_map(clinic, appt_type_id)

        result = Availability()
        for did in dict.fromkeys(types.values()):
            info = people[did]
            result.doctors[did] = Doctor(
                id=did,
                name=(info.get("full_name") or f"Doctor {did}").strip(),
                notes=(info.get("statement") or "").strip(),
                slug=info.get("slug"),
                url=SITE + info["listing_path"] if info.get("listing_path") else None,
            )
        pairs = [
            (atid, did) for atid, did in types.items() if doctor_ids is None or did in doctor_ids
        ]
        if not pairs:
            return result

        start = dt.datetime.now(dt.UTC).replace(second=0, microsecond=0)
        end = dt.datetime.combine(until + dt.timedelta(days=1), dt.time(), tz)
        found: dict[str, Slot] = {}
        first = True
        while first or start < end:
            window_end = start + WINDOW
            body = await self.client.get_time_slots(
                str(clinic["clinic"]["id"]), tzname, start, window_end, pairs
            )
            for raw in body["time_slots"]:
                did = types.get(str(raw.get("availability_type_id")))
                when = _parse_time(raw.get("start_time"), tz)
                if did is None or when is None or (doctor_ids is not None and did not in doctor_ids):
                    continue
                slot = Slot(when, did, result.doctors[did].name, url=raw.get("link") or None)
                found[slot.key] = slot
            if first:
                # Only doctors with nothing in the window get next_available.
                for item in body.get("doctors") or []:
                    doctor = result.doctors.get(str(item.get("id")))
                    if doctor is not None:
                        doctor.next_available = _parse_time(item.get("next_available"), tz)
                first = False
            start = window_end

        result.slots = sorted(found.values())
        for slot in result.slots:
            doctor = result.doctors[slot.resource_id]
            if doctor.next_available is None or slot.start < doctor.next_available:
                doctor.next_available = slot.start
        return result


def _lower(text: str | None) -> str | None:
    return text.lower() if text else None
