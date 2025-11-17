"""Heat Exchanger Operator Training System

A turn-based training simulator for shell-and-tube heat exchanger operation
with realistic what-if scenarios and safety systems.
"""

import streamlit as st
import numpy as np
from typing import Dict
from plant_hx import PlantHeatExchanger

st.set_page_config("Heat Exchanger OTS", layout="wide")

# ============================================================================
# Session State Initialization
# ============================================================================
if "plant" not in st.session_state:
    st.session_state.plant = PlantHeatExchanger()
if "turn" not in st.session_state:
    st.session_state.turn = 0
if "log" not in st.session_state:
    st.session_state.log = []
if "phase" not in st.session_state:
    st.session_state.phase = "READY"  # READY -> APPLIED

plant: PlantHeatExchanger = st.session_state.plant

# ============================================================================
# Safety Thresholds
# ============================================================================
LIMITS = {
    # Temperature limits
    "T_hot_out_alarm": 140.0,
    "T_hot_out_esd": 150.0,
    "T_cold_out_alarm": 55.0,
    "T_cold_out_esd": 60.0,

    # Pressure drop limits
    "dP_hot_alarm": 2.0,
    "dP_hot_esd": 2.5,
    "dP_cold_alarm": 1.2,
    "dP_cold_esd": 1.5,

    # Flow limits
    "F_hot_min": 10.0,
    "F_cold_min": 15.0,

    # Fouling limits
    "fouling_alarm": 0.50,  # 50%
    "fouling_critical": 0.75,  # 75%

    # Tube leak limits
    "tube_leak_alarm": 0.10,  # 10%
    "tube_leak_critical": 0.30,  # 30%

    # Temperature approach (efficiency indicator)
    "approach_temp_min": 5.0,  # Minimum approach temperature (°C)
}

# ============================================================================
# Safety Logic
# ============================================================================
def safety_logic(x_next: Dict, u_applied: Dict) -> Dict:
    """Three-tier safety system for heat exchanger.

    Returns:
        dict with alarms, interlock, adjust, and esd flags
    """
    alarms, interlock, esd = [], [], False
    adjust = {}

    # Tier 1: Alarms
    if x_next["T_hot_out"] > LIMITS["T_hot_out_alarm"]:
        alarms.append("High hot outlet temperature")
    if x_next["T_cold_out"] > LIMITS["T_cold_out_alarm"]:
        alarms.append("High cold outlet temperature")
    if x_next["dP_hot"] > LIMITS["dP_hot_alarm"]:
        alarms.append("High hot side pressure drop")
    if x_next["dP_cold"] > LIMITS["dP_cold_alarm"]:
        alarms.append("High cold side pressure drop")
    if x_next["F_hot"] < LIMITS["F_hot_min"]:
        alarms.append("Low hot side flow")
    if x_next["F_cold"] < LIMITS["F_cold_min"]:
        alarms.append("Low cold side flow")
    if x_next["fouling_hot"] > LIMITS["fouling_alarm"]:
        alarms.append("High hot side fouling")
    if x_next["fouling_cold"] > LIMITS["fouling_alarm"]:
        alarms.append("High cold side fouling")
    if x_next["tube_leak"] > LIMITS["tube_leak_alarm"]:
        alarms.append("Tube leakage detected")

    # Temperature approach check
    approach_temp = min(
        x_next["T_hot_out"] - x_next["T_cold_in"],
        x_next["T_cold_out"] - x_next["T_cold_in"]
    )
    if approach_temp < LIMITS["approach_temp_min"]:
        alarms.append("Low temperature approach - poor heat transfer")

    # Tier 2: Interlocks
    # High pressure drop interlock - increase cold flow to improve heat transfer
    if x_next["dP_hot"] > (LIMITS["dP_hot_alarm"] + 0.3):
        interlock.append("High ΔP interlock: increase cold flow, reduce hot flow")
        adjust["SP_F_hot"] = max(u_applied["SP_F_hot"] - 5.0, LIMITS["F_hot_min"])
        adjust["SP_F_cold"] = min(u_applied["SP_F_cold"] + 10.0, 100.0)

    # High temperature interlock - increase cooling
    if x_next["T_hot_out"] > (LIMITS["T_hot_out_alarm"] + 5.0):
        interlock.append("High temp interlock: increase cold flow")
        adjust["SP_F_cold"] = min(
            u_applied.get("SP_F_cold", 50.0) + 15.0, 100.0
        )

    # Severe fouling interlock - reduce flows to prevent damage
    if (x_next["fouling_hot"] > LIMITS["fouling_critical"] or
        x_next["fouling_cold"] > LIMITS["fouling_critical"]):
        interlock.append("Critical fouling interlock: reduce flows")
        adjust["SP_F_hot"] = max(u_applied["SP_F_hot"] * 0.7, LIMITS["F_hot_min"])
        adjust["SP_F_cold"] = max(u_applied["SP_F_cold"] * 0.7, LIMITS["F_cold_min"])

    # Tier 3: Emergency Shutdown
    if (x_next["T_hot_out"] > LIMITS["T_hot_out_esd"] or
        x_next["T_cold_out"] > LIMITS["T_cold_out_esd"] or
        x_next["dP_hot"] > LIMITS["dP_hot_esd"] or
        x_next["dP_cold"] > LIMITS["dP_cold_esd"] or
        x_next["tube_leak"] > LIMITS["tube_leak_critical"]):
        esd = True

    return {"alarms": alarms, "interlock": interlock, "adjust": adjust, "esd": esd}


