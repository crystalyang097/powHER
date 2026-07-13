"""Anthropic client + grounded generation, with a hard guardrail layer.

If generation fails, or any guardrail rejects the output, the app falls
back to the curated message bank rather than shipping an ungrounded or
off-tone response.
"""

import os
import re
from dataclasses import dataclass

import anthropic
from dotenv import load_dotenv

from powher.context_builder import ContextBundle
from powher.guardrails import GuardrailResult, run_all_guardrails
from powher.messages import get_fallback_message
from powher.models import EnergyTag, Phase

load_dotenv()

MODEL = "claude-opus-4-6"

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def extract_text(response) -> str:
    """Robustly extract text from a response, ignoring thinking/tool_use blocks.
    Never index content[0] -- filter by type instead."""
    return "".join(block.text for block in response.content if block.type == "text")


@dataclass
class GenerationResult:
    recommendation: str
    message: str
    source_ids: set[str]
    used_fallback: bool
    fallback_reason: str = ""


_LABEL = r"\**\s*{}\s*:\**"  # tolerate markdown bold around labels, e.g. **RECOMMENDATION:**


def _strip_sources_line(text: str) -> str:
    return re.split(r"\n\**\s*Sources?:", text, flags=re.IGNORECASE)[0].strip()


def _split_recommendation_and_message(text: str) -> tuple[str, str]:
    rec_pat = _LABEL.format("RECOMMENDATION")
    msg_pat = _LABEL.format("MESSAGE")
    rec_match = re.search(rf"{rec_pat}\s*(.+?)(?=\n{msg_pat}|\Z)", text, re.IGNORECASE | re.DOTALL)
    msg_match = re.search(rf"{msg_pat}\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    recommendation = rec_match.group(1).strip() if rec_match else text.strip()
    message = msg_match.group(1).strip() if msg_match else ""
    recommendation = _strip_sources_line(recommendation)
    message = _strip_sources_line(message)
    return recommendation, message


def generate(
    context: ContextBundle,
    energy_tags: list[EnergyTag],
    last_logged_weight: float | None = None,
    proposed_weight: float | None = None,
) -> GenerationResult:
    try:
        response = get_client().messages.create(
            model=MODEL,
            max_tokens=512,
            system=context.system_prompt,
            messages=[{"role": "user", "content": context.user_prompt}],
        )
        text = extract_text(response)
    except Exception as exc:  # noqa: BLE001 -- any API failure falls back
        return _fallback(context, energy_tags, reason=f"Generation error: {exc}")

    if not text.strip():
        return _fallback(context, energy_tags, reason="Empty generation.")

    results: list[GuardrailResult] = run_all_guardrails(
        text,
        cited_source_ids=context.cited_source_ids,
        energy_tags=energy_tags,
        last_logged_weight=last_logged_weight,
        proposed_weight=proposed_weight,
    )
    failures = [r for r in results if not r.passed]
    if failures:
        reason = "; ".join(r.reason for r in failures)
        return _fallback(context, energy_tags, reason=reason)

    recommendation, message = _split_recommendation_and_message(text)
    if not message:
        message = get_fallback_message(energy_tags[0], context.phase)

    return GenerationResult(
        recommendation=recommendation,
        message=message,
        source_ids=context.cited_source_ids,
        used_fallback=False,
    )


def _fallback(context: ContextBundle, energy_tags: list[EnergyTag], reason: str) -> GenerationResult:
    tag = energy_tags[0] if energy_tags else EnergyTag.NORMAL
    message = get_fallback_message(tag, context.phase)
    if EnergyTag.IN_PAIN in energy_tags:
        recommendation = (
            "Let's skip prescribing weights today. Gentle movement or rest are both good "
            "options -- follow what your body's telling you."
        )
    else:
        recommendation = (
            "We couldn't generate a fully grounded recommendation this time, so here's a safe "
            "default: hold at your last logged weights and let today's energy guide volume."
        )
    return GenerationResult(
        recommendation=recommendation,
        message=message,
        source_ids=context.cited_source_ids,
        used_fallback=True,
        fallback_reason=reason,
    )
