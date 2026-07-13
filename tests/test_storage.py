"""Round-trip and legacy-format tests for workout storage."""

import json
from datetime import date

import pytest

from powher import storage
from powher.models import EnergyTag, Exercise, SetType, WorkoutEntry, WorkoutSet


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    storage.init_db(path)
    return path


def _entry(exercises):
    return WorkoutEntry(
        entry_id="e1", user_id="u", date=date(2026, 7, 13),
        exercises=exercises, energy_tags=[EnergyTag.NORMAL],
    )


def test_per_set_round_trip(db):
    exercises = [
        Exercise(
            name="Squat",
            sets=[
                WorkoutSet(60.0, 10, SetType.WARMUP),
                WorkoutSet(100.0, 8, SetType.NORMAL),
                WorkoutSet(100.0, 6, SetType.FAILURE),
            ],
            notes="paused reps",
        )
    ]
    storage.save_workout(_entry(exercises), db)
    loaded = storage.get_workouts("u", db)[0].exercises[0]
    assert loaded.name == "Squat"
    assert loaded.notes == "paused reps"
    assert [(s.weight, s.reps, s.set_type) for s in loaded.sets] == [
        (60.0, 10, SetType.WARMUP),
        (100.0, 8, SetType.NORMAL),
        (100.0, 6, SetType.FAILURE),
    ]


def test_legacy_format_expands_to_sets(db):
    legacy_json = json.dumps([{"name": "Bench", "weight": 45.0, "reps": 8, "sets": 3}])
    conn = storage.get_connection(db)
    conn.execute(
        "INSERT INTO workouts (entry_id, user_id, date, exercises_json, energy_tags) "
        "VALUES (?, ?, ?, ?, ?)",
        ("legacy1", "u", "2026-06-01", legacy_json, "NORMAL"),
    )
    conn.commit()
    conn.close()
    loaded = storage.get_workouts("u", db)[0].exercises[0]
    assert loaded.name == "Bench"
    assert len(loaded.sets) == 3
    assert all(s.weight == 45.0 and s.reps == 8 and s.set_type == SetType.NORMAL for s in loaded.sets)


def test_last_logged_weight_ignores_warmups(db):
    exercises = [
        Exercise(
            name="Deadlift",
            sets=[WorkoutSet(140.0, 5, SetType.WARMUP), WorkoutSet(120.0, 5, SetType.NORMAL)],
        )
    ]
    storage.save_workout(_entry(exercises), db)
    assert storage.last_logged_weight("u", "Deadlift", db) == 120.0


def test_last_logged_weight_matches_plural_and_case(db):
    exercises = [Exercise(name="Goblet Squats", sets=[WorkoutSet(24.0, 10, SetType.NORMAL)])]
    storage.save_workout(_entry(exercises), db)
    assert storage.last_logged_weight("u", "goblet squat", db) == 24.0
