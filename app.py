"""Benzene Column Operator Training System.

A turn-based process simulation for training operators on a benzene-toluene
distillation column. Features physics-based plant dynamics, a three-tier
safety system, multiple control strategies, and performance scoring.
"""

from __future__ import annotations

from typing import Dict, List

import streamlit as st

from src.models import Plant, PlantState, STEADY_STATE
from src.models.plant import cap_moves
from src.safety import evaluate_safety, SafetyResult
from src.controllers import NNController, MPCController
from src.scoring import ScoreTracker
from src.ui.sidebar import render_sidebar
from src.ui.dashboard import render_dashboard
from src.ui.controls import render_controls
from src.ui.schematic import render_schematic
from src.ui.trends import render_trends, render_score_trend
from src.ui.event_log import render_event_log


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

def _init_session() -> None:
    """Set up session state on first load."""
    if "plant" not in st.session_state:
        st.session_state.plant = Plant()
    if "turn" not in st.session_state:
        st.session_state.turn = 0
    if "scorer" not in st.session_state:
        st.session_state.scorer = ScoreTracker()
    if "event_log" not in st.session_state:
        st.session_state.event_log: List[Dict[str, str]] = []
    if "state_history" not in st.session_state:
        st.session_state.state_history: List[Dict[str, float]] = []
    if "score_history" not in st.session_state:
        st.session_state.score_history: List[float] = []


def _log_event(turn: int, severity: str, message: str) -> None:
    st.session_state.event_log.append(
        {"turn": str(turn), "severity": severity, "message": message}
    )


def _record_state(state: PlantState) -> None:
    st.session_state.state_history.append(state.to_dict())


# ---------------------------------------------------------------------------
# Simulation step
# ---------------------------------------------------------------------------

def _execute_turn(
    u_raw: Dict[str, float],
    scenario: Dict[str, float],
    source: str,
) -> SafetyResult:
    """Execute one simulation turn with safety evaluation.

    Implements the two-phase commit pattern:
      1. Compute tentative next state
      2. Evaluate safety
      3. Commit (or ESD / interlock override)
    """
    plant: Plant = st.session_state.plant
    turn: int = st.session_state.turn + 1

    # Rate-limit control moves
    u_capped = cap_moves(u_raw, plant.state)

    # Phase 1: tentative state
    x_next = plant.step(u_capped, scenario)

    # Phase 2: safety evaluation
    safety = evaluate_safety(x_next, u_capped)

    # Phase 3: commit
    if safety.esd_triggered:
        plant.esd_safe_state()
        _log_event(turn, "esd", safety.esd_reason)
    elif safety.interlock_active:
        # Recalculate with adjusted inputs
        x_adjusted = plant.step(safety.adjusted_inputs, scenario)
        plant.commit(x_adjusted)
        _log_event(turn, "interlock", safety.interlock_reason)
    else:
        plant.commit(x_next)

    # Log alarms
    for alarm in safety.alarms:
        _log_event(turn, "alarm", alarm)

    # Log operator action
    _log_event(
        turn,
        "action",
        f"{source}: Ref={u_capped['SP_F_Reflux']:.1f} "
        f"Reb={u_capped['SP_F_Reboil']:.2f} "
        f"ToT={u_capped['SP_F_ToTol']:.1f}",
    )

    # Score and record
    score = st.session_state.scorer.score_turn(turn, plant.state, safety)
    st.session_state.score_history.append(score.total)
    _record_state(plant.state)
    st.session_state.turn = turn

    return safety


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Benzene Column OTS",
        page_icon="🏭",
        layout="wide",
    )

    _init_session()

    # Title
    st.markdown(
        "# Benzene Column Operator Training System\n"
        "*Turn-based distillation simulator with safety systems and performance scoring*"
    )

    # Sidebar: scenario + controller selection
    scenario_dict, controller_name = render_sidebar()

    plant: Plant = st.session_state.plant
    scorer: ScoreTracker = st.session_state.scorer
    state = plant.state

    # KPI dashboard
    render_dashboard(state, scorer)

    st.divider()

    # Control panel
    setpoints, action = render_controls(state)

    # Process action
    if action != "none":
        if action == "controller" and controller_name != "None (Manual)":
            if controller_name == "NN Policy":
                ctrl = NNController()
            else:
                ctrl = MPCController()
            u = ctrl.decide(state, scenario_dict)
            source = f"Auto ({ctrl.name})"
        elif action == "next":
            # Hold current values
            u = {
                "SP_F_Reflux": state.F_Reflux,
                "SP_F_Reboil": state.F_Reboil,
                "SP_F_ToTol": state.F_ToTol,
            }
            source = "Hold"
        else:
            u = setpoints
            source = "Operator"

        safety = _execute_turn(u, scenario_dict, source)
        state = plant.state  # refresh after commit

        # Show turn result
        turn = st.session_state.turn
        score = scorer.history[-1] if scorer.history else None

        if safety.esd_triggered:
            st.error(f"Turn {turn}: EMERGENCY SHUTDOWN - {safety.esd_reason}")
        elif safety.interlock_active:
            st.warning(f"Turn {turn}: Interlock active - {safety.interlock_reason}")
        elif safety.alarms:
            st.warning(f"Turn {turn}: {len(safety.alarms)} alarm(s) active")
        else:
            st.success(f"Turn {turn}: Normal operation")

        if score:
            st.caption(
                f"Score: {score.total:.0f}/100 ({score.grade}) | "
                f"Purity: {score.purity_score:.0f} | "
                f"Pressure: {score.pressure_score:.0f} | "
                f"Levels: {score.level_score:.0f} | "
                f"Safety: {score.safety_penalty:+.0f}"
            )

    st.divider()

    # Process schematic
    last_safety = (
        evaluate_safety(state, {
            "SP_F_Reflux": state.F_Reflux,
            "SP_F_Reboil": state.F_Reboil,
            "SP_F_ToTol": state.F_ToTol,
        })
        if st.session_state.turn > 0
        else SafetyResult()
    )
    render_schematic(
        state,
        alarms=last_safety.alarms,
        interlock_active=last_safety.interlock_active,
        esd_triggered=last_safety.esd_triggered,
    )

    st.divider()

    # Trends and event log in two columns
    col_left, col_right = st.columns([3, 2])

    with col_left:
        render_trends(st.session_state.state_history)
        render_score_trend(st.session_state.score_history)

    with col_right:
        render_event_log(st.session_state.event_log)

        # Summary stats
        if scorer.history:
            st.markdown("### Session Summary")
            summary = scorer.summary()
            st.markdown(
                f"**Turns:** {summary['turns']} | "
                f"**Average:** {summary['average_score']:.0f} ({summary['grade']})"
            )
            st.markdown(
                f"**ESDs:** {summary['esd_trips']} | "
                f"**Interlocks:** {summary['interlocks']} | "
                f"**Alarms:** {summary['alarms']}"
            )


if __name__ == "__main__":
    main()
