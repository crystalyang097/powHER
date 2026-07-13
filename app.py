"""powHER — Streamlit entry point."""

import uuid
from datetime import date, datetime

import streamlit as st

from powher import storage
from powher.agent import generate
from powher.context_builder import build_context
from powher.cycle import (
    ESTIMATE_NOTE,
    amenorrhea_flag,
    cycle_day as compute_cycle_day,
    phase_for_date,
)
from powher.messages import get_fallback_message
from powher.models import EnergyTag, Exercise, Phase, Profile, WorkoutEntry

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
    EnergyTag.CRAMPING: "〰️ Cramping",
    EnergyTag.IN_PAIN: "⚠️ In pain",
    EnergyTag.FASTER_FATIGUE: "🌀 Fatiguing faster than usual",
}
PHASE_BLURBS = {
    Phase.MENSTRUAL: "Bleeding phase. Some feel low-energy here, some don't — both are normal. Movement is evidence-backed for easing period pain, not something to avoid.",
    Phase.FOLLICULAR: "Estrogen is rising as your body preps to ovulate. Some report more energy here; the evidence for a consistent boost is weak, so there's no rule to expect it.",
    Phase.OVULATORY: "The few days around mid-cycle. Some feel a short burst of energy, others notice nothing distinct.",
    Phase.LUTEAL: "Progesterone rises, then both hormones drop before your next period — PMS symptoms are most commonly reported in this window.",
}

st.set_page_config(page_title="powHER", page_icon="🌸", layout="centered")


def inject_css():
    dark = st.session_state.get("dark_mode", False)
    if dark:
        bg, card, text, accent, accent2 = "#2b2338", "#3a3048", "#f2ebe4", "#c9a7c9", "#a9c9b8"
    else:
        bg, card, text, accent, accent2 = "#fdf8f3", "#ffffff", "#3d3241", "#d8a7b1", "#a9c9b8"
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
                "Typical cycle length (days) :red[*]", min_value=15, max_value=45, value=28
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


def render_home(profile: Profile):
    phase = current_phase(profile)
    if phase is not None:
        st.markdown(
            f"<div class='powher-card'><span class='powher-badge'>Estimated phase: {phase.value.title()}</span>"
            f"<p class='powher-note'>{ESTIMATE_NOTE}</p></div>",
            unsafe_allow_html=True,
        )
    if amenorrhea_flag(profile.last_period_start) if profile.cycle_applicable else False:
        st.warning(
            "You haven't logged a period in a while. That's really common and usually very "
            "treatable — but it's worth mentioning to a doctor, because it can be your body's "
            "way of saying it needs more fuel or more rest. Nothing about this means you've "
            "done anything wrong."
        )
    todays_message = get_fallback_message(EnergyTag.NORMAL, phase)
    st.markdown(
        f"<div class='powher-card'><span class='powher-quote'>“{todays_message}”</span></div>",
        unsafe_allow_html=True,
    )
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


def render_workout(profile: Profile):
    st.subheader("Today's Workout")

    if "exercise_rows" not in st.session_state:
        st.session_state.exercise_rows = [{"name": "", "weight": 0.0, "reps": 8, "sets": 3}]

    for i, row in enumerate(st.session_state.exercise_rows):
        cols = st.columns([3, 2, 2, 2])
        row["name"] = cols[0].text_input("Exercise", value=row["name"], key=f"name_{i}")
        row["weight"] = cols[1].number_input("Weight", min_value=0.0, value=float(row["weight"]), key=f"weight_{i}", step=2.5)
        row["reps"] = cols[2].number_input("Reps", min_value=1, value=int(row["reps"]), key=f"reps_{i}")
        row["sets"] = cols[3].number_input("Sets", min_value=1, value=int(row["sets"]), key=f"sets_{i}")

    if st.button("+ Add another exercise"):
        st.session_state.exercise_rows.append({"name": "", "weight": 0.0, "reps": 8, "sets": 3})
        st.rerun()

    energy_tags = st.multiselect(
        "How are you feeling today? (pick one or more)",
        options=list(EnergyTag),
        format_func=lambda t: ENERGY_LABELS[t],
    )
    notes = st.text_area("Notes (optional)", value="")

    if st.button("Get my recommendation", type="primary"):
        if not energy_tags:
            st.error("Pick at least one energy tag so we know how to help.")
            return
        exercises = [
            Exercise(name=r["name"].strip(), weight=r["weight"], reps=int(r["reps"]), sets=int(r["sets"]))
            for r in st.session_state.exercise_rows
            if r["name"].strip()
        ]

        phase = current_phase(profile)
        cycle_day_val = None
        if profile.cycle_applicable and profile.last_period_start is not None:
            cycle_day_val = compute_cycle_day(profile.last_period_start, profile.cycle_length)

        history = storage.get_workouts(USER_ID)

        last_logged_weight = None
        proposed_weight = None
        if exercises:
            primary = exercises[0]
            last_logged_weight = storage.last_logged_weight(USER_ID, primary.name)
            if EnergyTag.ENERGIZED in energy_tags and last_logged_weight:
                proposed_weight = round((last_logged_weight * 1.05) / 2.5) * 2.5

        with st.spinner("Thinking this through..."):
            ctx = build_context(profile, energy_tags, profile.goal, notes, history)
            result = generate(ctx, energy_tags, last_logged_weight=last_logged_weight, proposed_weight=proposed_weight)

        entry = WorkoutEntry(
            entry_id=str(uuid.uuid4()),
            user_id=USER_ID,
            date=date.today(),
            exercises=exercises,
            energy_tags=energy_tags,
            cycle_day=cycle_day_val,
            phase=phase,
            notes=notes,
        )
        storage.save_workout(entry)

        st.markdown(
            f"<div class='powher-card'><span class='powher-quote'>“{result.message}”</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown("**Recommendation**")
        st.write(result.recommendation)
        if result.source_ids:
            badges = "".join(f"<span class='powher-badge powher-badge-alt'>{sid}</span>" for sid in sorted(result.source_ids))
            st.markdown(f"Sources: {badges}", unsafe_allow_html=True)
        if result.used_fallback:
            st.caption("Served from our curated message bank this time, to stay safely grounded.")
        if ctx.pattern_note:
            st.info(ctx.pattern_note)


def render_history(profile: Profile):
    st.subheader("History")
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
                st.write(f"- {ex.name}: {ex.weight} × {ex.reps} reps × {ex.sets} sets")
            if entry.notes:
                st.caption(entry.notes)

    exercise_names = sorted({ex.name for e in history for ex in e.exercises})
    if exercise_names:
        chosen = st.selectbox("Weight trend for", exercise_names)
        trend = [
            {"date": e.date, "weight": ex.weight}
            for e in sorted(history, key=lambda e: e.date)
            for ex in e.exercises
            if ex.name == chosen
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
            cycle_length = st.number_input("Typical cycle length (days)", min_value=15, max_value=45, value=cycle_length)
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
    for phase, blurb in PHASE_BLURBS.items():
        st.markdown(f"**{phase.value.title()}**")
        st.write(blurb)
        st.caption("Some women notice this. Many notice nothing. Both are completely normal.")

    st.divider()
    st.markdown("### Your data")
    st.caption("Cycle dates are encrypted at rest. You can delete everything, any time.")
    if st.button("Delete all my data", type="secondary"):
        storage.delete_all_user_data(USER_ID)
        for key in ["profile", "page", "exercise_rows"]:
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
