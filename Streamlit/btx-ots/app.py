import streamlit as st
import numpy as np
from typing import Dict
import sys
import os

# Add parent directory to path for logger import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from plant_neqsim import PlantNeqSim
from ui.image_panel import render_process_panel
from constants import (
    SAFETY_LIMITS,
    SLIDER_CONFIG,
    MOVE_RATE_CAPS,
    INTERLOCK_ADJUSTMENTS,
    DEFAULTS,
    EVENT_LOG_LINES,
    CONTROLLER_LIMITS,
)
from logger import get_logger

logger = get_logger("btx-ots")

st.set_page_config("BTX Benzene Column — Turn-based OTS", layout="wide")

# ---- Session bootstrap ----
if "plant" not in st.session_state:
    st.session_state.plant = PlantNeqSim()
if "turn" not in st.session_state:
    st.session_state.turn = 0
if "log" not in st.session_state:
    st.session_state.log = []
if "phase" not in st.session_state:
    st.session_state.phase = "READY"   # READY -> APPLIED

plant: PlantNeqSim = st.session_state.plant

# Use constants for safety limits
LIMITS = SAFETY_LIMITS

# ---- Input validation helper ----
def validate_numeric_input(value, min_val, max_val, name):
    """Validate that a numeric input is within expected bounds."""
    if not isinstance(value, (int, float)):
        logger.error(f"Invalid type for {name}: expected numeric, got {type(value)}")
        raise ValueError(f"{name} must be a number")
    if not (min_val <= value <= max_val):
        logger.warning(f"{name} value {value} out of bounds [{min_val}, {max_val}], clamping")
        return max(min_val, min(max_val, value))
    return value

# ---- Sidebar: scenario & controller selection ----
with st.sidebar:
    st.header("Scenario")
    cfg = SLIDER_CONFIG
    fouling_cond = st.slider(
        "Condenser fouling (%)",
        cfg["fouling_condenser"]["min"],
        cfg["fouling_condenser"]["max"],
        cfg["fouling_condenser"]["default"],
        step=cfg["fouling_condenser"]["step"]
    )
    fouling_reb = st.slider(
        "Reboiler fouling (%)",
        cfg["fouling_reboiler"]["min"],
        cfg["fouling_reboiler"]["max"],
        cfg["fouling_reboiler"]["default"],
        step=cfg["fouling_reboiler"]["step"]
    )
    zB_feed = st.slider(
        "Feed benzene (mol frac)",
        cfg["feed_benzene"]["min"],
        cfg["feed_benzene"]["max"],
        cfg["feed_benzene"]["default"],
        step=cfg["feed_benzene"]["step"]
    )
    F_feed = st.slider(
        "Feed rate (t/h)",
        cfg["feed_rate"]["min"],
        cfg["feed_rate"]["max"],
        cfg["feed_rate"]["default"],
        step=cfg["feed_rate"]["step"]
    )
    controller_choice = st.selectbox("Controller", ["NN policy", "Linear MPC (2×2)"])
    if st.button("Reset scenario"):
        logger.info("Scenario reset initiated")
        st.session_state.plant = PlantNeqSim()
        st.session_state.turn = 0
        st.session_state.log = []
        st.session_state.phase = "READY"
        st.rerun()

# ---- Lazy import chosen controller ----
if controller_choice == "NN policy":
    from controllers.nn_controller import ControllerNN as Controller
else:
    from controllers.mpc_controller import ControllerMPC as Controller
controller = Controller()

# ---- Headline & KPIs ----
st.title("Benzene Column — Turn-based OTS")
x = plant.state
k1, k2, k3, k4 = st.columns(4)
k1.metric("Benzene purity (side-draw)", f"{x['xB_sd']:.5f}")
k2.metric("Column ΔP (bar)", f"{x['dP_col']:.3f}")
k3.metric("Overhead T (°C)", f"{x['T_top']:.1f}")
k4.metric("Energy proxy (MW eq.)", f"{x['F_Reboil']:.2f}")

