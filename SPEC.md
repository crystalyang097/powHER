# powHER — Build Spec / Claude Code Prompt

> **How to use this:** Save this file to your repo root as `SPEC.md`, then in Claude Code run:
> `Read SPEC.md and build the project exactly as described. Start with the corpus documents and README, then the retrieval layer, then the app. Ask me before installing anything not listed in the stack.`

---

## 0. Context for the model

You are helping build **powHER**, a cycle-aware fitness web app for women. This is a student project (JHU AI Developer Guide, MCP / Context-Aware AI Interface category) built by a CS student learning agent engineering. Time budget for v1 is roughly 10 hours, so favor a working end-to-end slice over completeness.

**The single most important design principle:** powHER is **symptom-responsive and phase-aware**, NOT phase-prescriptive. The scientific evidence does not support prescribing specific load reductions based on cycle phase. Recommendations adjust off the user's **self-reported energy tag**, not off her phase. Phase provides *context, education, and long-term pattern detection only*. Never generate a recommendation that says "you are in X phase, therefore lift Y% less."

**Tone principle:** Every message must leave the user feeling capable, not limited. Never imply her period is holding her back or costing her progress. Gentle, warm, encouraging — Pinterest inspirational quote energy, not drill sergeant.

---

## 1. Tech stack (do not add to this without asking)

- **Python 3.11+**, managed with `uv`
- **Streamlit** — UI (already chosen for speed; it is a web app, not native)
- **Anthropic Python SDK** (`anthropic`) — LLM calls, model `claude-opus-4-6`
- **`python-dotenv`** — API key from `.env` (never hardcode; `.env` in `.gitignore`)
- **ChromaDB** (or FAISS if simpler) — local vector store for RAG
- **`sentence-transformers`** — local embeddings, so no second API bill
- **SQLite** — local profile + workout history
- **`cryptography`** (Fernet) — encrypt cycle data at rest

---

## 2. Architecture

```
User (Streamlit UI)
   │
   ├─ Home  ──────────► main menu: Today's Workout | History | Cycle & Learn
   │
   ├─ Today's Workout ─► log exercises/weights/reps
   │                     + energy tag  ──┐
   │                                      │
   ├─ History ─────────► trends + pattern detection
   │                                      │
   └─ Cycle & Learn ───► cycle input + phase education
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │   Context Builder     │  ← the heart of the app
                              │  assembles: phase,    │
                              │  energy tag, goal,    │
                              │  recent history,      │
                              │  retrieved evidence   │
                              └───────────┬───────────┘
                                          │
                     ┌────────────────────┴──────────────────┐
                     ▼                                       ▼
          ┌─────────────────────┐              ┌──────────────────────┐
          │  RAG Retriever      │              │  Message Bank        │
          │  (Chroma + corpus)  │              │  (curated fallback)  │
          │  returns cited      │              │                      │
          │  evidence chunks    │              └──────────┬───────────┘
          └──────────┬──────────┘                         │
                     └──────────────┬────────────────────┘
                                    ▼
                        ┌───────────────────────┐
                        │   Claude (Anthropic)  │
                        │  grounded generation  │
                        │  + supportive message │
                        └───────────┬───────────┘
                                    ▼
                            Guardrail layer
                        (bounds + safety triggers)
                                    ▼
                            Recommendation + citation
```

**Critical rule for the LLM layer:** Claude may only make fitness/health claims that appear in retrieved corpus chunks. If no chunk supports a claim, it must not make it. Every recommendation surfaces its source. If retrieval returns nothing relevant, fall back to the message bank and a generic-but-safe recommendation.

---

## 3. File structure

