from datetime import date, datetime

from powher.context_builder import build_context, detect_pattern
from powher.models import EnergyTag, Phase, Profile, WorkoutEntry, Exercise, WorkoutSet


def _profile(**overrides) -> Profile:
    defaults = dict(
        user_id="test_user",
        display_name="Test",
        goal="strength",
        last_period_start=date(2026, 6, 1),
        cycle_length=28,
        cycle_applicable=True,
        created_at=datetime.now(),
    )
    defaults.update(overrides)
    return Profile(**defaults)


def test_cycle_applicable_false_hides_phase_and_excludes_phase_chunks():
    profile = _profile(cycle_applicable=False, last_period_start=None)
    ctx = build_context(profile, [EnergyTag.NORMAL], "strength", "", [])
    assert ctx.phase is None
    assert "MENSTRUAL" not in ctx.user_prompt
    assert "FOLLICULAR" not in ctx.user_prompt
    assert "OVULATORY" not in ctx.user_prompt
    assert "LUTEAL" not in ctx.user_prompt
    assert "PHASE-EVIDENCE" not in ctx.cited_source_ids
    assert "PHASE-EDUCATION" not in ctx.cited_source_ids


def test_cycle_applicable_true_surfaces_phase_as_context():
    profile = _profile(cycle_applicable=True, last_period_start=date(2026, 6, 1))
    ctx = build_context(profile, [EnergyTag.NORMAL], "strength", "", [])
    assert ctx.phase is not None
    assert ctx.phase.value in ctx.user_prompt
    assert "not for load prescription" in ctx.user_prompt


def test_detect_pattern_requires_at_least_two_matches():
    history = [
        WorkoutEntry(
            entry_id="1", user_id="u", date=date(2026, 6, 15),
            exercises=[Exercise("Squat", [WorkoutSet(100, 8), WorkoutSet(100, 8), WorkoutSet(100, 8)])], energy_tags=[EnergyTag.TIRED],
            cycle_day=15, phase=Phase.OVULATORY,
        )
    ]
    assert detect_pattern(history, current_cycle_day=15, cycle_length=28) is None


def test_detect_pattern_surfaces_recurring_tag():
    history = [
        WorkoutEntry(
            entry_id="1", user_id="u", date=date(2026, 5, 18),
            exercises=[Exercise("Squat", [WorkoutSet(100, 8), WorkoutSet(100, 8), WorkoutSet(100, 8)])], energy_tags=[EnergyTag.TIRED],
            cycle_day=16, phase=Phase.LUTEAL,
        ),
        WorkoutEntry(
            entry_id="2", user_id="u", date=date(2026, 6, 16),
            exercises=[Exercise("Squat", [WorkoutSet(100, 8), WorkoutSet(100, 8), WorkoutSet(100, 8)])], energy_tags=[EnergyTag.TIRED],
            cycle_day=15, phase=Phase.LUTEAL,
        ),
    ]
    note = detect_pattern(history, current_cycle_day=15, cycle_length=28)
    assert note is not None
    assert "tired" in note.lower()
    assert "pattern, not a rule" in note
