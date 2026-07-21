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
    (EnergyTag.MUSCLE_FATIGUE, None): [
        "Your body's telling you something useful — listening is the strong move.",
        "Cutting a set short today isn't quitting. It's paying attention.",
    ],
    (EnergyTag.MOTIVATED, None): [
        "That drive is yours — spend it on something that feels good to finish.",
        "Motivated days are gifts. Enjoy this one, no strings attached.",
    ],
    (EnergyTag.SLEPT_POORLY, None): [
        "Short on sleep is a real thing, not a character flaw. Scale today to match.",
        "A gentler session on a tired brain still counts — showing up is the win.",
    ],
    (EnergyTag.BRAIN_FOG, None): [
        "Foggy days are for familiar movements — let your body run the patterns it knows.",
        "You don't need to be sharp to be strong. Keep it simple today.",
    ],
    (EnergyTag.BLOATED, None): [
        "Bloating is water and hormones doing their thing — it changes nothing about your strength.",
        "Comfort first today: looser positions, gentler core work, zero apologies.",
    ],
    (EnergyTag.BREAST_TENDERNESS, None): [
        "Tenderness is common and real — swap or soften anything that aggravates it.",
        "Adjusting around a sore chest is smart training, not a smaller workout.",
    ],
    (EnergyTag.SORENESS, None): [
        "Soreness means you did something. Easy movement today helps it settle.",
        "A lighter day on sore muscles is part of the plan, not a pause in it.",
    ],
    (EnergyTag.DIZZY, None): [
        "Dizzy days deserve extra care — stay grounded, sip water, and skip anything that feels risky.",
        "If the room's spinning even a little, gentleness is the only assignment today.",
    ],
    (EnergyTag.HEAVY_FLOW, None): [
        "Heavy days ask a lot of your body. Whatever feels comfortable is exactly enough.",
        "Choose comfort first today — your strength isn't going anywhere.",
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
    (EnergyTag.HEADACHE, None): [
        "A sore head is a real reason to keep things easy today. Lighter still counts.",
        "Listen to that ache — gentle or short is a smart call, not a lesser one.",
    ],
    (EnergyTag.HOT_FLASHES, None): [
        "Take it at your own temperature today — breaks and water are part of training too.",
        "However your body's running its thermostat today, meeting it where it is is the win.",
    ],
    (EnergyTag.LOWER_BACK_PAIN, None): [
        "Be gentle with your back today. If something aggravates it, that's your cue to ease off.",
        "A tender back deserves care, not a test. Move in the ranges that feel safe.",
    ],
    (EnergyTag.NAUSEA, None): [
        "Feeling queasy is a fair reason to go slow or rest. Both are completely okay.",
        "Your body's asking for gentleness today — that's worth honoring.",
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
