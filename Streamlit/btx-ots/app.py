"""BTX Benzene Column — Turn-based Operator Training System.

Main Streamlit application wiring together the plant model, safety logic,
controllers, and process visualisation panel.
"""

import streamlit as st
import numpy as np
from typing import Dict

from plant_neqsim import PlantNeqSim
from ui.image_panel import render_process_panel

st.set_page_config("BTX Benzene Column — Turn-based OTS", layout="wide")

# ═══════════════════════════════════════════════════════════════════════════
# Session bootstrap
# ═══════════════════════════════════════════════════════════════════════════
if "plant" not in st.session_state:
    st.session_state.plant = PlantNeqSim()
if "turn" not in st.session_state:
    st.session_state.turn = 0
if "log" not in st.session_state:
    st.session_state.log = []
if "phase" not in st.session_state:
    st.session_state.phase = "READY"  # READY → APPLIED

plant: PlantNeqSim = st.session_state.plant

# ═══════════════════════════════════════════════════════════════════════════
# Safety thresholds
# ═══════════════════════════════════════════════════════════════════════════
LIMITS = {
    "dP_alarm":    0.30,
    "dP_trip":     0.33,
    "dP_esd":      0.34,
    "T_top_alarm": 100.0,
    "T_top_esd":   103.0,
    "xB_spec":     0.9990,
    "L_drum_min":  0.10,
    "L_drum_crit": 0.05,
}

# ═══════════════════════════════════════════════════════════════════════════
# Sidebar — scenario & controller selection
# ═══════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.header("Scenario")
    fouling_cond = st.slider("Condenser fouling (%)", 0, 60, 0, step=5)
    fouling_reb  = st.slider("Reboiler fouling (%)", 0, 60, 0, step=5)
    zB_feed      = st.slider("Feed benzene (mol frac)", 0.45, 0.75, 0.60, step=0.01)
    F_feed       = st.slider("Feed rate (t/h)", 50, 120, 80, step=1)
    controller_choice = st.selectbox("Controller", ["NN policy", "Linear MPC (2\u00d72)"])
    if st.button("Reset scenario"):
        st.session_state.plant = PlantNeqSim()
        st.session_state.turn = 0
        st.session_state.log = []
        st.session_state.phase = "READY"
        st.rerun()

# Lazy-import chosen controller
if controller_choice == "NN policy":
    from controllers.nn_controller import ControllerNN as Controller
else:
    from controllers.mpc_controller import ControllerMPC as Controller
controller = Controller()

# ═══════════════════════════════════════════════════════════════════════════
# Headline KPIs
# ═══════════════════════════════════════════════════════════════════════════
st.title("Benzene Column — Turn-based OTS")
x = plant.state
k1, k2, k3, k4 = st.columns(4)
k1.metric("Benzene purity (side-draw)", f"{x['xB_sd']:.5f}")
k2.metric("Column \u0394P (bar)", f"{x['dP_col']:.3f}")
k3.metric("Overhead T (\u00b0C)", f"{x['T_top']:.1f}")
k4.metric("Energy proxy (MW eq.)", f"{x['F_Reboil']:.2f}")

# ═══════════════════════════════════════════════════════════════════════════
# Control sliders
# ═══════════════════════════════════════════════════════════════════════════
locked = st.session_state.phase != "READY"
c1, c2, c3 = st.columns(3)
SP_F_Reflux = c1.slider("SP_F_Reflux (t/h)", 10.0, 45.0, float(x["F_Reflux"]), step=0.5, disabled=locked)
SP_F_Reboil = c2.slider("SP_F_Reboil (MW eq.)", 0.3, 3.5, float(x["F_Reboil"]), step=0.1, disabled=locked)
SP_F_ToTol  = c3.slider("SP_F_ToTol (t/h)", 30.0, 90.0, float(x["F_ToTol"]), step=0.5, disabled=locked)


# ═══════════════════════════════════════════════════════════════════════════
# Per-turn move-rate limiter
# ═══════════════════════════════════════════════════════════════════════════
def cap_moves(u_req: Dict, x_curr: Dict) -> Dict:
    caps = {"SP_F_Reflux": 2.0, "SP_F_Reboil": 0.15, "SP_F_ToTol": 5.0}
    u = u_req.copy()
    for sp_key, pv_key in [("SP_F_Reflux", "F_Reflux"), ("SP_F_Reboil", "F_Reboil"), ("SP_F_ToTol", "F_ToTol")]:
        u[sp_key] = float(np.clip(u[sp_key], x_curr[pv_key] - caps[sp_key], x_curr[pv_key] + caps[sp_key]))
    return u


