"""Hard-coded guardrails, run post-generation. Not left to prompting alone.

Every rule here corresponds to a row in SPEC.md §9 / README.md §8.
"""

import re
from dataclasses import dataclass

from powher.models import EnergyTag, Phase

BANNED_PHRASES = [
    "behind",
    "excuse",
    "push through",
    "make up for",
    "lost progress",
    "despite your period",
]

# Phrases that tie a load number to a phase rather than an energy tag.
PHASE_LOAD_PATTERN = re.compile(
    r"\b(menstrual|follicular|ovulatory|luteal)\s+phase\b.{0,60}?"
    r"(\d+(\.\d+)?\s?%|\blift\b.{0,20}\b(less|more|lighter|heavier)\b)",
    re.IGNORECASE | re.DOTALL,
)

LOAD_INCREASE_PATTERN = re.compile(r"(\d+(\.\d+)?)\s?%\s*(increase|more|heavier|higher)", re.IGNORECASE)

MAX_LOAD_INCREASE_PCT = 10.0
AMENORRHEA_THRESHOLD_DAYS = 90


@dataclass
class GuardrailResult:
    passed: bool
    reason: str = ""


def check_no_unsourced_claims(text: str, cited_source_ids: set[str]) -> GuardrailResult:
    """A claim ships only if at least one corpus chunk was actually retrieved and cited.

    This is a coarse, necessary-not-sufficient check: if generation produced
    any fitness/health claim but retrieval returned nothing, there is no
    grounding to point to, so the output is rejected outright.
    """
    if not cited_source_ids:
        return GuardrailResult(False, "No retrieved source backs this output.")
    return GuardrailResult(True)


def check_no_phase_prescribed_load(text: str) -> GuardrailResult:
    if PHASE_LOAD_PATTERN.search(text):
        return GuardrailResult(
            False, "Output ties a load number/direction to a cycle phase rather than an energy tag."
        )
    return GuardrailResult(True)


def check_load_bounds(text: str, last_logged_weight: float | None, proposed_weight: float | None) -> GuardrailResult:
    if last_logged_weight is None or proposed_weight is None:
        return GuardrailResult(True)
    if proposed_weight <= last_logged_weight:
        return GuardrailResult(True)
    pct_increase = (proposed_weight - last_logged_weight) / last_logged_weight * 100
    if pct_increase > MAX_LOAD_INCREASE_PCT:
        return GuardrailResult(
            False,
            f"Proposed weight {proposed_weight} is a {pct_increase:.1f}% increase over last "
            f"logged {last_logged_weight}, exceeding the {MAX_LOAD_INCREASE_PCT}% bound.",
        )
    return GuardrailResult(True)


def check_tone(text: str) -> GuardrailResult:
    lowered = text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lowered:
            return GuardrailResult(False, f"Banned phrase detected: '{phrase}'.")
    return GuardrailResult(True)


def check_pain_no_load_prescription(energy_tags: list[EnergyTag], text: str) -> GuardrailResult:
    if EnergyTag.IN_PAIN not in energy_tags:
        return GuardrailResult(True)
    if re.search(r"\d+\s?(lbs?|kg|reps?|sets?)\b", text, re.IGNORECASE):
        return GuardrailResult(False, "IN_PAIN tag present but output prescribes a load/rep/set number.")
    return GuardrailResult(True)


def check_disordered_eating_guard(text: str) -> GuardrailResult:
    lowered = text.lower()
    banned = ["calorie", "calories", "goal weight", "body fat %", "compensate for", "streak"]
    for phrase in banned:
        if phrase in lowered:
            return GuardrailResult(False, f"Disordered-eating-adjacent phrase detected: '{phrase}'.")
    return GuardrailResult(True)


def amenorrhea_referral_needed(days_since_last_period: int | None) -> bool:
    if days_since_last_period is None:
        return False
    return days_since_last_period >= AMENORRHEA_THRESHOLD_DAYS


def run_all_guardrails(
    text: str,
    *,
    cited_source_ids: set[str],
    energy_tags: list[EnergyTag],
    last_logged_weight: float | None = None,
    proposed_weight: float | None = None,
) -> list[GuardrailResult]:
    """Run every post-generation guardrail. Caller should reject/regenerate/fall
    back to messages.py if any result has passed=False."""
    return [
        check_no_unsourced_claims(text, cited_source_ids),
        check_no_phase_prescribed_load(text),
        check_load_bounds(text, last_logged_weight, proposed_weight),
        check_tone(text),
        check_pain_no_load_prescription(energy_tags, text),
        check_disordered_eating_guard(text),
    ]
