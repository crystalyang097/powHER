"""SQLite storage with Fernet encryption for cycle-derived fields.

Cycle data is health data. last_period_start, cycle_day, and phase are
encrypted at rest. Everything else (goal, exercises, energy tags) is
plain -- there's nothing sensitive about a logged bench press.
"""

import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv, set_key

from powher.models import (
    EnergyTag,
    Exercise,
    PeriodEvent,
    Phase,
    Profile,
    Routine,
    RoutineExercise,
    SetType,
    WorkoutEntry,
    WorkoutSet,
    normalize_exercise_name,
)

load_dotenv()

DB_PATH = Path(__file__).resolve().parent.parent / "powher.db"
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _get_or_create_key() -> bytes:
    key = os.getenv("POWHER_ENCRYPTION_KEY")
    if key:
        return key.encode()
    key = Fernet.generate_key()
    if not ENV_PATH.exists():
        ENV_PATH.touch()
    set_key(str(ENV_PATH), "POWHER_ENCRYPTION_KEY", key.decode())
    os.environ["POWHER_ENCRYPTION_KEY"] = key.decode()
    return key


_fernet = Fernet(_get_or_create_key())


def _encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def _decrypt(value: str | None) -> str | None:
    if value is None:
        return None
    return _fernet.decrypt(value.encode()).decode()


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            user_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            goal TEXT NOT NULL,
            last_period_start_enc TEXT,
            cycle_length INTEGER NOT NULL DEFAULT 28,
            cycle_applicable INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workouts (
            entry_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            exercises_json TEXT NOT NULL,
            energy_tags TEXT NOT NULL,
            cycle_day_enc TEXT,
            phase_enc TEXT,
            notes TEXT DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS routines (
            routine_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            exercises_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS period_events (
            event_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            date_enc TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def save_profile(profile: Profile, db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    last_period_enc = (
        _encrypt(profile.last_period_start.isoformat()) if profile.last_period_start else None
    )
    conn.execute(
        """
        INSERT INTO profiles (user_id, display_name, goal, last_period_start_enc,
                               cycle_length, cycle_applicable, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            display_name=excluded.display_name,
            goal=excluded.goal,
            last_period_start_enc=excluded.last_period_start_enc,
            cycle_length=excluded.cycle_length,
            cycle_applicable=excluded.cycle_applicable
        """,
        (
            profile.user_id,
            profile.display_name,
            profile.goal,
            last_period_enc,
            profile.cycle_length,
            int(profile.cycle_applicable),
            profile.created_at.isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_profile(user_id: str, db_path: Path = DB_PATH) -> Profile | None:
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    last_period_start = None
    decrypted = _decrypt(row["last_period_start_enc"])
    if decrypted:
        last_period_start = date.fromisoformat(decrypted)
    return Profile(
        user_id=row["user_id"],
        display_name=row["display_name"],
        goal=row["goal"],
        last_period_start=last_period_start,
        cycle_length=row["cycle_length"],
        cycle_applicable=bool(row["cycle_applicable"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _exercise_to_dict(ex: Exercise) -> dict:
    return {
        "name": ex.name,
        "notes": ex.notes,
        "sets": [
            {"weight": s.weight, "reps": s.reps, "set_type": s.set_type.value} for s in ex.sets
        ],
    }


def _exercise_from_dict(data: dict) -> Exercise:
    if isinstance(data.get("sets"), int):
        # Legacy format: {"name", "weight", "reps", "sets": int} — expand into
        # that many identical normal sets.
        sets = [
            WorkoutSet(weight=data["weight"], reps=data["reps"], set_type=SetType.NORMAL)
            for _ in range(data["sets"])
        ]
        return Exercise(name=data["name"], sets=sets)
    return Exercise(
        name=data["name"],
        sets=[
            WorkoutSet(weight=s["weight"], reps=s["reps"], set_type=SetType(s["set_type"]))
            for s in data["sets"]
        ],
        notes=data.get("notes", ""),
    )


def save_workout(entry: WorkoutEntry, db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    exercises_json = json.dumps([_exercise_to_dict(e) for e in entry.exercises])
    energy_tags = ",".join(tag.value for tag in entry.energy_tags)
    cycle_day_enc = _encrypt(str(entry.cycle_day)) if entry.cycle_day is not None else None
    phase_enc = _encrypt(entry.phase.value) if entry.phase is not None else None
    conn.execute(
        """
        INSERT INTO workouts (entry_id, user_id, date, exercises_json, energy_tags,
                               cycle_day_enc, phase_enc, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(entry_id) DO UPDATE SET
            date=excluded.date,
            exercises_json=excluded.exercises_json,
            energy_tags=excluded.energy_tags,
            cycle_day_enc=excluded.cycle_day_enc,
            phase_enc=excluded.phase_enc,
            notes=excluded.notes
        """,
        (
            entry.entry_id,
            entry.user_id,
            entry.date.isoformat(),
            exercises_json,
            energy_tags,
            cycle_day_enc,
            phase_enc,
            entry.notes,
        ),
    )
    conn.commit()
    conn.close()


def _row_to_workout(row: sqlite3.Row) -> WorkoutEntry:
    exercises = [_exercise_from_dict(e) for e in json.loads(row["exercises_json"])]
    energy_tags = [EnergyTag(t) for t in row["energy_tags"].split(",") if t]
    cycle_day_dec = _decrypt(row["cycle_day_enc"])
    phase_dec = _decrypt(row["phase_enc"])
    return WorkoutEntry(
        entry_id=row["entry_id"],
        user_id=row["user_id"],
        date=date.fromisoformat(row["date"]),
        exercises=exercises,
        energy_tags=energy_tags,
        cycle_day=int(cycle_day_dec) if cycle_day_dec is not None else None,
        phase=Phase(phase_dec) if phase_dec is not None else None,
        notes=row["notes"] or "",
    )


def get_workouts(user_id: str, db_path: Path = DB_PATH) -> list[WorkoutEntry]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM workouts WHERE user_id = ? ORDER BY date DESC", (user_id,)
    ).fetchall()
    conn.close()
    return [_row_to_workout(r) for r in rows]


def last_logged_weight(user_id: str, exercise_name: str, db_path: Path = DB_PATH) -> float | None:
    """Most recent logged weight for a given exercise, for load-bound guardrails."""
    target = normalize_exercise_name(exercise_name)
    for entry in get_workouts(user_id, db_path):
        for ex in entry.exercises:
            if normalize_exercise_name(ex.name) == target:
                weight = ex.top_working_weight()
                if weight is not None:
                    return weight
    return None


def save_routine(routine: Routine, db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    exercises_json = json.dumps(
        [{"name": e.name, "set_types": [t.value for t in e.set_types]} for e in routine.exercises]
    )
    conn.execute(
        """
        INSERT INTO routines (routine_id, user_id, name, exercises_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(routine_id) DO UPDATE SET
            name=excluded.name,
            exercises_json=excluded.exercises_json
        """,
        (
            routine.routine_id,
            routine.user_id,
            routine.name,
            exercises_json,
            routine.created_at.isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def _row_to_routine(row: sqlite3.Row) -> Routine:
    exercises = [
        RoutineExercise(name=e["name"], set_types=[SetType(t) for t in e["set_types"]])
        for e in json.loads(row["exercises_json"])
    ]
    return Routine(
        routine_id=row["routine_id"],
        user_id=row["user_id"],
        name=row["name"],
        exercises=exercises,
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def get_routines(user_id: str, db_path: Path = DB_PATH) -> list[Routine]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM routines WHERE user_id = ? ORDER BY created_at", (user_id,)
    ).fetchall()
    conn.close()
    return [_row_to_routine(r) for r in rows]


def delete_routine(routine_id: str, db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    conn.execute("DELETE FROM routines WHERE routine_id = ?", (routine_id,))
    conn.commit()
    conn.close()


def previous_exercise_sets(
    user_id: str, exercise_name: str, db_path: Path = DB_PATH
) -> list[WorkoutSet] | None:
    """Sets from the most recent past workout containing this (normalized)
    exercise, for the 'last time' reference in the set editor. None if never logged."""
    target = normalize_exercise_name(exercise_name)
    for entry in get_workouts(user_id, db_path):  # already sorted date DESC
        for ex in entry.exercises:
            if normalize_exercise_name(ex.name) == target:
                return ex.sets
    return None


def best_working_weight(user_id: str, exercise_name: str, db_path: Path = DB_PATH) -> float | None:
    """Heaviest non-warm-up weight ever logged for this (normalized) exercise,
    across all history. Used to detect personal records."""
    target = normalize_exercise_name(exercise_name)
    best: float | None = None
    for entry in get_workouts(user_id, db_path):
        for ex in entry.exercises:
            if normalize_exercise_name(ex.name) == target:
                w = ex.top_working_weight()
                if w is not None and (best is None or w > best):
                    best = w
    return best


def save_period_event(event: PeriodEvent, db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    conn.execute(
        """
        INSERT INTO period_events (event_id, user_id, kind, date_enc, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(event_id) DO UPDATE SET
            kind=excluded.kind,
            date_enc=excluded.date_enc
        """,
        (
            event.event_id,
            event.user_id,
            event.kind,
            _encrypt(event.date.isoformat()),
            event.created_at.isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_period_events(user_id: str, db_path: Path = DB_PATH) -> list[PeriodEvent]:
    """Period events in chronological order (oldest first)."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM period_events WHERE user_id = ? ORDER BY created_at", (user_id,)
    ).fetchall()
    conn.close()
    events = [
        PeriodEvent(
            event_id=r["event_id"],
            user_id=r["user_id"],
            kind=r["kind"],
            date=date.fromisoformat(_decrypt(r["date_enc"])),
            created_at=datetime.fromisoformat(r["created_at"]),
        )
        for r in rows
    ]
    return sorted(events, key=lambda e: (e.date, e.created_at))


def delete_all_user_data(user_id: str, db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    conn.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM workouts WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM routines WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM period_events WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
