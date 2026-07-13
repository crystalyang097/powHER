"""Round-trip, ordering, and deletion tests for saved routines."""

import uuid

import pytest

from powher import storage
from powher.models import Routine, RoutineExercise, SetType


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    storage.init_db(path)
    return path


def _routine(name, exercises):
    return Routine(
        routine_id=str(uuid.uuid4()), user_id="u", name=name, exercises=exercises
    )


def test_routine_round_trip_preserves_order_and_set_types(db):
    r = _routine(
        "Leg Day",
        [
            RoutineExercise("Squat", [SetType.WARMUP, SetType.NORMAL, SetType.FAILURE]),
            RoutineExercise("Romanian Deadlift", [SetType.NORMAL, SetType.NORMAL]),
        ],
    )
    storage.save_routine(r, db)
    loaded = storage.get_routines("u", db)
    assert len(loaded) == 1
    got = loaded[0]
    assert got.name == "Leg Day"
    assert [e.name for e in got.exercises] == ["Squat", "Romanian Deadlift"]
    assert got.exercises[0].set_types == [SetType.WARMUP, SetType.NORMAL, SetType.FAILURE]
    assert got.exercises[1].set_types == [SetType.NORMAL, SetType.NORMAL]


def test_routines_returned_in_creation_order(db):
    storage.save_routine(_routine("Push", [RoutineExercise("Bench", [SetType.NORMAL])]), db)
    storage.save_routine(_routine("Pull", [RoutineExercise("Row", [SetType.NORMAL])]), db)
    assert [r.name for r in storage.get_routines("u", db)] == ["Push", "Pull"]


def test_delete_routine(db):
    r = _routine("Push", [RoutineExercise("Bench", [SetType.NORMAL])])
    storage.save_routine(r, db)
    storage.delete_routine(r.routine_id, db)
    assert storage.get_routines("u", db) == []


def test_delete_all_user_data_removes_routines(db):
    storage.save_routine(_routine("Push", [RoutineExercise("Bench", [SetType.NORMAL])]), db)
    storage.delete_all_user_data("u", db)
    assert storage.get_routines("u", db) == []