```
powher/
├── .env                       # ANTHROPIC_API_KEY (gitignored)
├── .gitignore
├── pyproject.toml
├── README.md                  # Responsible-AI README — see §8
├── SPEC.md                    # this file
├── app.py                     # Streamlit entry point
├── powher/
│   ├── __init__.py
│   ├── cycle.py               # phase calculation
│   ├── context_builder.py     # assembles context → system prompt
│   ├── retriever.py           # RAG: embed corpus, query, return cited chunks
│   ├── agent.py               # Anthropic client + extract_text() + generation
│   ├── messages.py            # curated message bank
│   ├── guardrails.py          # bounds + safety triggers
│   ├── storage.py             # SQLite + Fernet encryption
│   └── models.py              # dataclasses: Profile, Workout, EnergyTag, Phase
├── corpus/                    # the RAG knowledge base — see §7
│   ├── 01_phase_evidence.md
│   ├── 02_exercise_and_pain.md
│   ├── 03_training_principles.md
│   ├── 04_phase_education.md
│   ├── 05_safety_and_referral.md
│   └── SOURCES.md
└── tests/
    └── test_cycle.py
```

---

## 4. Data model

```python
Profile:
    user_id: str
    display_name: str
    goal: Literal["strength", "hypertrophy", "endurance", "general_fitness", "fat_loss"]
    cycle_length: int            # default 28
    last_period_start: date      # ENCRYPTED at rest
    cycle_applicable: bool       # False if user selected the "may not apply" option
    created_at: datetime

WorkoutEntry:
    entry_id, user_id, date
    exercises: list[Exercise]    # name, weight, reps, sets — user types these in
    energy_tag: EnergyTag
    cycle_day: int | None        # derived, ENCRYPTED
    phase: Phase | None          # derived, ENCRYPTED
    notes: str

EnergyTag (fixed set — user picks one or more):
    ENERGIZED | NORMAL | TIRED | DRAINED | IN_PAIN | CRAMPING | FASTER_FATIGUE

Phase (derived, for context/education only — NOT for prescribing load):
    MENSTRUAL | FOLLICULAR | OVULATORY | LUTEAL
```

**No height/weight fields. No goal-weight field. No calorie tracking.** (See §9.)

**Baseline strength:** user enters her own working weights in session one. From session two on, the app suggests based on her logged history. No estimation from body metrics.

---

## 5. Cycle phase calculation (`cycle.py`)

Simple, honest date math from `last_period_start` + `cycle_length`:

- **Menstrual:** days 1–5
- **Follicular:** days 6 → (cycle_length − 14 − 1)
- **Ovulatory:** the ~3 days around (cycle_length − 14)
- **Luteal:** from ovulation → end of cycle

Every phase display must be labeled as an **estimate**. Include a visible note: *"This is estimated from your dates — bodies aren't calendars, and that's normal."*

**The "may not apply" path.** Add a clearly visible option on the Cycle tab:

> **"This might not apply to me right now."**
> *For irregular cycles, hormonal birth control, perimenopause, or if you're not currently cycling — phase estimates won't be accurate for you, and we don't want to guess. We're actively working on finding accurate, well-researched guidance for these situations, and we want to build for you properly rather than quickly. In the meantime, everything else in powHER still works: log your workouts, tag your energy, and get recommendations based on how you're actually feeling.*

If `cycle_applicable = False`: hide phase context entirely, skip retrieval of phase chunks, and drive recommendations purely off energy tag + history. **The app must remain fully functional in this mode.**

---

## 6. The recommendation logic

**Inputs:** energy tag (primary), goal, recent workout history, phase (context only).

**Load adjustment is driven by the ENERGY TAG:**

| Energy tag | Adjustment |
|---|---|
| ENERGIZED | Suggest progressing — small increase if history supports it |
| NORMAL | Hold steady at logged working weights |
| TIRED / FASTER_FATIGUE | Suggest reducing reps-in-reserve pressure; keep load, cut volume, or lighten — user's choice, framed as smart, not lesser |
| DRAINED | Suggest a lighter session or active recovery; explicitly say rest is training |
| CRAMPING | Note that exercise is evidence-backed for reducing menstrual pain (cite corpus); offer both a lighter option and a normal option; never push |
| IN_PAIN | Do NOT prescribe load. Offer gentle movement or rest, and if pain is severe/recurring, suggest talking to a doctor. |

**Goal shapes rep/set structure** (grounded in the 2026 ACSM Position Stand chunk in corpus):
- strength → heavier loads, 2–3 sets, key lifts early, ≥2×/week
- hypertrophy → higher weekly volume (≥10 sets/muscle/week)
- endurance / general → moderate loads, higher reps
- fat_loss → frame as *training composition*, never restriction (see §9)

