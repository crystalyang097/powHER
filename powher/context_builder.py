"""Assembles phase, energy tag, goal, recent history, and retrieved evidence
into a system prompt for Claude. This is the heart of the app per SPEC.md §2.
"""

from dataclasses import dataclass, field

from powher.cycle import amenorrhea_flag, phase_for_date, ESTIMATE_NOTE
from powher.messages import get_messages
from powher.models import EnergyTag, Phase, Profile, WorkoutEntry
from powher.retriever import Chunk, get_retriever

SYSTEM_PROMPT_HEADER = """\
You are the recommendation voice inside powHER, a cycle-aware fitness app for women.

Non-negotiable rules:
1. You may ONLY make fitness/health claims that appear in the "Retrieved evidence" \
section below. If no chunk supports a claim, do not make it. If you're unsure, say \
less rather than invent something.
2. Every recommendation must be driven by the user's ENERGY TAG for today, never by \
her cycle phase. Phase (if shown below) is context and education only. NEVER write a \
sentence that ties a load number or direction to a phase (e.g. "in your luteal phase, \
lift X% less"). That number does not exist in the evidence and inventing it is the \
single worst failure mode for this app.
3. Never suggest increasing a logged weight by more than 10% over last time.
4. If the energy tag is IN_PAIN, do not prescribe any load, rep, or set number. Offer \
gentle movement or rest, and if pain is noted as severe or recurring, gently suggest \
talking to a doctor.
5. Tone: gentle, warm, second-person, short. Pinterest-inspirational-quote energy, not \
drill sergeant, not clinical. Never imply she is behind, weaker, or that her period is \
an obstacle. Match the voice of the example messages below.
6. Cite your source: end with which corpus source_id(s) grounded your claims.

Write two things, clearly separated, as plain text (no markdown bold on the labels \
themselves):
RECOMMENDATION: a short, concrete suggestion for today's session.
MESSAGE: one short, warm, supportive sentence or two.
Then end with a final line starting "Sources:" listing the source_id(s) you drew on.
"""


@dataclass
class ContextBundle:
    system_prompt: str
    user_prompt: str
    cited_source_ids: set[str] = field(default_factory=set)
    phase: Phase | None = None
    amenorrhea_referral: bool = False
    pattern_note: str | None = None


def _retrieval_query(energy_tags: list[EnergyTag], goal: str, notes: str) -> str:
    tag_text = " ".join(t.value.replace("_", " ").lower() for t in energy_tags)
    return f"{tag_text} {goal.replace('_', ' ')} training recommendation {notes}".strip()


def _format_evidence(chunks: list[Chunk]) -> str:
    if not chunks:
        return "(none retrieved)"
    lines = []
    for c in chunks:
        lines.append(f"[{c.source_id} | {c.heading}]\n{c.text}")
    return "\n\n".join(lines)


def detect_pattern(
    history: list[WorkoutEntry], current_cycle_day: int | None, cycle_length: int, window: int = 2
) -> str | None:
    """If the user has consistently tagged a similar cycle-day range a given way
    across >=2 distinct cycles, surface it as her observed pattern (never a
    scientific claim about women in general)."""
    if current_cycle_day is None or len(history) < 2:
        return None

    def in_window(day: int) -> bool:
        diff = min(
            abs(day - current_cycle_day),
            cycle_length - abs(day - current_cycle_day),
        )
        return diff <= window

    matches = [e for e in history if e.cycle_day is not None and in_window(e.cycle_day)]
    if len(matches) < 2:
        return None

    tag_counts: dict[EnergyTag, int] = {}
    for entry in matches:
        for tag in entry.energy_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    if not tag_counts:
        return None
    top_tag, count = max(tag_counts.items(), key=lambda kv: kv[1])
    if count < 2:
        return None

    label = top_tag.value.replace("_", " ").lower()
    return (
        f"Heads up — around this point in your last cycles you tagged '{label}'. "
        f"That's your pattern, not a rule. You might feel completely different today. "
        f"How are you feeling?"
    )


def build_context(
    profile: Profile,
    energy_tags: list[EnergyTag],
    goal: str,
    notes: str,
    history: list[WorkoutEntry],
) -> ContextBundle:
    phase: Phase | None = None
    current_cycle_day: int | None = None
    pattern_note: str | None = None
    amenorrhea_referral = False

    if profile.cycle_applicable and profile.last_period_start is not None:
        from powher.cycle import cycle_day as compute_cycle_day

        current_cycle_day = compute_cycle_day(profile.last_period_start, profile.cycle_length)
        phase = phase_for_date(profile.last_period_start, profile.cycle_length)
        amenorrhea_referral = amenorrhea_flag(profile.last_period_start)
        pattern_note = detect_pattern(history, current_cycle_day, profile.cycle_length)

    query = _retrieval_query(energy_tags, goal, notes)
    retriever = get_retriever()
    chunks = retriever.query(query, n_results=4, exclude_phase=not profile.cycle_applicable)
    cited_source_ids = {c.source_id for c in chunks}

    tone_examples = []
    for tag in energy_tags:
        tone_examples.extend(get_messages(tag, None)[:2])

    context_lines = [
        f"Energy tag(s) today: {', '.join(t.value for t in energy_tags)}",
        f"Goal: {goal}",
    ]
    if phase is not None:
        context_lines.append(f"Estimated phase (context only, not for load prescription): {phase.value}")
        context_lines.append(f"Phase note: {ESTIMATE_NOTE}")
    else:
        context_lines.append("Cycle phase: not applicable / not tracked for this user.")
    if notes:
        context_lines.append(f"User notes: {notes}")
    if pattern_note:
        context_lines.append(f"Observed personal pattern: {pattern_note}")
    if amenorrhea_referral:
        context_lines.append(
            "IMPORTANT: user hasn't logged a period in 90+ days. Suppress the normal training "
            "recommendation this session and instead surface the RED-S referral message from "
            "the SAFETY-REFERRAL evidence, warmly and without alarm."
        )

    user_prompt = "\n".join(
        [
            *context_lines,
            "",
            "Tone exemplars (match this voice, do not copy verbatim):",
            *[f"- {m}" for m in tone_examples],
            "",
            "Retrieved evidence (only source of truth for any claim):",
            _format_evidence(chunks),
        ]
    )

    return ContextBundle(
        system_prompt=SYSTEM_PROMPT_HEADER,
        user_prompt=user_prompt,
        cited_source_ids=cited_source_ids,
        phase=phase,
        amenorrhea_referral=amenorrhea_referral,
        pattern_note=pattern_note,
    )
