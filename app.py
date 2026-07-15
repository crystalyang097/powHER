"""powHER — Streamlit entry point."""

import uuid
from datetime import date, datetime

import streamlit as st
import streamlit.components.v1 as components

from powher import storage
from powher.agent import generate
from powher.context_builder import build_context
from powher.cycle import (
    ESTIMATE_NOTE,
    amenorrhea_flag,
    cycle_day as compute_cycle_day,
    phase_for_date,
)
from powher.models import (
    EnergyTag,
    Exercise,
    PeriodEvent,
    Phase,
    Profile,
    Routine,
    RoutineExercise,
    SetType,
    WorkoutEntry,
    WorkoutSet,
    normalize_exercise_name,
)

CYCLE_LENGTH_HELP = (
    "Count from the first day of one period to the first day of your next period "
    "— that whole span is your cycle length. Most fall around 28 days, but anywhere "
    "from 21 to 35 is common."
)

USER_ID = "local_user"
GOALS = ["strength", "hypertrophy", "endurance", "general_fitness", "fat_loss"]
GOAL_LABELS = {
    "strength": "Strength",
    "hypertrophy": "Hypertrophy",
    "endurance": "Endurance",
    "general_fitness": "General fitness",
    "fat_loss": "Training composition (fat loss)",
}
ENERGY_LABELS = {
    EnergyTag.ENERGIZED: "⚡ Energized",
    EnergyTag.NORMAL: "🙂 Normal",
    EnergyTag.TIRED: "😮‍💨 Tired",
    EnergyTag.DRAINED: "🔋 Drained",
    EnergyTag.FASTER_FATIGUE: "🌀 Fatiguing faster than usual",
    EnergyTag.CRAMPING: "〰️ Cramping",
    EnergyTag.IN_PAIN: "⚠️ In pain",
    EnergyTag.HEADACHE: "🤕 Headache",
    EnergyTag.HOT_FLASHES: "🥵 Hot flashes",
    EnergyTag.LOWER_BACK_PAIN: "🦴 Lower back pain",
    EnergyTag.NAUSEA: "🤢 Nausea",
}
PHASE_BLURBS = {
    Phase.MENSTRUAL: "Bleeding phase. Some feel low-energy here, some don't — both are normal. Movement is evidence-backed for easing period pain, not something to avoid.",
    Phase.FOLLICULAR: "Estrogen is rising as your body preps to ovulate. Some report more energy here; the evidence for a consistent boost is weak, so there's no rule to expect it.",
    Phase.OVULATORY: "The few days around mid-cycle. Some feel a short burst of energy, others notice nothing distinct.",
    Phase.LUTEAL: "Progesterone rises, then both hormones drop before your next period — PMS symptoms are most commonly reported in this window.",
}
PHASE_NORMAL_LINE = "Some women notice this. Many notice nothing. Both are completely normal."
# Longer, hormone-focused education for the Cycle & Learn tab. Deliberately uses
# "can"/"may"/"some" throughout — describing what hormones *can* do, never a rule.
PHASE_EDUCATION = {
    Phase.MENSTRUAL: (
        "Your period, roughly days 1–5. Estrogen and progesterone are both at their lowest, "
        "and that drop is what signals the uterine lining to shed. Prostaglandins — the compounds "
        "that make the uterus contract — can drive cramping, and some women notice lower energy, "
        "heavier legs, or disrupted sleep in this window. Others feel completely normal. Gentle "
        "movement is well-evidenced for easing period pain, so it's a green light here, not "
        "something to avoid or push through."
    ),
    Phase.FOLLICULAR: (
        "From the end of your period up to ovulation. A follicle matures and estrogen climbs "
        "steadily. Rising estrogen is often described as energizing and mood-lifting, and some "
        "women report feeling strong or motivated — but the research on a real, consistent "
        "performance boost is weak and mixed, so there's no rule that says you'll feel it. If you "
        "do, enjoy it; if you don't, that's just as normal."
    ),
    Phase.OVULATORY: (
        "The few days around mid-cycle. A surge in luteinizing hormone (LH) triggers the ovary to "
        "release an egg, and estrogen peaks just before. Some women feel a short lift in energy, "
        "drive, or confidence around this peak; others notice nothing distinct, and a few feel a "
        "mild one-sided twinge as the egg releases (called mittelschmerz)."
    ),
    Phase.LUTEAL: (
        "After ovulation until your next period. Progesterone rises to prepare the body for a "
        "possible pregnancy, and can nudge your resting temperature up slightly and leave you "
        "feeling warmer or more tired. If there's no pregnancy, both estrogen and progesterone "
        "fall sharply just before bleeding — the premenstrual drop when PMS symptoms are most "
        "commonly reported: mood shifts, bloating, breast tenderness, or a session feeling harder "
        "than the numbers suggest. Many women move through this window feeling completely fine."
    ),
}
# Encouragement stays conditional on how she actually feels — never "you're in
# X phase, so do Y". Phase gives context; the body gets the final say.
PHASE_ENCOURAGEMENT = {
    Phase.MENSTRUAL: "However today feels, gentle movement can genuinely ease the aches — and rest is just as valid. You get to choose.",
    Phase.FOLLICULAR: "If you're feeling good, give yourself a little push today — you'd be surprised what your body can do.",
    Phase.OVULATORY: "If there's a little extra in the tank today, enjoy spending it. And if there isn't, steady is still strong.",
    Phase.LUTEAL: "Some feel a dip before their period, some don't — however today lands, you get to meet it your way. You've got this.",
}
GENERAL_ENCOURAGEMENT = "However you're feeling today, showing up is the part that counts. Meet yourself where you are."

