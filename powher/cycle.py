"""Cycle phase estimation from simple date math.

Phase is derived purely for context, education, and long-term pattern
detection. It must never be used to prescribe a load number -- see
guardrails.py for the hard-coded check that enforces this.
"""

from datetime import date

from powher.models import Phase

ESTIMATE_NOTE = (
    "This is estimated from your dates — bodies aren't calendars, and that's normal."
)


def cycle_day(last_period_start: date, cycle_length: int, on_date: date | None = None) -> int:
    """Return the 1-indexed day of the cycle for on_date (defaults to today)."""
    on_date = on_date or date.today()
    if on_date < last_period_start:
        raise ValueError("on_date is before last_period_start")
    days_elapsed = (on_date - last_period_start).days
    return (days_elapsed % cycle_length) + 1


def phase_for_day(day: int, cycle_length: int) -> Phase:
    """Map a cycle day to a phase, per SPEC.md §5.

    Menstrual: days 1-5
    Follicular: day 6 -> (cycle_length - 14 - 1)
    Ovulatory: the ~3 days around (cycle_length - 14)
    Luteal: from the end of ovulation -> end of cycle
    """
    ovulation_day = cycle_length - 14
    ovulatory_start = ovulation_day - 1
    ovulatory_end = ovulation_day + 1
    follicular_end = ovulatory_start - 1

    if day <= 5:
        return Phase.MENSTRUAL
    if day <= follicular_end:
        return Phase.FOLLICULAR
    if day <= ovulatory_end:
        return Phase.OVULATORY
    return Phase.LUTEAL


def phase_for_date(last_period_start: date, cycle_length: int, on_date: date | None = None) -> Phase:
    day = cycle_day(last_period_start, cycle_length, on_date)
    return phase_for_day(day, cycle_length)


def days_since_last_period(last_period_start: date, on_date: date | None = None) -> int:
    on_date = on_date or date.today()
    return (on_date - last_period_start).days


def amenorrhea_flag(last_period_start: date | None, on_date: date | None = None, threshold_days: int = 90) -> bool:
    """True if no period has been logged for >= threshold_days (RED-S referral trigger)."""
    if last_period_start is None:
        return False
    return days_since_last_period(last_period_start, on_date) >= threshold_days