def cap_moves(u_req: Dict, x_curr: Dict) -> Dict:
    """Rate limit control changes to prevent thermal shock.

    Max changes per turn:
    - Hot flow: ±5.0 kg/s
    - Cold flow: ±10.0 kg/s
    """
    caps = {"SP_F_hot": 5.0, "SP_F_cold": 10.0}
    u = u_req.copy()

    u["SP_F_hot"] = float(np.clip(
        u["SP_F_hot"],
        x_curr["F_hot"] - caps["SP_F_hot"],
        x_curr["F_hot"] + caps["SP_F_hot"]
    ))
    u["SP_F_cold"] = float(np.clip(
        u["SP_F_cold"],
        x_curr["F_cold"] - caps["SP_F_cold"],
        x_curr["F_cold"] + caps["SP_F_cold"]
    ))

    return u


# ============================================================================
# Sidebar: What-If Scenarios
# ============================================================================
with st.sidebar:
    st.header("🔬 What-If Scenario")

    st.subheader("Feed Conditions")
    T_hot_in_feed = st.slider(
        "Hot inlet temperature (°C)", 80, 180, 120, step=5
    )
    T_cold_in_feed = st.slider(
        "Cold inlet temperature (°C)", 15, 40, 25, step=1
    )

    st.subheader("Fouling (Slow Drift)")
    fouling_hot_rate = st.slider(
        "Hot side fouling rate (%/turn)", 0, 10, 0, step=1
    )
    fouling_cold_rate = st.slider(
        "Cold side fouling rate (%/turn)", 0, 10, 0, step=1
    )

    st.subheader("Failures")
    tube_leak_severity = st.slider(
        "Tube leak severity (%)", 0, 50, 0, step=5
    ) / 100.0

    col1, col2 = st.columns(2)
    hot_pump_trip = col1.checkbox("Hot pump trip")
    cold_pump_trip = col2.checkbox("Cold pump trip")

    st.divider()

    if st.button("🔄 Reset Scenario"):
        st.session_state.plant = PlantHeatExchanger()
        st.session_state.turn = 0
        st.session_state.log = []
        st.session_state.phase = "READY"
        st.rerun()

# ============================================================================
# Main Display
# ============================================================================
st.title("🔥 Heat Exchanger — Operator Training System")

# Current state
x = plant.state

# KPI Metrics
col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Hot Outlet",
    f"{x['T_hot_out']:.1f} °C",
    f"{x['T_hot_out'] - 60.0:+.1f}",
    delta_color="inverse"
)
col2.metric(
    "Cold Outlet",
    f"{x['T_cold_out']:.1f} °C",
    f"{x['T_cold_out'] - 45.0:+.1f}",
)
col3.metric(
    "Heat Duty",
    f"{x['Q_duty']:.0f} kW",
    f"{x['Q_duty'] - 7560.0:+.0f}",
)
col4.metric(
    "Effectiveness",
    f"{100.0 * x['Q_duty'] / max((x['F_hot'] * 4.2 * (x['T_hot_in'] - x['T_cold_in'])), 1.0):.1f}%",
)

st.divider()

