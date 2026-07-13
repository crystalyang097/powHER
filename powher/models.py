from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Literal

Goal = Literal["strength", "hypertrophy", "endurance", "general_fitness", "fat_loss"]


class EnergyTag(str, Enum):
    ENERGIZED = "ENERGIZED"
    NORMAL = "NORMAL"
    TIRED = "TIRED"
    DRAINED = "DRAINED"
    IN_PAIN = "IN_PAIN"
    CRAMPING = "CRAMPING"
    FASTER_FATIGUE = "FASTER_FATIGUE"


class Phase(str, Enum):
    MENSTRUAL = "MENSTRUAL"
    FOLLICULAR = "FOLLICULAR"
    OVULATORY = "OVULATORY"
    LUTEAL = "LUTEAL"


@dataclass
class Profile:
    user_id: str
    display_name: str
    goal: Goal
    last_period_start: date | None  # ENCRYPTED at rest
    cycle_length: int = 28
    cycle_applicable: bool = True  # False if user selected "may not apply"
    created_at: datetime = field(default_factory=datetime.now)


class SetType(str, Enum):
    WARMUP = "WARMUP"
    NORMAL = "NORMAL"
    FAILURE = "FAILURE"


@dataclass
class WorkoutSet:
    weight: float
    reps: int
    set_type: SetType = SetType.NORMAL


@dataclass
class Exercise:
    name: str
    sets: list[WorkoutSet]
    notes: str = ""

    def top_working_weight(self) -> float | None:
        """Heaviest non-warm-up weight, falling back to any set."""
        pool = [s.weight for s in self.sets if s.set_type != SetType.WARMUP]
        pool = pool or [s.weight for s in self.sets]
        return max(pool) if pool else None


@dataclass
class WorkoutEntry:
    entry_id: str
    user_id: str
    date: date
    exercises: list[Exercise]
    energy_tags: list[EnergyTag]
    cycle_day: int | None = None  # derived, ENCRYPTED
    phase: Phase | None = None  # derived, ENCRYPTED
    notes: str = ""
