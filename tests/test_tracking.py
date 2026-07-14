"""Tests for period events, previous-set lookup, PR detection, and new tags."""

import uuid
from datetime import date

import pytest

from powher import storage
from powher.messages import GENERIC_FALLBACK, get_fallback_message
from powher.models import (
    EnergyTag,
    Exercise,
    PeriodEvent,
    SetType,
    WorkoutEntry,
    WorkoutSet,
)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    storage.init_db(path)
    return path


def _workout(day: date, exercises, tags=None):
    return WorkoutEntry(
        entry_id=str(uuid.uuid4()), user_id="u", date=day,
        exercises=exercises, energy_tags=tags or [EnergyTag.NORMAL],
    )


# --- Period events ---------------------------------------------------------

def test_period_event_round_trip_and_order(db):
    d1, d2 = date(2026, 6, 1), date(2026, 6, 28)
    storage.save_period_event(PeriodEvent(str(uuid.uuid4()), "u", "start", d1), db)
    storage.save_period_event(PeriodEvent(str(uuid.uuid4()), "u", "end", date(2026, 6, 5)), db)
    storage.save_period_event(PeriodEvent(str(uuid.uuid4()), "u", "start", d2), db)
    events = storage.get_period_events("u", db)
    # chronological by date
    assert [e.kind for e in events] == ["start", "end", "start"]
    assert events[0].date == d1 and events[-1].date == d2


def test_period_event_date_is_encrypted_at_rest(db):
    d = date(2026, 6, 1)
    storage.save_period_event(PeriodEvent(str(uuid.uuid4()), "u", "start", d), db)
    conn = storage.get_connection(db)
    raw = conn.execute("SELECT date_enc FROM period_events").fetchone()["date_enc"]
    conn.close()
    assert d.isoformat() not in raw  # ciphertext, not plaintext


def test_delete_all_removes_period_events(db):
    storage.save_period_event(PeriodEvent(str(uuid.uuid4()), "u", "start", date(2026, 6, 1)), db)
    storage.delete_all_user_data("u", db)
    assert storage.get_period_events("u", db) == []


# --- Previous sets & PR detection -----------------------------------------

def test_previous_exercise_sets_returns_most_recent_past_session(db):
    older = _workout(date(2026, 6, 1), [Exercise("Squat", [WorkoutSet(60, 5)])])
    newer = _workout(date(2026, 6, 8), [Exercise("Squat", [WorkoutSet(70, 5), WorkoutSet(70, 4)])])
    storage.save_workout(older, db)
    storage.save_workout(newer, db)
    prev = storage.previous_exercise_sets("u", "squat", db)  # case-insensitive
    assert [(s.weight, s.reps) for s in prev] == [(70, 5), (70, 4)]


def test_previous_exercise_sets_none_when_never_logged(db):
    assert storage.previous_exercise_sets("u", "Deadlift", db) is None


def test_best_working_weight_ignores_warmups_and_spans_history(db):
    storage.save_workout(_workout(date(2026, 6, 1), [
        Exercise("Bench", [WorkoutSet(40, 8, SetType.NORMAL)])]), db)
    storage.save_workout(_workout(date(2026, 6, 8), [
        Exercise("bench", [WorkoutSet(80, 1, SetType.WARMUP), WorkoutSet(45, 8, SetType.NORMAL)])]), db)
    # heaviest NON-warmup across history is 45, not the 80 warmup
    assert storage.best_working_weight("u", "Bench", db) == 45.0


# --- New energy tags -------------------------------------------------------

def test_new_symptom_tags_exist():
    for name in ("HEADACHE", "HOT_FLASHES", "LOWER_BACK_PAIN", "NAUSEA"):
        assert hasattr(EnergyTag, name)


def test_new_tags_have_curated_messages():
    for tag in (EnergyTag.HEADACHE, EnergyTag.HOT_FLASHES, EnergyTag.LOWER_BACK_PAIN, EnergyTag.NAUSEA):
        assert get_fallback_message(tag) != GENERIC_FALLBACK