# ---- Controls (inner-loop setpoints) ----
locked = st.session_state.phase != "READY"
c1, c2, c3 = st.columns(3)
SP_F_Reflux = c1.slider(
    "SP_F_Reflux (t/h)",
    cfg["SP_F_Reflux"]["min"],
    cfg["SP_F_Reflux"]["max"],
    float(x["F_Reflux"]),
    step=cfg["SP_F_Reflux"]["step"],
    disabled=locked
)
SP_F_Reboil = c2.slider(
    "SP_F_Reboil (MW eq.)",
    cfg["SP_F_Reboil"]["min"],
    cfg["SP_F_Reboil"]["max"],
    float(x["F_Reboil"]),
    step=cfg["SP_F_Reboil"]["step"],
    disabled=locked
)
SP_F_ToTol = c3.slider(
    "SP_F_ToTol (t/h)",
    cfg["SP_F_ToTol"]["min"],
    cfg["SP_F_ToTol"]["max"],
    float(x["F_ToTol"]),
    step=cfg["SP_F_ToTol"]["step"],
    disabled=locked
)

# ---- Helper: per-turn move caps ----
def cap_moves(u_req: Dict, x_curr: Dict) -> Dict:
    """Apply rate-of-change limits to setpoint changes."""
    caps = MOVE_RATE_CAPS
    u = u_req.copy()
    for key in ["SP_F_Reflux", "SP_F_Reboil", "SP_F_ToTol"]:
        actual_key = key.replace("SP_", "")
        u[key] = float(np.clip(
            u[key],
            x_curr[actual_key] - caps[key],
            x_curr[actual_key] + caps[key]
        ))
    return u

# ---- Safety / guardrails (deterministic) ----
def safety_logic(x_next: Dict, u_applied: Dict) -> Dict:
    """Check safety conditions and determine required actions."""
    alarms, interlock, esd = [], [], False
    adjust = {}

    # Check alarm conditions
    if x_next["dP_col"] > LIMITS["dP_alarm"]:
        alarms.append("High column ΔP")
        logger.warning(f"High column ΔP alarm: {x_next['dP_col']:.3f} bar > {LIMITS['dP_alarm']:.3f} bar")

    if x_next["T_top"] > LIMITS["T_top_alarm"]:
        alarms.append("High overhead T")
        logger.warning(f"High overhead T alarm: {x_next['T_top']:.1f} °C > {LIMITS['T_top_alarm']:.1f} °C")

    if x_next["xB_sd"] < LIMITS["xB_spec"]:
        alarms.append("Off-spec benzene purity")
        logger.warning(f"Off-spec benzene purity: {x_next['xB_sd']:.5f} < {LIMITS['xB_spec']:.5f}")

    drum_level = x_next.get("L_Drum", DEFAULTS["L_drum_fallback"])
    if drum_level < LIMITS["L_drum_min"]:
        alarms.append("Low reflux drum level")
        logger.warning(f"Low reflux drum level: {drum_level:.3f} < {LIMITS['L_drum_min']:.3f}")

    # Interlock (example flooding)
    if x_next["dP_col"] > LIMITS["dP_trip"]:
        interlock.append("Flooding ILK: clamp reboil, increase reflux")
        adjust["SP_F_Reboil"] = max(
            u_applied["SP_F_Reboil"] - INTERLOCK_ADJUSTMENTS["reboil_decrease"],
            INTERLOCK_ADJUSTMENTS["reboil_min"]
        )
        adjust["SP_F_Reflux"] = min(
            u_applied["SP_F_Reflux"] + INTERLOCK_ADJUSTMENTS["reflux_increase"],
            INTERLOCK_ADJUSTMENTS["reflux_max"]
        )
        logger.error(f"Flooding interlock triggered at ΔP={x_next['dP_col']:.3f} bar. "
                    f"Adjusting reboil to {adjust['SP_F_Reboil']:.2f}, reflux to {adjust['SP_F_Reflux']:.2f}")

    # ESD conditions
    esd_reasons = []
    if x_next["dP_col"] > LIMITS["dP_esd"]:
        esd_reasons.append(f"ΔP={x_next['dP_col']:.3f} > {LIMITS['dP_esd']:.3f}")
    if x_next["T_top"] > LIMITS["T_top_esd"]:
        esd_reasons.append(f"T_top={x_next['T_top']:.1f} > {LIMITS['T_top_esd']:.1f}")
    if drum_level < LIMITS["L_drum_crit"]:
        esd_reasons.append(f"L_Drum={drum_level:.3f} < {LIMITS['L_drum_crit']:.3f}")

    if esd_reasons:
        esd = True
        logger.critical(f"ESD TRIGGERED: {'; '.join(esd_reasons)}")

    return {"alarms": alarms, "interlock": interlock, "adjust": adjust, "esd": esd}

