"""Curated message bank.

Used two ways:
1. As fallback when generation fails or a guardrail rejects the model's output.
2. As tone exemplars injected into the system prompt so Claude's generated
   messages match this voice.

Voice: gentle, warm, second-person, short. Never clinical, never hype,
never "girlboss". Every message should leave the reader feeling capable,
not limited.
"""

from powher.models import EnergyTag, Phase

MessageBank = dict[tuple[EnergyTag, Phase | None], list[str]]

MESSAGE_BANK: MessageBank = {
    (EnergyTag.ENERGIZED, None): [
        "You showed up. That's the part most people skip.",
        "That energy is real — let's put it somewhere good today.",
        "Some days the tank is full. Enjoy this one.",
    ],
    (EnergyTag.NORMAL, None): [
        "A steady day is still a strong day.",
        "You don't need a big feeling to have a good session.",
        "Consistent is its own kind of impressive.",
    ],
    (EnergyTag.TIRED, None): [
        "Lighter today isn't smaller. It's smart.",
        "Give yourself a little grace today. Your body is doing so much.",
        "Tired isn't the opposite of strong. It's just today's weather.",
    ],
    (EnergyTag.FASTER_FATIGUE, None): [
        "Your body's telling you something useful — listening is the strong move.",
        "Cutting a set short today isn't quitting. It's paying attention.",
    ],
    (EnergyTag.DRAINED, None): [
        "Rest is training. It's where the strength actually gets built.",
        "Some days the best rep is the one you don't take. That's allowed.",
        "Showing up to rest on purpose still counts as showing up.",
    ],
    (EnergyTag.CRAMPING, None): [
        "Movement can genuinely help with this — no pressure either way.",
        "Your body isn't working against you. It's working.",
        "Whatever you choose today, both options are the right one.",
    ],
    (EnergyTag.IN_PAIN, None): [
        "Today isn't about pushing. Gentle movement or rest are both wins.",
        "Pain is information, not a test you're failing.",
        "Be as kind to yourself today as you'd be to a friend feeling this.",
    ],
}

GENERIC_FALLBACK = "You showed up today. That already matters."


def get_messages(energy_tag: EnergyTag, phase: Phase | None = None) -> list[str]:
    if (energy_tag, phase) in MESSAGE_BANK:
        return MESSAGE_BANK[(energy_tag, phase)]
    return MESSAGE_BANK.get((energy_tag, None), [GENERIC_FALLBACK])


def get_fallback_message(energy_tag: EnergyTag, phase: Phase | None = None) -> str:
    messages = get_messages(energy_tag, phase)
    return messages[0] if messages else GENERIC_FALLBACK