st.set_page_config(page_title="powHER", page_icon="🌸", layout="centered")


def inject_css():
    dark = st.session_state.get("dark_mode", False)
    if dark:
        bg, card, text, accent, accent2 = "#2b2338", "#3a3048", "#f2ebe4", "#c9a7c9", "#a9c9b8"
        cream = "#352b43"
    else:
        bg, card, text, accent, accent2 = "#fdf8f3", "#ffffff", "#3d3241", "#d8a7b1", "#a9c9b8"
        cream = "#f7ecdd"
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');
        html, body, [class*="css"] {{ font-family: 'Nunito', sans-serif; }}
        .stApp {{ background-color: {bg}; color: {text}; }}
        .powher-card {{
            background-color: {card};
            border-radius: 20px;
            padding: 2rem;
            text-align: center;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
            margin-bottom: 1.5rem;
        }}
        .powher-quote {{
            font-size: 1.4rem;
            font-weight: 700;
            color: {text};
            line-height: 1.5;
        }}
        .powher-badge {{
            display: inline-block;
            background-color: {accent};
            color: {text};
            border-radius: 999px;
            padding: 0.25rem 0.9rem;
            font-weight: 600;
            font-size: 0.85rem;
            margin: 0.2rem;
        }}
        .powher-badge-alt {{ background-color: {accent2}; }}
        .powher-note {{ font-size: 0.85rem; opacity: 0.75; font-style: italic; }}
        .powher-keepinmind {{
            font-weight: 700;
            color: {text};
            font-size: 0.8rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.7;
            margin-top: 1.4rem;
            margin-bottom: 0.3rem;
        }}
        .powher-edu {{ font-size: 1rem; color: {text}; line-height: 1.6; margin: 0.3rem auto; max-width: 90%; }}
        .powher-phase {{
            background-color: {cream};
            border-radius: 18px;
            padding: 1.2rem 1.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 1px 6px rgba(0,0,0,0.05);
        }}
        .powher-phase h4 {{ margin: 0 0 0.4rem 0; color: {text}; font-weight: 800; font-size: 1.15rem; }}
        .powher-phase p {{ margin: 0; color: {text}; line-height: 1.65; }}
        div.stButton > button {{
            border-radius: 14px;
            font-weight: 700;
            padding: 0.6rem 1rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def ensure_profile_loaded():
    storage.init_db()
    if "profile" not in st.session_state:
        st.session_state.profile = storage.get_profile(USER_ID)


def render_onboarding():
    st.markdown("<div class='powher-card'><span class='powher-quote'>Welcome to powHER 🌸</span></div>", unsafe_allow_html=True)
    st.write("Let's set up your profile. This only takes a moment.")
    st.caption("Fields marked with :red[*] are required.")
    with st.form("onboarding"):
        display_name = st.text_input("What should we call you? :red[*]", value="")
        goal = st.selectbox(
            "Primary training goal :red[*]",
            GOALS,
            index=None,
            placeholder="Choose your goal",
            format_func=lambda g: GOAL_LABELS[g],
        )
        cycle_applicable = not st.checkbox("This might not apply to me right now")
        if not cycle_applicable:
            st.info(
                "For irregular cycles, hormonal birth control, perimenopause, or if you're not "
                "currently cycling — phase estimates won't be accurate for you, and we don't "
                "want to guess. We're actively working on finding accurate, well-researched "
                "guidance for these situations, and we want to build for you properly rather "
                "than quickly. In the meantime, everything else in powHER still works: log your "
                "workouts, tag your energy, and get recommendations based on how you're actually "
                "feeling."
            )
        last_period_start = None
        cycle_length = 28
        if cycle_applicable:
            last_period_start = st.date_input(
                "First day of your last period :red[*]", value=None, max_value=date.today()
            )
            cycle_length = st.number_input(
                "Typical cycle length (days) :red[*]", min_value=15, max_value=45, value=28,
                help=CYCLE_LENGTH_HELP,
            )
        submitted = st.form_submit_button("Get started")
        if submitted:
            missing = []
            if not display_name.strip():
                missing.append("your name")
            if goal is None:
                missing.append("a training goal")
            if cycle_applicable and last_period_start is None:
                missing.append("the first day of your last period")
            if missing:
                st.error(f"Almost there — we still need {', '.join(missing)}.")
                return
            profile = Profile(
                user_id=USER_ID,
                display_name=display_name.strip(),
                goal=goal,
                last_period_start=last_period_start,
                cycle_length=int(cycle_length),
                cycle_applicable=cycle_applicable,
                created_at=datetime.now(),
            )
            storage.save_profile(profile)
            st.session_state.profile = profile
            st.rerun()


def current_phase(profile: Profile) -> Phase | None:
    if profile.cycle_applicable and profile.last_period_start is not None:
        return phase_for_date(profile.last_period_start, profile.cycle_length)
    return None


def render_nav():
    st.markdown(f"### 🌸 powHER — hi, {st.session_state.profile.display_name}")
    cols = st.columns(4)
    labels = [("home", "🏠 Home"), ("workout", "🏋️ Today's Workout"), ("history", "📈 History"), ("cycle", "🌙 Cycle & Learn")]
    for col, (key, label) in zip(cols, labels):
        if col.button(label, use_container_width=True, key=f"nav_{key}"):
            st.session_state.page = key
    st.toggle("Dark mode", key="dark_mode")
    st.divider()


def _period_ongoing(events: list[PeriodEvent]) -> bool:
    """True if the most recently logged event is a period start (i.e. a period
    is underway and hasn't been marked ended yet)."""
    return bool(events) and events[-1].kind == "start"


def render_period_tracker(profile: Profile):
    events = storage.get_period_events(USER_ID)
    if _period_ongoing(events):
        start_date = events[-1].date
        st.caption(f"🩸 Period in progress — started {start_date.isoformat()}.")
        cols = st.columns([3, 1])
        end_date = cols[0].date_input(
            "Period ended on",
            value=date.today(),
            min_value=start_date,
            max_value=date.today(),
            key="period_end_date",
        )
        if cols[1].button("Log end", key="log_period_end", use_container_width=True):
            storage.save_period_event(
                PeriodEvent(
                    event_id=str(uuid.uuid4()), user_id=USER_ID, kind="end", date=end_date
                )
            )
            st.toast("Logged the end of your period. Take good care 💗")
            st.rerun()
    else:
        if st.button("🩸 Started period today", use_container_width=True):
            today = date.today()
            storage.save_period_event(
                PeriodEvent(
                    event_id=str(uuid.uuid4()), user_id=USER_ID, kind="start", date=today
                )
            )
            # Starting a period resets the phase reference date. Cycle length is
            # left as-is — the user only changes that manually in Cycle & Learn.
            profile.last_period_start = today
            storage.save_profile(profile)
            st.session_state.profile = profile
            st.toast("Logged the start of your period. Your phase estimate is updated.")
            st.rerun()


def render_home(profile: Profile):
    phase = current_phase(profile)
    if phase is not None:
        st.markdown(
            f"<div class='powher-card'>"
            f"<span class='powher-badge'>Estimated phase: {phase.value.title()}</span>"
            f"<p class='powher-note'>{ESTIMATE_NOTE}</p>"
            f"<p class='powher-keepinmind'>Something to keep in mind</p>"
            f"<p class='powher-edu'>{PHASE_BLURBS[phase]}</p>"
            f"<p class='powher-note'>{PHASE_NORMAL_LINE}</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
    if amenorrhea_flag(profile.last_period_start) if profile.cycle_applicable else False:
        st.warning(
            "You haven't logged a period in a while. That's really common and usually very "
            "treatable — but it's worth mentioning to a doctor, because it can be your body's "
            "way of saying it needs more fuel or more rest. Nothing about this means you've "
            "done anything wrong."
        )
    encouragement = PHASE_ENCOURAGEMENT.get(phase, GENERAL_ENCOURAGEMENT)
    st.markdown(
        f"<div class='powher-card'><span class='powher-quote'>“{encouragement}”</span></div>",
        unsafe_allow_html=True,
    )

    if profile.cycle_applicable:
        render_period_tracker(profile)

    st.write("Where to next?")
    c1, c2, c3 = st.columns(3)
    if c1.button("🏋️ Today's Workout", use_container_width=True, key="home_workout"):
        st.session_state.page = "workout"
        st.rerun()
    if c2.button("📈 History", use_container_width=True, key="home_history"):
        st.session_state.page = "history"
        st.rerun()
    if c3.button("🌙 Cycle & Learn", use_container_width=True, key="home_cycle"):
        st.session_state.page = "cycle"
        st.rerun()


SET_TYPE_LABELS = {
    SetType.NORMAL: "Normal",
    SetType.WARMUP: "Warm-up",
    SetType.FAILURE: "To failure",
}


def _new_set(set_type: SetType = SetType.NORMAL) -> dict:
    return {"uid": uuid.uuid4().hex, "weight": 0.0, "reps": 8, "set_type": set_type}


def _new_exercise() -> dict:
    return {"uid": uuid.uuid4().hex, "name": "", "notes": "", "sets": [_new_set()]}


def _blank_set(set_type: SetType) -> dict:
    """A set pre-filled from a routine: type preserved, weight and reps zeroed."""
    return {"uid": uuid.uuid4().hex, "weight": 0.0, "reps": 0, "set_type": set_type}


def _exercises_from_routine(routine: Routine) -> list[dict]:
    return [
        {
            "uid": uuid.uuid4().hex,
            "name": rex.name,
            "notes": "",
            "sets": [_blank_set(t) for t in rex.set_types] or [_blank_set(SetType.NORMAL)],
        }
        for rex in routine.exercises
    ]


def render_routine_bar():
    """Saved routines: one tap loads a named group of exercises as a fresh
    template (weights and reps zeroed). Routines are created from History."""
    routines = storage.get_routines(USER_ID)
    if not routines:
        return

    st.caption("Start from a routine")
    cols = st.columns(min(len(routines), 3))
    for i, routine in enumerate(routines):
        if cols[i % len(cols)].button(
            f"📋 {routine.name}", key=f"load_routine_{routine.routine_id}",
            use_container_width=True,
        ):
            st.session_state.workout_exercises = _exercises_from_routine(routine)
            st.toast(f"Loaded “{routine.name}” — fill in your weights and reps.")
            st.rerun()

    with st.expander("Manage routines"):
        for routine in routines:
            row = st.columns([5, 1])
            row[0].write(f"**{routine.name}** — {', '.join(r.name for r in routine.exercises)}")
            if row[1].button("🗑", key=f"del_routine_{routine.routine_id}", help="Delete this routine"):
                storage.delete_routine(routine.routine_id)
                st.rerun()


def render_exercise_inputs():
    """The per-exercise, per-set editor for the current workout."""
    for i, ex in enumerate(st.session_state.workout_exercises):
        eid = ex["uid"]
        with st.container(border=True):
            top = st.columns([5, 1])
            ex["name"] = top[0].text_input("Exercise", value=ex["name"], key=f"ex_name_{eid}")
            if len(st.session_state.workout_exercises) > 1:
                if top[1].button("🗑", key=f"ex_del_{eid}", help="Remove this exercise"):
                    st.session_state.workout_exercises.pop(i)
                    st.rerun()

            # "Previous" reference: the same exercise's sets from the most recent
            # past session, so she can see what to match or beat (Hevy-style).
            prev_sets = (
                storage.previous_exercise_sets(USER_ID, ex["name"]) if ex["name"].strip() else None
            )

            col_spec = [0.7, 2, 3, 2, 2, 0.8]
            header = st.columns(col_spec)
            for col, label in zip(header, ["Set", "Previous", "Type", "Weight", "Reps", ""]):
                col.caption(label)
            for j, s in enumerate(ex["sets"]):
                sid = s["uid"]
                cols = st.columns(col_spec)
                cols[0].markdown(f"**{j + 1}**")
                prev = prev_sets[j] if prev_sets and j < len(prev_sets) else None
                prev_label = f"{prev.weight:g}×{prev.reps}" if prev else "—"
                cols[1].markdown(
                    f"<span style='opacity:0.5'>{prev_label}</span>", unsafe_allow_html=True
                )
                s["set_type"] = cols[2].selectbox(
                    "Type", list(SET_TYPE_LABELS), index=list(SET_TYPE_LABELS).index(s["set_type"]),
                    format_func=lambda t: SET_TYPE_LABELS[t],
                    key=f"set_type_{sid}", label_visibility="collapsed",
                )
                s["weight"] = cols[3].number_input(
                    "Weight", min_value=0.0, value=float(s["weight"]), step=2.5,
                    key=f"set_weight_{sid}", label_visibility="collapsed",
                )
                s["reps"] = cols[4].number_input(
                    "Reps", min_value=0, value=int(s["reps"]),
                    key=f"set_reps_{sid}", label_visibility="collapsed",
                )
                if len(ex["sets"]) > 1:
                    if cols[5].button("✕", key=f"set_del_{sid}", help="Remove this set"):
                        ex["sets"].pop(j)
                        st.rerun()

            if st.button("+ Add set", key=f"add_set_{eid}"):
                ex["sets"].append({**ex["sets"][-1], "uid": uuid.uuid4().hex})
                st.rerun()

            ex["notes"] = st.text_input(
                "Notes for this exercise (optional)", value=ex["notes"], key=f"ex_notes_{eid}",
                placeholder="e.g. felt heavy today, paused reps, new grip",
            )

    if st.button("+ Add another exercise"):
        st.session_state.workout_exercises.append(_new_exercise())
        st.rerun()


def render_energy_tag_buttons() -> list[EnergyTag]:
    """Multi-select energy/symptom check-in as individual toggle buttons.
    Selected tags are highlighted; returns them in enum order."""
    if "today_energy_set" not in st.session_state:
        st.session_state.today_energy_set = set()
    st.caption("Tap all that apply")
    tags = list(EnergyTag)
    per_row = 2
    for start in range(0, len(tags), per_row):
        row = tags[start : start + per_row]
        cols = st.columns(len(row))
        for col, tag in zip(cols, row):
            selected = tag in st.session_state.today_energy_set
            if col.button(
                ENERGY_LABELS[tag],
                key=f"energy_btn_{tag.value}",
                type="primary" if selected else "secondary",
                use_container_width=True,
            ):
                if selected:
                    st.session_state.today_energy_set.discard(tag)
                else:
                    st.session_state.today_energy_set.add(tag)
                st.rerun()
    return [t for t in tags if t in st.session_state.today_energy_set]


REST_TIMER_HTML = """
<div style="font-family: sans-serif; text-align:center; color:inherit;">
  <div id="disp" style="font-size:2.4rem; font-weight:800; margin:0.2rem 0;">0:00</div>
  <div style="display:flex; gap:0.4rem; justify-content:center; flex-wrap:wrap;">
    <button onclick="setT(60)">60s</button>
    <button onclick="setT(90)">90s</button>
    <button onclick="setT(120)">2:00</button>
    <button onclick="setT(180)">3:00</button>
    <button onclick="stopT()" style="background:#e9e2ea;">Reset</button>
  </div>
  <style>
    button { border:none; border-radius:12px; padding:0.5rem 0.9rem; font-weight:700;
             font-size:0.95rem; cursor:pointer; background:#d8a7b1; color:#3d3241; }
    button:hover { opacity:0.85; }
  </style>
  <script>
    let remaining = 0, timer = null;
    const disp = document.getElementById('disp');
    function fmt(s){ const m=Math.floor(s/60); const ss=String(s%60).padStart(2,'0'); return m+':'+ss; }
    function tick(){ if(remaining<=0){ clearInterval(timer); timer=null; disp.textContent='Done! 💪'; return; }
                     remaining--; disp.textContent=fmt(remaining); }
    function setT(s){ remaining=s; disp.textContent=fmt(remaining);
                      if(timer) clearInterval(timer); timer=setInterval(tick,1000); }
    function stopT(){ if(timer) clearInterval(timer); timer=null; remaining=0; disp.textContent='0:00'; }
  </script>
</div>
"""


def render_rest_timer():
    with st.expander("⏱️ Rest timer"):
        components.html(REST_TIMER_HTML, height=150)


def render_workout(profile: Profile):
    st.subheader("Today's Workout")

    if "workout_exercises" not in st.session_state:
        st.session_state.workout_exercises = [_new_exercise()]

    # --- Step 1: check in and get the recommendation BEFORE working out ---
    st.markdown("**First, how are you feeling today?**")
    energy_tags = render_energy_tag_buttons()
    notes = st.text_area(
        "Anything you want to note before you start? (optional)",
        key="today_notes",
        placeholder="e.g. slept badly, feeling motivated, tight shoulder",
    )

    if st.button("Get my recommendation", type="primary"):
        if not energy_tags:
            st.error("Pick at least one energy tag so we know how to help.")
        else:
            history = storage.get_workouts(USER_ID)
            with st.spinner("Thinking this through..."):
                ctx = build_context(profile, energy_tags, profile.goal, notes, history)
                result = generate(ctx, energy_tags)
            st.session_state.today_reco = {
                "message": result.message,
                "recommendation": result.recommendation,
                "source_ids": sorted(result.source_ids),
                "used_fallback": result.used_fallback,
                "pattern_note": ctx.pattern_note,
            }
            st.rerun()

    reco = st.session_state.get("today_reco")
    if not reco:
        return

    st.markdown(
        f"<div class='powher-card'><span class='powher-quote'>“{reco['message']}”</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown("**Recommendation**")
    st.write(reco["recommendation"])
    if reco["source_ids"]:
        badges = "".join(
            f"<span class='powher-badge powher-badge-alt'>{sid}</span>" for sid in reco["source_ids"]
        )
        st.markdown(f"Sources: {badges}", unsafe_allow_html=True)
    if reco["used_fallback"]:
        st.caption("Served from our curated message bank this time, to stay safely grounded.")
    if reco["pattern_note"]:
        st.info(reco["pattern_note"])

    # --- Step 2: log the workout, then mark it done ---
    st.divider()
    st.markdown("### Now log your workout")
    render_routine_bar()
    render_rest_timer()
    render_exercise_inputs()

    workout_date = st.date_input(
        "Workout date",
        value=date.today(),
        max_value=date.today(),
        help="Defaults to today. Pick an earlier date to backfill past sessions — handy for "
        "building up history to see trends over time.",
    )

    if st.button("✅ Mark workout as done", type="primary"):
        exercises = [
            Exercise(
                name=ex["name"].strip(),
                sets=[
                    WorkoutSet(weight=float(s["weight"]), reps=int(s["reps"]), set_type=s["set_type"])
                    for s in ex["sets"]
                ],
                notes=ex["notes"].strip(),
            )
            for ex in st.session_state.workout_exercises
            if ex["name"].strip()
        ]
        if not exercises:
            st.error("Add at least one exercise before marking your workout done.")
            return

        # Detect weight PRs against prior history (this workout isn't saved yet).
        # Only for real, same-day sessions — backfilled dates shouldn't fire "new PR".
        prs = []
        if workout_date == date.today():
            for ex in exercises:
                prior_best = storage.best_working_weight(USER_ID, ex.name)
                today_best = ex.top_working_weight()
                if prior_best is not None and today_best is not None and today_best > prior_best:
                    prs.append(f"{ex.name.strip()} — {today_best:g} (up from {prior_best:g})")

        # Phase/cycle-day reflect the workout's own date, so backfilled sessions
        # map to the right point in the cycle for trends and pattern detection.
        phase = None
        cycle_day_val = None
        if (
            profile.cycle_applicable
            and profile.last_period_start is not None
            and workout_date >= profile.last_period_start
        ):
            phase = phase_for_date(profile.last_period_start, profile.cycle_length, workout_date)
            cycle_day_val = compute_cycle_day(
                profile.last_period_start, profile.cycle_length, workout_date
            )

        saved_tags = [t for t in EnergyTag if t in st.session_state.get("today_energy_set", set())]
        entry = WorkoutEntry(
            entry_id=str(uuid.uuid4()),
            user_id=USER_ID,
            date=workout_date,
            exercises=exercises,
            energy_tags=saved_tags,
            cycle_day=cycle_day_val,
            phase=phase,
            notes=st.session_state.get("today_notes", ""),
        )
        storage.save_workout(entry)
        if prs:
            st.session_state["celebrate"] = prs
        for key in ["today_reco", "today_energy_set", "today_notes", "workout_exercises"]:
            st.session_state.pop(key, None)
        st.toast("Workout saved to your History 💪 You can turn it into a routine there.")
        st.session_state.page = "history"
        st.rerun()


def render_save_as_routine(entry: WorkoutEntry):
    """Turn a saved workout into a reusable, named routine (exercises and set
    types only — weights and reps are entered fresh each time it's loaded)."""
    with st.expander("＋ Save as routine"):
        # A form batches the name field and submit so the text field's blur
        # can't collapse this expander before the save registers.
        with st.form(f"routine_from_{entry.entry_id}", clear_on_submit=True):
            routine_name = st.text_input("Routine name", placeholder="e.g. Leg Day")
            if st.form_submit_button("Save routine"):
                if not routine_name.strip():
                    st.error("Give your routine a name first.")
                else:
                    routine = Routine(
                        routine_id=str(uuid.uuid4()),
                        user_id=USER_ID,
                        name=routine_name.strip(),
                        exercises=[
                            RoutineExercise(
                                name=ex.name.strip(),
                                set_types=[s.set_type for s in ex.sets],
                            )
                            for ex in entry.exercises
                        ],
                    )
                    storage.save_routine(routine)
                    st.toast(f"Saved “{routine.name}” — start from it any time on Today's Workout.")
                    st.rerun()


def render_period_log():
    events = storage.get_period_events(USER_ID)
    if not events:
        return
    st.markdown("#### 🩸 Period log")
    with st.container(border=True):
        for e in reversed(events):  # newest first
            label = "Started" if e.kind == "start" else "Ended"
            st.write(f"**{label}** — {e.date.isoformat()}")
    st.divider()


def render_history(profile: Profile):
    st.subheader("History")

    celebrate = st.session_state.pop("celebrate", None)
    if celebrate:
        st.balloons()
        for pr in celebrate:
            st.success(f"🎉 New personal best — {pr}. That's your strength showing.")

    render_period_log()
    history = storage.get_workouts(USER_ID)
    if not history:
        st.write("No workouts logged yet — head to Today's Workout to log your first session.")
        return

    for entry in history:
        with st.container(border=True):
            st.markdown(f"**{entry.date.isoformat()}** — {', '.join(t.value.title() for t in entry.energy_tags)}")
            if entry.phase:
                st.caption(f"Estimated phase at the time: {entry.phase.value.title()} (cycle day {entry.cycle_day})")
            for ex in entry.exercises:
                set_bits = []
                for s in ex.sets:
                    bit = f"{s.weight:g}×{s.reps}"
                    if s.set_type == SetType.WARMUP:
                        bit += " (warm-up)"
                    elif s.set_type == SetType.FAILURE:
                        bit += " (to failure)"
                    set_bits.append(bit)
                st.write(f"- **{ex.name.strip()}**: {', '.join(set_bits)}")
                if ex.notes:
                    st.caption(f"↳ {ex.notes}")
            if entry.notes:
                st.caption(entry.notes)
            render_save_as_routine(entry)

    # Group exercises by normalized name (case, spacing, and plural insensitive)
    # so variants like "Goblet Squat", "goblet squat", and "goblet squats" share
    # one trend. Same resolver as storage.last_logged_weight.
    by_norm: dict[str, str] = {}
    for e in sorted(history, key=lambda e: e.date):
        for ex in e.exercises:
            by_norm[normalize_exercise_name(ex.name)] = ex.name.strip()  # keep latest spelling as label
    if by_norm:
        chosen = st.selectbox("Weight trend for", sorted(by_norm.values(), key=str.lower))
        chosen_norm = normalize_exercise_name(chosen)
        trend = [
            {"date": e.date, "weight": ex.top_working_weight()}
            for e in sorted(history, key=lambda e: e.date)
            for ex in e.exercises
            if normalize_exercise_name(ex.name) == chosen_norm and ex.top_working_weight() is not None
        ]
        if trend:
            import pandas as pd

            df = pd.DataFrame(trend).set_index("date")
            st.line_chart(df)

    tagged_days = [(e.cycle_day, e.energy_tags[0].value) for e in history if e.cycle_day is not None and e.energy_tags]
    if tagged_days:
        st.write("Energy tags mapped against cycle day:")
        import pandas as pd

        df = pd.DataFrame(tagged_days, columns=["cycle_day", "energy_tag"])
        st.dataframe(df, use_container_width=True, hide_index=True)


def render_cycle(profile: Profile):
    st.subheader("Cycle & Learn")

    with st.form("cycle_update"):
        cycle_applicable = not st.checkbox(
            "This might not apply to me right now", value=not profile.cycle_applicable
        )
        if not cycle_applicable:
            st.info(
                "For irregular cycles, hormonal birth control, perimenopause, or if you're not "
                "currently cycling — phase estimates won't be accurate for you, and we don't "
                "want to guess. We're actively working on finding accurate, well-researched "
                "guidance for these situations, and we want to build for you properly rather "
                "than quickly. In the meantime, everything else in powHER still works: log your "
                "workouts, tag your energy, and get recommendations based on how you're actually "
                "feeling."
            )
        last_period_start = profile.last_period_start or date.today()
        cycle_length = profile.cycle_length
        if cycle_applicable:
            last_period_start = st.date_input("First day of your last period", value=last_period_start)
            cycle_length = st.number_input(
                "Typical cycle length (days)", min_value=15, max_value=45, value=cycle_length,
                help=CYCLE_LENGTH_HELP,
            )
        if st.form_submit_button("Save"):
            profile.cycle_applicable = cycle_applicable
            profile.last_period_start = last_period_start if cycle_applicable else None
            profile.cycle_length = int(cycle_length)
            storage.save_profile(profile)
            st.session_state.profile = profile
            st.success("Saved.")
            st.rerun()

    if profile.cycle_applicable and profile.last_period_start:
        phase = phase_for_date(profile.last_period_start, profile.cycle_length)
        st.markdown(f"**Estimated phase today: {phase.value.title()}**")
        st.caption(ESTIMATE_NOTE)

    st.markdown("### Phase education")
    for phase, text in PHASE_EDUCATION.items():
        st.markdown(
            f"<div class='powher-phase'><h4>{phase.value.title()}</h4><p>{text}</p></div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        f"<p class='powher-note' style='text-align:center'>{PHASE_NORMAL_LINE}</p>",
        unsafe_allow_html=True,
    )

    st.divider()
    st.markdown("### Your data")
    st.caption("Cycle dates are encrypted at rest. You can delete everything, any time.")
    if st.button("Delete all my data", type="secondary"):
        storage.delete_all_user_data(USER_ID)
        for key in [
            "profile", "page", "workout_exercises", "today_energy_set",
            "today_notes", "today_reco", "celebrate",
        ]:
            st.session_state.pop(key, None)
        st.success("All your data has been deleted.")
        st.rerun()


def main():
    ensure_profile_loaded()
    inject_css()
    if st.session_state.profile is None:
        render_onboarding()
        return

    if "page" not in st.session_state:
        st.session_state.page = "home"

    render_nav()
    page = st.session_state.page
    profile = st.session_state.profile
    if page == "home":
        render_home(profile)
    elif page == "workout":
        render_workout(profile)
    elif page == "history":
        render_history(profile)
    elif page == "cycle":
        render_cycle(profile)


if __name__ == "__main__":
    main()