# ---- Helper: process action (DRY - removes duplicate code) ----
def process_action(u_req: Dict, scenario: Dict, events: Dict, source: str) -> None:
    """Process operator or controller action with safety checks.

    Args:
        u_req: Requested setpoints
        scenario: Current scenario parameters
        events: Events dict to update (interlock/esd flags)
        source: Action source for logging ("operator" or "controller")
    """
    logger.info(f"Processing {source} action: {u_req}")

    u_cap = cap_moves(u_req, x)
    x_pred = plant.step(u=u_cap, scenario=scenario)
    safe = safety_logic(x_pred, u_cap)

    if safe["esd"]:
        events["esd"] = True
        st.error("ESD TRIGGERED — moving to safe state.")
        plant.esd_safe_state()
        logger.critical(f"ESD triggered on turn {st.session_state.turn} from {source} action")
    else:
        if safe["adjust"]:
            events["interlock"] = True
            u_adj = {
                "SP_F_Reflux": safe["adjust"].get("SP_F_Reflux", u_cap["SP_F_Reflux"]),
                "SP_F_Reboil": safe["adjust"].get("SP_F_Reboil", u_cap["SP_F_Reboil"]),
                "SP_F_ToTol":  u_cap["SP_F_ToTol"],
            }
            x_final = plant.step(u=u_adj, scenario=scenario)
            plant.commit(x_final)
            msg = " | ".join(safe["alarms"] + safe["interlock"])
            st.warning(msg if msg else "Interlock applied.")
            st.session_state.log.append(f"TURN {st.session_state.turn}: {msg}")
            logger.info(f"Interlock applied on turn {st.session_state.turn}: {msg}")
        else:
            plant.commit(x_pred)
            msg = " | ".join(safe["alarms"])
            if msg:
                st.warning(msg)
                st.session_state.log.append(f"TURN {st.session_state.turn}: {msg}")
                logger.info(f"Alarms on turn {st.session_state.turn}: {msg}")
            else:
                logger.info(f"Action completed successfully on turn {st.session_state.turn}")

    st.session_state.phase = "APPLIED"

# ---- Buttons ----
b1, b2, b3 = st.columns([1,1,1])
apply_click = b1.button("Apply Operator Action", disabled=locked)
ctrl_click  = b2.button("Let Controller Decide", disabled=locked)
next_click  = b3.button("Next Turn", disabled=(st.session_state.phase!="APPLIED"))

scenario = {"F_feed": F_feed, "zB_feed": zB_feed,
            "Fouling_Cond": fouling_cond/100.0, "Fouling_Reb": fouling_reb/100.0}

# ---- Handle actions ----
events = {"interlock": False, "esd": False}

if apply_click:
    u_req = {"SP_F_Reflux": SP_F_Reflux, "SP_F_Reboil": SP_F_Reboil, "SP_F_ToTol": SP_F_ToTol}
    process_action(u_req, scenario, events, "operator")

elif ctrl_click:
    # Controller proposes setpoints
    limits = {**CONTROLLER_LIMITS, "dP_max": LIMITS["dP_alarm"], "xB_spec": LIMITS["xB_spec"]}
    u_suggest = controller.decide(state=x, scenario=scenario, limits=limits)
    process_action(u_suggest, scenario, events, "controller")

elif next_click:
    logger.info(f"Advancing to turn {st.session_state.turn + 1}")
    st.session_state.turn += 1
    st.session_state.phase = "READY"
    st.rerun()

# ---- Process panel (static image + badges) ----
render_process_panel(state=plant.state, limits=LIMITS, events=events)

# ---- Event log ----
st.subheader("Event Log")
for line in st.session_state.log[-EVENT_LOG_LINES:][::-1]:
    st.text(line)
