"""Streamlit MVP for the operator training system."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List

import numpy as np
import pandas as pd
import streamlit as st

from logger import get_logger
from scoring import ScoreTracker
from ui import render_header


@dataclass
class PlantState:
    """Represent the simplified state of the process plant."""

    level: float
    temperature: float
    pressure: float

    def as_array(self) -> np.ndarray:
        return np.array([self.level, self.temperature, self.pressure], dtype=float)

    @classmethod
    def from_array(cls, values: np.ndarray) -> PlantState:
        return cls(level=float(values[0]), temperature=float(values[1]), pressure=float(values[2]))


LOGGER = get_logger()
MVS = ["feed_valve", "heater_duty", "reflux_ratio"]
FAULT_LIBRARY = {
    "None": "No active fault",
    "Heater Fouling": "Reduces temperature response by lowering energy input.",
    "Reflux Pump Trip": "Drops column pressure by removing reflux flow.",
    "Level Sensor Drift": "Skews the reported level upward by a fixed offset.",
}


def initialize_session() -> None:
    if "plant_state" not in st.session_state:
        st.session_state.plant_state = PlantState(level=50.0, temperature=350.0, pressure=5.0)
    if "mv_settings" not in st.session_state:
        st.session_state.mv_settings = {"feed_valve": 0.5, "heater_duty": 0.5, "reflux_ratio": 0.5}
    if "active_faults" not in st.session_state:
        st.session_state.active_faults: List[str] = []
    if "score_tracker" not in st.session_state:
        st.session_state.score_tracker = ScoreTracker()
    if "log_records" not in st.session_state:
        st.session_state.log_records: List[Dict[str, float]] = []


def steady_state_map(mv_settings: Dict[str, float], faults: List[str]) -> Dict[str, float]:
    """Simple surrogate relating manipulated variables to process state."""
    base_state = np.array([50.0, 350.0, 5.0])
    influence_matrix = np.array([
        [40.0,  5.0, -10.0],
        [ 5.0, 80.0,   2.0],
        [-10.0, 10.0,  20.0],
    ])
    mv_vector = np.array([mv_settings[mv] - 0.5 for mv in MVS])
    result = base_state + influence_matrix.T @ mv_vector

    for fault in faults:
        if fault == "Heater Fouling":
            result[1] -= 25.0
        elif fault == "Reflux Pump Trip":
            result[2] -= 1.5
            result[0] += 5.0
        elif fault == "Level Sensor Drift":
            result[0] += 3.0

    return {"level": float(result[0]), "temperature": float(result[1]), "pressure": float(result[2])}


def run_first_order_update(state: PlantState, target: Dict[str, float], dt: float = 1.0, tau: float = 6.0) -> PlantState:
    """Relax the plant state toward the steady-state target."""
    current = state.as_array()
    target_vec = np.array([target["level"], target["temperature"], target["pressure"]])
    updated = current + (target_vec - current) * (dt / tau)
    noise = np.random.normal(scale=[0.2, 0.5, 0.05])
    return PlantState.from_array(updated + noise)


def render_sidebar() -> Dict[str, float]:
    st.sidebar.header("Controls")
    st.sidebar.write("Manipulated variables (0-1 scale)")
    mv_settings: Dict[str, float] = {}
    mv_settings["feed_valve"] = st.sidebar.slider("Feed Valve", 0.0, 1.0, float(st.session_state.mv_settings["feed_valve"]))
    mv_settings["heater_duty"] = st.sidebar.slider("Heater Duty", 0.0, 1.0, float(st.session_state.mv_settings["heater_duty"]))
    mv_settings["reflux_ratio"] = st.sidebar.slider("Reflux Ratio", 0.0, 1.0, float(st.session_state.mv_settings["reflux_ratio"]))

    selected_faults = st.sidebar.multiselect(
        "Injected Faults",
        options=[f for f in FAULT_LIBRARY if f != "None"],
        default=st.session_state.active_faults,
        help="Select process faults to challenge the operator.",
    )
    st.session_state.active_faults = selected_faults

    st.sidebar.write("\n**Fault Descriptions**")
    for name, description in FAULT_LIBRARY.items():
        if name != "None":
            st.sidebar.caption(f"{name}: {description}")

    st.session_state.mv_settings = mv_settings
    return mv_settings


def render_targets() -> Dict[str, float]:
    st.subheader("Performance Targets")
    col_level, col_temp, col_press = st.columns(3)
    with col_level:
        target_level = st.number_input("Level setpoint", value=50.0, step=1.0)
    with col_temp:
        target_temp = st.number_input("Temperature setpoint", value=350.0, step=5.0)
    with col_press:
        target_press = st.number_input("Pressure setpoint", value=5.0, step=0.1, format="%.2f")
    return {"level": target_level, "temperature": target_temp, "pressure": target_press}


def log_update(new_state: PlantState, mv_settings: Dict[str, float]) -> None:
    record = {**mv_settings, **asdict(new_state)}
    st.session_state.log_records.append(record)
    LOGGER.info("State updated: %s", record)


def render_log() -> None:
    st.subheader("Simulation Log")
    if not st.session_state.log_records:
        st.info("Adjust the controls and press *Advance Simulation* to begin logging.")
        return
    df = pd.DataFrame(st.session_state.log_records)
    st.dataframe(df.tail(10), use_container_width=True)


def render_scoreboard() -> None:
    tracker: ScoreTracker = st.session_state.score_tracker
    st.subheader("Scoreboard")
    if not tracker.history:
        st.caption("No scores yet. Keep iterating toward the targets!")
        return
    score_df = pd.DataFrame({"Score": tracker.history})
    st.metric("Average Score", f"{tracker.average:.3f}")
    st.line_chart(score_df)


def main() -> None:
    st.set_page_config(page_title="Operator Training System", layout="wide")
    initialize_session()
    render_header("Operator Training System", "MVP training environment for process operators")

    mv_settings = render_sidebar()
    target_state = steady_state_map(mv_settings, st.session_state.active_faults)
    operator_targets = render_targets()

    if st.button("Advance Simulation", type="primary"):
        new_state = run_first_order_update(st.session_state.plant_state, target_state)
        st.session_state.plant_state = new_state
        log_update(new_state, mv_settings)

        actual = new_state.as_array()
        desired = np.array([operator_targets["level"], operator_targets["temperature"], operator_targets["pressure"]])
        deviation = actual - desired
        score = st.session_state.score_tracker.update(deviation)
        st.success(f"New score: {score:.3f}")

    st.subheader("Current Plant State")
    st.dataframe(pd.DataFrame([asdict(st.session_state.plant_state)], columns=["level", "temperature", "pressure"]))

    with st.expander("Steady-State Prediction", expanded=False):
        st.json(target_state)

    render_log()
    render_scoreboard()


if __name__ == "__main__":
    main()
