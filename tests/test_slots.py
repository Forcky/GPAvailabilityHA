"""Provider-neutral slot matching (no Home Assistant runtime needed)."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from custom_components.gp_availability.const import ANY_DOCTOR
from custom_components.gp_availability.slots import (
    Window,
    Slot,
    diff_seen,
    format_slot,
    qualifying,
    slots_for_watch,
)

HOBART = ZoneInfo("Australia/Hobart")
# Saturday 27 Sep 2026, 10:00 in Hobart (AEST, before DST starts on 4 Oct).
NOW = dt.datetime(2026, 9, 27, 10, 0, tzinfo=HOBART)
MORGAN, LEE = "2001", "2002"


def _slot(days: float, who: str = MORGAN) -> Slot:
    return Slot(NOW + dt.timedelta(days=days), who, who)


def test_any_doctor_is_the_union():
    slots = [_slot(1), _slot(2, LEE)]
    assert slots_for_watch(slots, ANY_DOCTOR) == slots
    assert slots_for_watch(slots, LEE) == [slots[1]]
    assert slots_for_watch(slots, "9999") == []


def test_cutoff_is_inclusive_calendar_days():
    late_on_last_day = Slot(dt.datetime(2026, 10, 11, 23, 30, tzinfo=HOBART), MORGAN, "")
    first_after = Slot(dt.datetime(2026, 10, 12, 0, 0, tzinfo=HOBART), MORGAN, "")
    # 14 days from 27 Sep = 11 Oct, whatever the time of day (and across DST).
    assert qualifying([late_on_last_day, first_after], NOW, 14, HOBART) == [late_on_last_day]
    assert qualifying([late_on_last_day], NOW, 13, HOBART) == []


def test_past_slots_never_qualify():
    past = _slot(-5 / 1440)
    future = _slot(2 / 24)
    assert qualifying([past, future], NOW, 0, HOBART) == [future]


def test_diff_seen_announces_new_and_reopened_slots():
    a, b = _slot(1), _slot(2)
    new, seen = diff_seen([a], set())
    assert new == [a]
    new, seen = diff_seen([a, b], seen)
    assert new == [b]
    new, seen = diff_seen([a, b], seen)
    assert new == []
    # b is booked by someone else, then cancelled again: announce it again.
    new, seen = diff_seen([a], seen)
    assert new == [] and seen == {a.key}
    new, seen = diff_seen([a, b], seen)
    assert new == [b]


def test_key_is_doctor_and_local_time():
    slot = Slot(dt.datetime(2026, 10, 5, 8, 0, tzinfo=HOBART), MORGAN, "Alex Morgan")
    assert slot.key == "2001|2026-10-05T08:00:00"


def test_format_slot():
    slot = Slot(dt.datetime(2026, 10, 7, 10, 15, tzinfo=HOBART), MORGAN, "Alex Morgan")
    assert format_slot(slot, HOBART) == "Wed 7 Oct 10:15"
    assert format_slot(slot, HOBART, with_doctor=True) == "Alex Morgan Wed 7 Oct 10:15"


# ---- preferred window ---------------------------------------------------------

WED_1015 = Slot(dt.datetime(2026, 10, 7, 10, 15, tzinfo=HOBART), MORGAN, "Alex Morgan")


def test_day_presets():
    assert Window(days="wednesday").matches(WED_1015, HOBART)
    assert Window(days="weekdays").matches(WED_1015, HOBART)
    assert not Window(days="weekends").matches(WED_1015, HOBART)
    assert not Window(days="tuesday").matches(WED_1015, HOBART)
    assert Window(days="nonsense").matches(WED_1015, HOBART)  # unknown = any day


def test_time_edges_are_inclusive_and_overnight_wraps():
    t = dt.time
    assert Window(earliest=t(10, 15), latest=t(10, 15)).matches(WED_1015, HOBART)
    assert not Window(earliest=t(10, 16)).matches(WED_1015, HOBART)
    assert not Window(latest=t(10, 14)).matches(WED_1015, HOBART)
    overnight = Window(earliest=t(22, 0), latest=t(2, 0))
    late = Slot(dt.datetime(2026, 10, 7, 23, 0, tzinfo=HOBART), MORGAN, "")
    early = Slot(dt.datetime(2026, 10, 8, 1, 0, tzinfo=HOBART), MORGAN, "")
    assert overnight.matches(late, HOBART) and overnight.matches(early, HOBART)
    assert not overnight.matches(WED_1015, HOBART)


def test_window_uses_local_time_across_dst():
    # 08:00 on Mon 5 Oct is AEDT (+11); a fixed +10 offset would make it 07:00.
    slot = Slot(dt.datetime(2026, 10, 4, 21, 0, tzinfo=dt.UTC), MORGAN, "")
    assert Window(days="monday", earliest=dt.time(8, 0)).matches(slot, HOBART)


def test_from_and_until_dates():
    later = Slot(dt.datetime(2026, 10, 20, 9, 0, tzinfo=HOBART), MORGAN, "")
    assert not Window(from_date=dt.date(2026, 10, 8)).matches(WED_1015, HOBART)
    assert Window(from_date=dt.date(2026, 10, 7)).matches(WED_1015, HOBART)
    # The until date replaces the cutoff: 20 Oct is beyond 14 days from 27 Sep.
    assert qualifying([later], NOW, 14, HOBART) == []
    assert qualifying([later], NOW, 14, HOBART, Window(until_date=dt.date(2026, 10, 20))) == [later]
    assert qualifying([later], NOW, 14, HOBART, Window(until_date=dt.date(2026, 10, 19))) == []
    # "Only next Wednesday": from = until = that day.
    only_wed = Window(from_date=dt.date(2026, 10, 7), until_date=dt.date(2026, 10, 7))
    assert qualifying([WED_1015, later], NOW, 0, HOBART, only_wed) == [WED_1015]


def test_passed_until_date_matches_nothing():
    window = Window(until_date=dt.date(2026, 9, 26))
    assert qualifying([_slot(1)], NOW, 14, HOBART, window) == []
    assert window.describe(NOW.date()) == "until Sat 26 Sep (passed)"


def test_describe():
    today = NOW.date()
    assert Window().describe(today) == "Any time"
    assert (
        Window(
            days="wednesday",
            earliest=dt.time(9, 0),
            latest=dt.time(12, 0),
            until_date=dt.date(2026, 10, 15),
        ).describe(today)
        == "Wednesdays, 09:00–12:00, until Thu 15 Oct"
    )
    assert Window(from_date=dt.date(2026, 10, 7), until_date=dt.date(2026, 10, 7)).describe(
        today
    ) == "on Wed 7 Oct"
    assert Window(days="weekends", from_date=dt.date(2026, 10, 3)).describe(today) == (
        "Weekends, from Sat 3 Oct"
    )


def test_slot_link_is_not_part_of_identity():
    linked = Slot(WED_1015.start, MORGAN, "Alex Morgan", url="https://example.invalid/book")
    assert linked == WED_1015 and linked.key == WED_1015.key
    assert linked.as_dict()["booking_url"] == "https://example.invalid/book"
    assert "booking_url" not in WED_1015.as_dict()
