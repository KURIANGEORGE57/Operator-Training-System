"""Sidebar: scenario selection, controller choice, and plant reset."""

from __future__ import annotations

from typing import Dict, Tuple

import streamlit as st

from src.scenarios.library import SCENARIO_LIBRARY, Scenario


def render_sidebar() -> Tuple[Dict[str, float], str]:
    """Render the sidebar and return (scenario_dict, controller_name)."""

    st.sidebar.header("Training Scenario")

    scenario_names = [s.name for s in SCENARIO_LIBRARY]
    selected_name = st.sidebar.selectbox(
        "Scenario",
        scenario_names,
        index=0,
        help="Choose a pre-built scenario or Custom to set your own.",
    )

    scenario = next(s for s in SCENARIO_LIBRARY if s.name == selected_name)

    if selected_name == "Custom":
        F_feed = st.sidebar.slider("Feed rate (t/h)", 50.0, 120.0, 80.0, 1.0)
        zB_feed = st.sidebar.slider("Benzene in feed", 0.45, 0.75, 0.60, 0.01)
        foul_c = st.sidebar.slider("Condenser fouling", 0.0, 0.60, 0.0, 0.05)
        foul_r = st.sidebar.slider("Reboiler fouling", 0.0, 0.60, 0.0, 0.05)
        scenario_dict = {
            "F_feed": F_feed,
            "zB_feed": zB_feed,
            "Fouling_Cond": foul_c,
            "Fouling_Reb": foul_r,
        }
    else:
        scenario_dict = scenario.to_dict()
        st.sidebar.markdown(f"**Difficulty:** {scenario.difficulty}")
        st.sidebar.markdown(f"*{scenario.description}*")
        st.sidebar.markdown(
            f"Feed: {scenario.F_feed} t/h | zB: {scenario.zB_feed:.0%}"
        )
        if scenario.Fouling_Cond > 0 or scenario.Fouling_Reb > 0:
            st.sidebar.markdown(
                f"Fouling: Cond {scenario.Fouling_Cond:.0%} / Reb {scenario.Fouling_Reb:.0%}"
            )

    st.sidebar.divider()

    st.sidebar.header("Controller")
    controller_name = st.sidebar.radio(
        "Auto-controller",
        ["None (Manual)", "NN Policy", "Linear MPC"],
        index=0,
        help="Choose an automated controller or operate manually.",
    )

    st.sidebar.divider()

    if st.sidebar.button("Reset Plant", type="secondary", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    return scenario_dict, controller_name
