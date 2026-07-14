from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Literal

Goal = Literal["strength", "hypertrophy", "endurance", "general_fitness", "fat_loss"]


def _singularize(word: str) -> str:
    """Best-effort singular form of one word, tuned for gym vocabulary.

    English plurals are irregular, so this is a heuristic, not a stemmer. It
    deliberately leaves words ending in "ss" alone so "press" is never mangled
    into "pres". Good enough to merge "squats"/"squat"; a fixed exercise
    library will replace it later.
    """
    if len(word) <= 3:
        return word  # don't butcher short tokens ("abs", "ups")
    if word.endswith("ies"):
        return word[:-3] + "y"  # flies -> fly
    if word.endswith("sses"):
        return word[:-2]  # presses -> press
    if word.endswith(("ches", "shes", "xes", "zes")):
        return word[:-2]  # crunches -> crunch, boxes -> box
    if word.endswith("ss") or word.endswith("us") or word.endswith("is"):
        return word  # press, status, and the like are not plurals
    if word.endswith("s"):
        return word[:-1]  # squats -> squat, raises -> raise, lunges -> lunge
    return word


def normalize_exercise_name(name: str) -> str:
    """Canonical key for matching exercises: lowercased, trimmed, singularized.

    Used everywhere two exercise names are compared (history trends, load
    guardrail) so spelling, case, spacing, and plural variants all resolve to
    the same lift.
    """
    words = name.strip().lower().split()
    return " ".join(_singularize(w) for w in words)


class EnergyTag(str, Enum):
    ENERGIZED = "ENERGIZED"
    NORMAL = "NORMAL"
    TIRED = "TIRED"
    DRAINED = "DRAINED"
    IN_PAIN = "IN_PAIN"
    CRAMPING = "CRAMPING"
    FASTER_FATIGUE = "FASTER_FATIGUE"
    # Symptoms that affect energy during training. LOWER_BACK_PAIN is a hook for
    # future symptom-aware programming (avoid lower-back-loading lifts); for now
    # it simply informs the recommendation like any other tag.
    HEADACHE = "HEADACHE"
    HOT_FLASHES = "HOT_FLASHES"
    LOWER_BACK_PAIN = "LOWER_BACK_PAIN"
    NAUSEA = "NAUSEA"


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


@dataclass
class RoutineExercise:
    """One exercise slot in a saved routine: a name and the set structure to
    pre-fill. Weight and reps are entered fresh each session, so only the set
    types (order and count) are stored here."""

    name: str
    set_types: list[SetType]


@dataclass
class Routine:
    """A named, ordered group of exercises the user can start a workout from."""

    routine_id: str
    user_id: str
    name: str
    exercises: list[RoutineExercise]
    created_at: datetime = field(default_factory=datetime.now)


PeriodEventKind = Literal["start", "end"]


@dataclass
class PeriodEvent:
    """A logged start or end of a period. Health data — the date is encrypted
    at rest. The running history of these is kept so patterns can be reviewed."""

    event_id: str
    user_id: str
    kind: PeriodEventKind  # "start" | "end"
    date: date  # ENCRYPTED at rest
    created_at: datetime = field(default_factory=datetime.now)