**Pattern learning (the "history" feature):** after ≥2 logged cycles, if a user consistently tags a given cycle-day-range a certain way, surface it gently and *personally*:

> *"Heads up — around this point in your last two cycles you tagged 'tired.' That's your pattern, not a rule. You might feel completely different today. How are you feeling?"*

Always framed as **her observed pattern**, never as a scientific claim about women in general.

---

## 7. Corpus documents — WRITE THESE FIRST

Create each file in `corpus/` with the content below. Chunk on `##` headers when embedding. Attach source metadata to every chunk so citations can be surfaced in the UI.

### `corpus/01_phase_evidence.md`

Content must convey, accurately:

- The largest meta-analysis (McNulty et al., 2020, *Sports Medicine*, 78 studies) found exercise performance may be **trivially** reduced in the early follicular phase versus all other phases; performance was consistent between all other phases. Effect size was trivial, between-study variation large, and evidence quality rated **low**. The authors explicitly concluded that **general guidelines across the cycle cannot be formed** and that a **personalised approach** based on each individual's own response is what's warranted.
- An umbrella review of resistance-training evidence (Colenso-Semple, D'Souza, Elliott-Sale & Phillips, 2023, *Frontiers in Sports and Active Living*) found highly variable findings, poor and inconsistent methodology across the literature, and concluded it is **premature** to say cycle-phase hormone fluctuations appreciably affect acute performance or long-term strength/hypertrophy adaptations.
- A 2024 systematic review + meta-analysis on maximal strength (Niering et al., *Sports*; 22 studies, 433 women) found **heterogeneous** results.
- **The takeaway chunk (must be present verbatim in spirit):** *"There is no credible evidence base for prescribing a specific percentage load reduction based on menstrual cycle phase. Any app or coach doing so is inventing the number. What the evidence does support is listening to how you actually feel on a given day."*

### `corpus/02_exercise_and_pain.md`

- Cochrane review (2019, CD004142): exercise performed ~45–60 minutes, three or more times per week, **regardless of intensity**, may produce a clinically significant reduction in menstrual pain — roughly 25mm on a 100mm scale, over twice the minimum change women would notice.
- 2024 network meta-analysis (49 RCTs, 3,129 participants, *BMC Women's Health*): all exercise interventions significantly reduced menstrual pain; resistance exercise and multi-component exercise showed statistically significant reductions in pain intensity.
- 2024 network meta-analysis (29 RCTs, 1,808 participants, *Sports Medicine – Open*): all exercise types were effective at 8 weeks.
- **Framing chunk:** movement is not something to push through *despite* your period — it is evidence-backed *for* period pain. This is a green light, not a concession.

### `corpus/03_training_principles.md`

Grounded in the **2026 ACSM Position Stand** (*Resistance Training Prescription for Muscle Function, Hypertrophy, and Physical Performance in Healthy Adults*, an overview of 137 systematic reviews, >30,000 participants):

- **Strength:** loads ≥80% 1RM, full range of motion, 2–3 sets, key lifts early in the session, ≥2 sessions/week.
- **Hypertrophy:** higher weekly volume (≥10 sets per muscle group per week), eccentric overload.
- **Power:** moderate loads (30–70% 1RM), fast concentric phase.
- **Training to absolute failure is NOT necessary.** Sufficient effort is achievable near failure — roughly 2–3 reps in reserve.
- Non-traditional training (bands, bodyweight, home-based) produces marked benefits.
- The largest gains come from moving from *no* resistance training to *any* resistance training.

> The "you don't need to train to failure" and "any training beats no training" findings are **tone gold** — they are the evidence base for powHER's entire gentleness thesis. Surface them often.

### `corpus/04_phase_education.md`

Plain-language education, one chunk per phase, each with an honest evidence caveat. Include the documented knowledge gap as motivation: one survey found **70.1%** of recreational female athletes were not knowledgeable about their cycle phases and **55.5%** did not know which hormones are involved (*MDPI*, 2023).

Also include symptom-prevalence context:
- Across 1,086 athletes in 57 sports, dysmenorrhea and PMS were the most common symptoms and were *perceived* to negatively affect aerobic fitness, muscle strength, mental sharpness, balance, and sleep (*Frontiers in Physiology*, 2022).
- 71–83% of female athletes experience dysmenorrhea.
- A 2025 daily-monitoring study (108 elite athletes, 554 cycles) found symptoms clustered around menstruation and the pre-bleeding phase and correlated with reduced well-being — **and that performance declined on symptomatic days, not on phase days.** This is the empirical backbone of powHER's symptom-first design; make the distinction explicit in this chunk.

Each phase chunk must end with a variant of: *"Some women notice this. Many notice nothing. Both are completely normal."*

### `corpus/05_safety_and_referral.md`

Non-negotiable safety content, sourced to the **IOC Consensus Statement on Relative Energy Deficiency in Sport (REDs)** (2014, updated 2018 and 2023):

- Missing periods are not a neutral event. **Secondary amenorrhea (>6 months) or primary amenorrhea (>16 years)** is one of the flags that should trigger clinical assessment under the IOC's RED-S framework.
- Other early signs of low energy availability: recurrent stress fractures, unusual susceptibility to infection, hormonal imbalance, a mismatch between training effort and performance progress, and marked mood change.
- REDs affects athletes of any level, not just elites.
- Women are at particular risk for distorted body image and disordered eating; athletes with functional hypothalamic amenorrhea show lower stress tolerance and more depressive traits.

**Referral text (use warm, non-alarming language):**
> *"You haven't logged a period in a while. That's really common and usually very treatable — but it's worth mentioning to a doctor, because it can be your body's way of saying it needs more fuel or more rest. Nothing about this means you've done anything wrong."*

### `corpus/SOURCES.md`

Full citation list with links. Every corpus chunk carries a source ID that maps back to an entry here. Recruiters and graders will read this file — make it clean.

---

## 8. README.md — Responsible-AI README

Must contain all of the following (this is a graded deliverable per the JHU guide):

1. **Summary** — what powHER is, who it's for, in 3 sentences.
2. **The design decision that defines the app** — symptom-responsive, not phase-prescriptive. Explain *why*, citing the evidence. This is the intellectual centerpiece of the project; write it well.
3. **Models & services** — Anthropic `claude-opus-4-6` for generation; local `sentence-transformers` for embeddings; ChromaDB vector store; Streamlit UI; SQLite storage.
4. **Intended scope** — recreational women lifters who already have a routine and want cycle-aware support and a supportive voice.
5. **Explicitly out of scope** — medical advice; diagnosis; treatment of dysmenorrhea, PCOS, endometriosis, or amenorrhea; nutrition/calorie guidance; weight-loss coaching; contraception guidance; use by minors; use by pregnant or postpartum users; exercise programming for users with injuries.
6. **Known limitations** — phase estimates are calendar math, not measurement; the underlying research on cycle-phase performance effects is of low quality and mixed; the app currently does not serve users on hormonal contraception, with irregular cycles, or in perimenopause, and says so honestly rather than guessing.
7. **Model card** — intended use, what grounds the outputs (the corpus), primary risks, how success is evaluated.
8. **Guardrails / safety controls** — see §9.
9. **Evaluation checklist / seed tests** — see §10.
10. **Ops notes** — API cost per session, key rotation, `.env` handling, telemetry.
11. **Privacy** — cycle data is health data. Encrypted at rest with Fernet. Local-only storage in v1. User can delete all data with one button.
12. **Security roadmap (state this plainly):** *"v1 uses a lightweight local profile with no authentication, chosen deliberately for a time-constrained build. This is NOT adequate for health data in production. Real authentication (hashed credentials, session management, encrypted-at-rest server-side storage, and a documented data-deletion path) is required before this app is deployed for real users, and is the top item on the roadmap."*
13. **Roadmap** — real auth; Apple Health / HealthKit sync; native iOS app; exercise library; expanded corpus covering hormonal contraception and perimenopause.

---

## 9. Guardrails (`guardrails.py`) — implement as hard code, not prompt instructions

| Guardrail | Rule |
|---|---|
| **Load bounds** | Never suggest an increase >10% over the user's last logged weight for that lift. Never suggest a decrease framed as a deficit. |
| **No unsourced claims** | If a health/fitness claim isn't supported by a retrieved chunk, it doesn't ship. Post-generation check. |
| **No phase-prescribed load** | Reject/regenerate any output that ties a load number to a phase rather than to an energy tag. |
| **Amenorrhea trigger** | No period logged for 90+ days → surface the RED-S referral message. Suppress normal recommendations that session. |
| **Pain trigger** | `IN_PAIN` tag → no load prescription. Severe or repeated (3+ consecutive cycles) → gentle doctor suggestion. |
| **Disordered-eating guard** | No calorie tracking, no goal-weight, no body-composition estimates, no "compensate for" language, no streak-shaming. `fat_loss` goal is framed purely as training composition. |
| **Minors** | Out of scope; state in README. |
| **Tone check** | Reject any message implying the user is weaker, behind, losing progress, or that her period is an obstacle. |

---

## 10. Evaluation / seed tests

- **Grounding:** for 10 sample states (phase × energy tag), assert every health claim in the output maps to a retrieved chunk.
- **Hallucination spot-check:** prompt the agent with "what percent should I reduce my squat in luteal phase?" → it must **decline to give a number** and explain why.
- **Guardrail tests:** amenorrhea trigger fires at 90 days; `IN_PAIN` produces no load prescription; >10% increase is blocked.
- **Tone tests:** assert absence of a banned-phrase list ("behind," "excuse," "push through," "make up for," "lost progress," "despite your period").
- **`cycle_applicable = False` path:** app fully functional, no phase context leaks into prompts.
- **Known failure cases:** document them honestly in the README.

---

## 11. Message bank (`messages.py`)

Curated messages, keyed by `(energy_tag, phase | None)`, used as **fallback** and as **tone exemplars** injected into the system prompt so Claude's generated messages match the voice.

Voice: gentle, warm, second-person, short. Never clinical, never hype, never "girlboss."

Examples to seed with:
- *"You showed up. That's the part most people skip."*
- *"Give yourself a little grace today. Your body is doing so much."*
- *"Lighter today isn't smaller. It's smart."*
- *"Rest is training. It's where the strength actually gets built."*
- *"Your body isn't working against you. It's working."*

Claude personalizes off these; if generation fails or a guardrail rejects the output, the bank is served directly.

---

## 12. UI (Streamlit)

**Home** — a soft landing page with the phase card (if applicable), today's supportive message, and a main menu with three destinations:
1. **Today's Workout** — type in exercises, weights, reps; pick an energy tag; get the recommendation + message + source citation.
2. **History** — logged sessions, weight trends over time, energy-tag patterns mapped against cycle days.
3. **Cycle & Learn** — cycle input (last period date, typical length, the "may not apply to me" option) **and** the phase education content, in one tab.

**Visual direction:**
- **Font:** rounded sans — Nunito or Quicksand. Soft, friendly, never harsh.
- **Palette:** light background by default. Soft dusty rose, lavender, sage, warm cream. No aggressive reds, no black-and-neon gym aesthetic.
- **Dark mode toggle** for accessibility, with the same softness (deep plum/charcoal, not pure black).
- **Message display:** generous whitespace, larger type, centered — treat the supportive message like a quote card, not a notification.
- Meet WCAG AA contrast in both modes.

---

## 13. Build order (respect this)

1. `corpus/` documents + `SOURCES.md` — **the evidence comes first, everything else grounds in it**
2. `README.md` — write it now, while the reasoning is fresh; do not defer it
3. `models.py`, `cycle.py`, `storage.py` (+ encryption)
4. `retriever.py` — embed corpus, verify retrieval returns sensible cited chunks
5. `messages.py`, `guardrails.py`
6. `context_builder.py` + `agent.py` (include a robust `extract_text(response) -> str` that filters blocks by `type == "text"` — do not index `content[0]`)
7. `app.py` — Streamlit UI last
8. `tests/`

Ship a working vertical slice before polishing anything.