# Control Panel
st.subheader("⚙️ Operator Controls")
locked = st.session_state.phase != "READY"

col1, col2 = st.columns(2)
SP_F_hot = col1.slider(
    "Hot side flow (kg/s)",
    10.0, 80.0, float(x["F_hot"]), step=1.0,
    disabled=locked
)
SP_F_cold = col2.slider(
    "Cold side flow (kg/s)",
    15.0, 120.0, float(x["F_cold"]), step=1.0,
    disabled=locked
)

# Action Buttons
col1, col2 = st.columns([1, 1])
apply_click = col1.button(
    "✅ Apply Operator Action",
    disabled=locked,
    use_container_width=True
)
next_click = col2.button(
    "➡️ Next Turn",
    disabled=(st.session_state.phase != "APPLIED"),
    use_container_width=True
)

# Build scenario dict
scenario = {
    "T_hot_in_feed": T_hot_in_feed,
    "T_cold_in_feed": T_cold_in_feed,
    "fouling_hot_rate": fouling_hot_rate,
    "fouling_cold_rate": fouling_cold_rate,
    "tube_leak_severity": tube_leak_severity,
    "hot_pump_trip": 1 if hot_pump_trip else 0,
    "cold_pump_trip": 1 if cold_pump_trip else 0,
}

events = {"interlock": False, "esd": False}

# ============================================================================
# Action Handlers
# ============================================================================
if apply_click:
    u_req = {"SP_F_hot": SP_F_hot, "SP_F_cold": SP_F_cold}
    u_cap = cap_moves(u_req, x)
    x_pred = plant.step(u=u_cap, scenario=scenario)
    safe = safety_logic(x_pred, u_cap)

    if safe["esd"]:
        events["esd"] = True
        st.error("🚨 EMERGENCY SHUTDOWN TRIGGERED — Moving to safe state")
        plant.esd_safe_state()
        st.session_state.log.append(
            f"TURN {st.session_state.turn}: ESD - " + " | ".join(safe["alarms"])
        )
    else:
        if safe["adjust"]:
            events["interlock"] = True
            u_adj = {
                "SP_F_hot": safe["adjust"].get("SP_F_hot", u_cap["SP_F_hot"]),
                "SP_F_cold": safe["adjust"].get("SP_F_cold", u_cap["SP_F_cold"]),
            }
            x_final = plant.step(u=u_adj, scenario=scenario)
            plant.commit(x_final)
            msg = " | ".join(safe["alarms"] + safe["interlock"])
            st.warning(f"⚠️ {msg if msg else 'Interlock applied'}")
            st.session_state.log.append(f"TURN {st.session_state.turn}: {msg}")
        else:
            plant.commit(x_pred)
            msg = " | ".join(safe["alarms"])
            if msg:
                st.warning(f"⚠️ {msg}")
                st.session_state.log.append(f"TURN {st.session_state.turn}: {msg}")

    st.session_state.phase = "APPLIED"
    st.rerun()

elif next_click:
    st.session_state.turn += 1
    st.session_state.phase = "READY"
    st.rerun()

# ============================================================================
# Process Visualization
# ============================================================================
st.divider()
st.subheader("🏭 Process Status")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### Temperatures")
    st.write(f"**Hot Side:**")
    st.write(f"  • Inlet: {x['T_hot_in']:.1f} °C")
    st.write(f"  • Outlet: {x['T_hot_out']:.1f} °C")
    st.write(f"  • ΔT: {x['T_hot_in'] - x['T_hot_out']:.1f} °C")

    st.write(f"**Cold Side:**")
    st.write(f"  • Inlet: {x['T_cold_in']:.1f} °C")
    st.write(f"  • Outlet: {x['T_cold_out']:.1f} °C")
    st.write(f"  • ΔT: {x['T_cold_out'] - x['T_cold_in']:.1f} °C")

with col2:
    st.markdown("### Hydraulics")
    st.write(f"**Flows:**")
    st.write(f"  • Hot: {x['F_hot']:.1f} kg/s")
    st.write(f"  • Cold: {x['F_cold']:.1f} kg/s")

    st.write(f"**Pressure Drops:**")
    st.write(f"  • Hot: {x['dP_hot']:.2f} bar")
    st.write(f"  • Cold: {x['dP_cold']:.2f} bar")

