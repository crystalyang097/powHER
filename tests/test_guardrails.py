from powher.guardrails import (
    BANNED_PHRASES,
    check_disordered_eating_guard,
    check_load_bounds,
    check_no_phase_prescribed_load,
    check_no_unsourced_claims,
    check_pain_no_load_prescription,
    check_tone,
)
from powher.models import EnergyTag


def test_load_bounds_blocks_over_10_percent_increase():
    result = check_load_bounds("some text", last_logged_weight=100, proposed_weight=111)
    assert result.passed is False


def test_load_bounds_allows_10_percent_increase():
    result = check_load_bounds("some text", last_logged_weight=100, proposed_weight=110)
    assert result.passed is True


def test_load_bounds_allows_decrease():
    result = check_load_bounds("some text", last_logged_weight=100, proposed_weight=80)
    assert result.passed is True


def test_load_bounds_passes_when_no_weights_given():
    result = check_load_bounds("some text", last_logged_weight=None, proposed_weight=None)
    assert result.passed is True


def test_no_unsourced_claims_requires_citation():
    assert check_no_unsourced_claims("text", cited_source_ids=set()).passed is False
    assert check_no_unsourced_claims("text", cited_source_ids={"TRAINING-PRINCIPLES"}).passed is True


def test_no_phase_prescribed_load_rejects_phase_percent():
    text = "In your luteal phase you should lift 15% less."
    assert check_no_phase_prescribed_load(text).passed is False


def test_no_phase_prescribed_load_allows_energy_based_language():
    text = "Since you're feeling tired today, consider lightening the load a bit."
    assert check_no_phase_prescribed_load(text).passed is True


def test_no_phase_prescribed_load_allows_phase_education_without_load_number():
    text = "You're currently in your luteal phase. Some women notice more fatigue here."
    assert check_no_phase_prescribed_load(text).passed is True


def test_pain_tag_blocks_load_prescription():
    text = "Try 3 sets of 8 reps at 135 lbs today."
    result = check_pain_no_load_prescription([EnergyTag.IN_PAIN], text)
    assert result.passed is False


def test_pain_tag_allows_text_without_numbers():
    text = "Gentle movement or rest are both good options today."
    result = check_pain_no_load_prescription([EnergyTag.IN_PAIN], text)
    assert result.passed is True


def test_non_pain_tag_ignores_numbers():
    text = "Try 3 sets of 8 reps at 135 lbs today."
    result = check_pain_no_load_prescription([EnergyTag.NORMAL], text)
    assert result.passed is True


def test_tone_check_rejects_banned_phrases():
    for phrase in BANNED_PHRASES:
        text = f"Don't let this {phrase} you."
        assert check_tone(text).passed is False, f"'{phrase}' should be rejected"


def test_tone_check_allows_clean_text():
    assert check_tone("You showed up today. That's what matters.").passed is True


def test_disordered_eating_guard_rejects_calorie_language():
    assert check_disordered_eating_guard("Cut 200 calories today.").passed is False
    assert check_disordered_eating_guard("Compensate for yesterday's meal.").passed is False


def test_disordered_eating_guard_allows_clean_text():
    assert check_disordered_eating_guard("Focus on your training composition today.").passed is True
