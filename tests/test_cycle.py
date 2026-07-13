from datetime import date

import pytest

from powher.cycle import (
    amenorrhea_flag,
    cycle_day,
    days_since_last_period,
    phase_for_date,
    phase_for_day,
)
from powher.models import Phase


def test_cycle_day_first_day_is_one():
    start = date(2026, 6, 1)
    assert cycle_day(start, 28, start) == 1


def test_cycle_day_wraps_around_cycle_length():
    start = date(2026, 6, 1)
    assert cycle_day(start, 28, date(2026, 6, 29)) == 1  # 28 days later wraps to day 1


def test_cycle_day_rejects_date_before_start():
    with pytest.raises(ValueError):
        cycle_day(date(2026, 6, 10), 28, date(2026, 6, 1))


@pytest.mark.parametrize(
    "day,expected",
    [
        (1, Phase.MENSTRUAL),
        (5, Phase.MENSTRUAL),
        (6, Phase.FOLLICULAR),
        (12, Phase.FOLLICULAR),
        (13, Phase.OVULATORY),
        (14, Phase.OVULATORY),
        (15, Phase.OVULATORY),
        (16, Phase.LUTEAL),
        (28, Phase.LUTEAL),
    ],
)
def test_phase_for_day_28_day_cycle(day, expected):
    assert phase_for_day(day, 28) == expected


def test_phase_for_date_matches_phase_for_day():
    start = date(2026, 6, 1)
    on_date = date(2026, 6, 20)  # cycle day 20
    assert phase_for_date(start, 28, on_date) == phase_for_day(20, 28)


def test_days_since_last_period():
    start = date(2026, 1, 1)
    assert days_since_last_period(start, date(2026, 4, 1)) == 90


def test_amenorrhea_flag_fires_at_90_days():
    start = date(2026, 1, 1)
    assert amenorrhea_flag(start, date(2026, 4, 1)) is True


def test_amenorrhea_flag_does_not_fire_at_89_days():
    start = date(2026, 1, 1)
    assert amenorrhea_flag(start, date(2026, 3, 31)) is False


def test_amenorrhea_flag_none_when_no_period_logged():
    assert amenorrhea_flag(None) is False
