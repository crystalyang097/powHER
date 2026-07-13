"""Tests for exercise-name normalization (case, spacing, plurals)."""

import pytest

from powher.models import normalize_exercise_name as norm


@pytest.mark.parametrize(
    "a, b",
    [
        ("Goblet Squat", "goblet squat"),          # case
        ("goblet squat", "goblet squat "),         # trailing space
        ("goblet  squat", "goblet squat"),         # collapsed inner spacing
        ("Goblet Squat", "goblet squats"),         # plural
        ("Bench Press", "bench presses"),          # es-plural of an -ss word
        ("Calf Raise", "calf raises"),             # -se word, drop only s
        ("Walking Lunge", "walking lunges"),       # -ge word, drop only s
        ("Cable Crunch", "cable crunches"),        # ch -> es plural
        ("Deadlift", "deadlifts"),                 # plain s
    ],
)
def test_variants_normalize_together(a, b):
    assert norm(a) == norm(b)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Bench Press", "bench press"),   # ss guard: not mangled to "pres"
        ("Lat Pulldowns", "lat pulldown"),
        ("Flyes", "flye"),
        ("abs", "abs"),                   # short-token guard
    ],
)
def test_expected_forms(name, expected):
    assert norm(name) == expected


def test_distinct_exercises_stay_distinct():
    assert norm("Bench Press") != norm("Leg Press")
    assert norm("Front Squat") != norm("Back Squat")
