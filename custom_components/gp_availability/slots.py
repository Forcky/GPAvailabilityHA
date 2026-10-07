"""Slot matching, shared by every provider.

Kept free of Home Assistant imports so the logic can be unit-tested with
plain pytest.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Iterable

from .const import ANY_DOCTOR

# Preferred-day presets, as Python weekdays (Monday = 0).
DAY_PRESETS: dict[str, frozenset[int]] = {
    "any": frozenset(range(7)),
    "weekdays": frozenset(range(5)),
    "weekends": frozenset({5, 6}),
    "monday": frozenset({0}),
    "tuesday": frozenset({1}),
    "wednesday": frozenset({2}),
    "thursday": frozenset({3}),
    "friday": frozenset({4}),
    "saturday": frozenset({5}),
    "sunday": frozenset({6}),
}
_DAY_LABELS = {
    "weekdays": "Weekdays",
    "weekends": "Weekends",
    **{d: f"{d.capitalize()}s" for d in DAY_PRESETS if d.endswith("day") and d != "any"},
}


@dataclass(frozen=True, order=True)
class Slot:
    """One bookable appointment time."""

    start: dt.datetime  # timezone-aware, in the practice's zone; first so slots sort by time
    resource_id: str  # the provider's doctor id
    resource_name: str
    # A link that opens booking for exactly this slot, when the site has one.
    url: str | None = field(default=None, compare=False)

    @property
    def key(self) -> str:
        """Stable identity used to remember which slots were already announced."""
        return f"{self.resource_id}|{self.start.replace(tzinfo=None).isoformat()}"

    def as_dict(self) -> dict[str, Any]:
        out = {
            "doctor": self.resource_name,
            "resource_id": self.resource_id,
            "start": self.start.isoformat(),
        }
        if self.url:
            out["booking_url"] = self.url
        return out


@dataclass(frozen=True)
class Window:
    """When a slot is wanted. The default matches everything up to the cutoff."""

    days: str = "any"  # a DAY_PRESETS key
    earliest: dt.time = dt.time(0, 0)
    latest: dt.time = dt.time(23, 59)
    from_date: dt.date | None = None
    until_date: dt.date | None = None  # when set, replaces the cutoff

    def last_day(self, now: dt.datetime, cutoff_days: int, tz: dt.tzinfo) -> dt.date:
        """Last calendar day (inclusive) that counts."""
        if self.until_date is not None:
            return self.until_date
        return cutoff_date(now, cutoff_days, tz)

    def matches(self, slot: Slot, tz: dt.tzinfo) -> bool:
        """Day, time and from-date checks (the last day is applied by qualifying)."""
        local = slot.start.astimezone(tz)
        if local.weekday() not in DAY_PRESETS.get(self.days, DAY_PRESETS["any"]):
            return False
        if self.from_date is not None and local.date() < self.from_date:
            return False
        start = local.time()
        if self.earliest <= self.latest:
            return self.earliest <= start <= self.latest
        return start >= self.earliest or start <= self.latest  # overnight, e.g. 22:00-02:00

    def describe(self, today: dt.date) -> str:
        """Short human form, e.g. 'Wednesdays 09:00-12:00, until Wed 15 Oct'."""
        parts = []
        if self.days in _DAY_LABELS:
            parts.append(_DAY_LABELS[self.days])
        if (self.earliest, self.latest) != (Window.earliest, Window.latest):
            parts.append(f"{self.earliest:%H:%M}–{self.latest:%H:%M}")
        if self.from_date is not None and self.from_date == self.until_date:
            parts.append(f"on {format_date(self.from_date)}")
        else:
            if self.from_date is not None:
                parts.append(f"from {format_date(self.from_date)}")
            if self.until_date is not None:
                parts.append(f"until {format_date(self.until_date)}")
        if self.until_date is not None and self.until_date < today:
            parts[-1] += " (passed)"
        return ", ".join(parts) or "Any time"


def slots_for_watch(slots: Iterable[Slot], watch_id: str) -> list[Slot]:
    """Slots belonging to one doctor, or all of them for ANY_DOCTOR."""
    if watch_id == ANY_DOCTOR:
        return list(slots)
    return [s for s in slots if s.resource_id == watch_id]


def cutoff_date(now: dt.datetime, cutoff_days: int, tz: dt.tzinfo) -> dt.date:
    """Last calendar day (inclusive) that counts as 'soon enough'."""
    return now.astimezone(tz).date() + dt.timedelta(days=cutoff_days)


def qualifying(
    slots: Iterable[Slot],
    now: dt.datetime,
    cutoff_days: int,
    tz: dt.tzinfo,
    window: Window | None = None,
) -> list[Slot]:
    """Future slots on or before the last day that fall inside the window."""
    window = window or Window()
    last_day = window.last_day(now, cutoff_days, tz)
    return [
        s
        for s in slots
        if s.start > now and s.start.astimezone(tz).date() <= last_day and window.matches(s, tz)
    ]


def diff_seen(
    current: Iterable[Slot], seen: set[str]
) -> tuple[list[Slot], set[str]]:
    """Return (slots not announced before, the new seen set).

    The new seen set is exactly the current qualifying keys, so a slot that
    disappears (someone booked it) and later reopens is announced again.
    """
    current = list(current)
    new = [s for s in current if s.key not in seen]
    return new, {s.key for s in current}


def format_slot(slot: Slot, tz: dt.tzinfo, with_doctor: bool = False) -> str:
    """Short human form, e.g. 'Tue 7 Oct 10:15'."""
    local = slot.start.astimezone(tz)
    text = f"{local:%a} {local.day} {local:%b %H:%M}"
    return f"{slot.resource_name} {text}" if with_doctor else text


def format_date(day: dt.date) -> str:
    return f"{day:%a} {day.day} {day:%b}"