# ═══════════════════════════════════════════════════════════════════════════
# Three-tier safety logic
# ═══════════════════════════════════════════════════════════════════════════
def safety_logic(x_next: Dict, u_applied: Dict) -> Dict:
    alarms, interlock = [], []
    adjust: Dict[str, float] = {}
    esd = False

    # Tier 1: Alarms
    if x_next["dP_col"] > LIMITS["dP_alarm"]:
        alarms.append("High column \u0394P")
    if x_next["T_top"] > LIMITS["T_top_alarm"]:
        alarms.append("High overhead T")
    if x_next["xB_sd"] < LIMITS["xB_spec"]:
        alarms.append("Off-spec benzene purity")
    if x_next.get("L_Drum", 0.5) < LIMITS["L_drum_min"]:
        alarms.append("Low reflux drum level")

    # Tier 2: Interlock (flooding)
    if x_next["dP_col"] > LIMITS["dP_trip"]:
        interlock.append("Flooding ILK: clamp reboil, increase reflux")
        adjust["SP_F_Reboil"] = max(u_applied["SP_F_Reboil"] - 0.2, 0.3)
        adjust["SP_F_Reflux"] = min(u_applied["SP_F_Reflux"] + 2.0, 45.0)

    # Tier 3: ESD
    if (
        x_next["dP_col"] > LIMITS["dP_esd"]
        or x_next["T_top"] > LIMITS["T_top_esd"]
        or x_next.get("L_Drum", 0.5) < LIMITS["L_drum_crit"]
    ):
        esd = True

    return {"alarms": alarms, "interlock": interlock, "adjust": adjust, "esd": esd}


# ═══════════════════════════════════════════════════════════════════════════
# Action buttons
# ═══════════════════════════════════════════════════════════════════════════
b1, b2, b3 = st.columns(3)
apply_click = b1.button("Apply Operator Action", disabled=locked)
ctrl_click  = b2.button("Let Controller Decide", disabled=locked)
next_click  = b3.button("Next Turn", disabled=(st.session_state.phase != "APPLIED"))

scenario = {
    "F_feed": F_feed,
    "zB_feed": zB_feed,
    "Fouling_Cond": fouling_cond / 100.0,
    "Fouling_Reb": fouling_reb / 100.0,
}


def apply_setpoints(u_cap: Dict, events: Dict) -> None:
    """Run safety logic and commit the resulting state."""
    x_pred = plant.step(u=u_cap, scenario=scenario)
    safe = safety_logic(x_pred, u_cap)

    if safe["esd"]:
        events["esd"] = True
        st.error("ESD TRIGGERED \u2014 moving to safe state.")
        plant.esd_safe_state()
    elif safe["adjust"]:
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
    else:
        plant.commit(x_pred)
        msg = " | ".join(safe["alarms"])
        if msg:
            st.warning(msg)
            st.session_state.log.append(f"TURN {st.session_state.turn}: {msg}")

    st.session_state.phase = "APPLIED"


# ═══════════════════════════════════════════════════════════════════════════
# Handle actions
# ═══════════════════════════════════════════════════════════════════════════
events = {"interlock": False, "esd": False}

if apply_click:
    u_req = {"SP_F_Reflux": SP_F_Reflux, "SP_F_Reboil": SP_F_Reboil, "SP_F_ToTol": SP_F_ToTol}
    u_cap = cap_moves(u_req, x)
    apply_setpoints(u_cap, events)

elif ctrl_click:
    limits = {
        "reflux": (10.0, 45.0), "reboil": (0.3, 3.5), "totol": (30.0, 90.0),
        "dP_max": LIMITS["dP_alarm"], "xB_spec": LIMITS["xB_spec"],
    }
    u_suggest = controller.decide(state=x, scenario=scenario, limits=limits)
    u_cap = cap_moves(u_suggest, x)
    apply_setpoints(u_cap, events)

elif next_click:
    st.session_state.turn += 1
    st.session_state.phase = "READY"
    st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# Process panel + event log
# ═══════════════════════════════════════════════════════════════════════════
render_process_panel(state=plant.state, limits=LIMITS, events=events)

st.subheader("Event Log")
for line in st.session_state.log[-15:][::-1]:
    st.text(line)