with col3:
    st.markdown("### Equipment Health")
    st.write(f"**Fouling:**")
    fouling_hot_pct = x['fouling_hot'] * 100
    fouling_cold_pct = x['fouling_cold'] * 100
    st.write(f"  • Hot side: {fouling_hot_pct:.1f}%")
    st.write(f"  • Cold side: {fouling_cold_pct:.1f}%")

    st.write(f"**Tube Condition:**")
    tube_leak_pct = x['tube_leak'] * 100
    if tube_leak_pct > 1.0:
        st.write(f"  • ⚠️ Leak: {tube_leak_pct:.1f}%")
    else:
        st.write(f"  • ✅ Integrity OK")

# Simple ASCII schematic
st.divider()
st.subheader("📊 Process Schematic")

# Color coding based on status
hot_temp_color = "🔴" if x['T_hot_out'] > LIMITS['T_hot_out_alarm'] else "🟢"
cold_temp_color = "🔴" if x['T_cold_out'] > LIMITS['T_cold_out_alarm'] else "🟢"
hot_dp_color = "🔴" if x['dP_hot'] > LIMITS['dP_hot_alarm'] else "🟢"
cold_dp_color = "🔴" if x['dP_cold'] > LIMITS['dP_cold_alarm'] else "🟢"

st.code(f"""
    HOT FLUID (Process)                COLD FLUID (Cooling Water)

    {x['T_hot_in']:.1f}°C ──────────────────────►  ◄────────────────────── {x['T_cold_in']:.1f}°C
    {x['F_hot']:.1f} kg/s         ╔═══════════╗          {x['F_cold']:.1f} kg/s
                              ║           ║
                              ║   SHELL   ║  {hot_temp_color} Hot: {x['T_hot_out']:.1f}°C
                              ║    AND    ║  {cold_temp_color} Cold: {x['T_cold_out']:.1f}°C
                              ║   TUBE    ║
                              ║    H/X    ║  {hot_dp_color} ΔP_hot: {x['dP_hot']:.2f} bar
                              ║           ║  {cold_dp_color} ΔP_cold: {x['dP_cold']:.2f} bar
                              ╚═══════════╝
                                   ▼              ▼
    {x['T_hot_out']:.1f}°C ◄────────────────────────  ────────────────────► {x['T_cold_out']:.1f}°C

    Heat Duty: {x['Q_duty']:.0f} kW
    Fouling: Hot {fouling_hot_pct:.0f}% | Cold {fouling_cold_pct:.0f}%
""", language="text")

# ============================================================================
# Event Log
# ============================================================================
st.divider()
st.subheader("📋 Event Log")
st.caption(f"Turn: {st.session_state.turn}")

if st.session_state.log:
    for line in st.session_state.log[-10:][::-1]:
        st.text(line)
else:
    st.info("No events logged yet. Start operating the heat exchanger!")

# ============================================================================
# Help & Information
# ============================================================================
with st.expander("ℹ️ Operating Guide"):
    st.markdown("""
    ### Heat Exchanger Operation

    **Objective:** Maintain safe and efficient heat transfer operation

    **Key Parameters:**
    - **Hot Outlet Temperature**: Keep below 140°C (alarm at 140°C, ESD at 150°C)
    - **Cold Outlet Temperature**: Keep below 55°C (alarm at 55°C, ESD at 60°C)
    - **Pressure Drops**: Monitor fouling (high ΔP indicates fouling)
    - **Heat Duty**: Maximize while staying within safety limits

    **What-If Scenarios:**
    1. **Fouling**: Gradually reduces heat transfer, increases ΔP
       - *Action*: Increase flows or schedule cleaning
    2. **Tube Leak**: Hot fluid contaminates cold side
       - *Action*: Reduce flows, isolate unit for repair
    3. **Pump Trip**: Loss of flow causes poor heat transfer
       - *Action*: Restart pump or switch to backup
    4. **High Inlet Temperature**: Can cause outlet temp alarms
       - *Action*: Increase cold flow to compensate

    **Safety System:**
    - **Alarms**: Early warnings (yellow)
    - **Interlocks**: Automatic protective actions (orange)
    - **ESD**: Emergency shutdown for critical conditions (red)

    **Rate Limits:**
    - Hot flow: ±5 kg/s per turn (prevent thermal shock)
    - Cold flow: ±10 kg/s per turn
    """)
