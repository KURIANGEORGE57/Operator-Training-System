"""Operator control panel: sliders and action buttons."""

from __future__ import annotations

from typing import Dict, Tuple

import streamlit as st

from src.models.constants import ACTUATOR_RANGES
from src.models.plant_state import PlantState


def render_controls(state: PlantState) -> Tuple[Dict[str, float], str]:
    """Render control sliders and action buttons.

    Returns:
        (setpoints_dict, action) where action is one of:
        "apply", "controller", "next", or "none".
    """

    st.markdown("### Operator Controls")

    c1, c2, c3 = st.columns(3)

    rr_lo, rr_hi = ACTUATOR_RANGES["SP_F_Reflux"]
    with c1:
        sp_reflux = st.slider(
            "Reflux Flow (t/h)",
            min_value=rr_lo,
            max_value=rr_hi,
            value=round(state.F_Reflux, 1),
            step=0.5,
            key="slider_reflux",
        )

    qr_lo, qr_hi = ACTUATOR_RANGES["SP_F_Reboil"]
    with c2:
        sp_reboil = st.slider(
            "Reboiler Duty (MW)",
            min_value=qr_lo,
            max_value=qr_hi,
            value=round(state.F_Reboil, 2),
            step=0.05,
            key="slider_reboil",
        )

    tt_lo, tt_hi = ACTUATOR_RANGES["SP_F_ToTol"]
    with c3:
        sp_totol = st.slider(
            "Toluene Transfer (t/h)",
            min_value=tt_lo,
            max_value=tt_hi,
            value=round(state.F_ToTol, 1),
            step=1.0,
            key="slider_totol",
        )

    setpoints = {
        "SP_F_Reflux": sp_reflux,
        "SP_F_Reboil": sp_reboil,
        "SP_F_ToTol": sp_totol,
    }

    b1, b2, b3 = st.columns(3)
    action = "none"

    with b1:
        if st.button("Apply Operator Move", type="primary", use_container_width=True):
            action = "apply"
    with b2:
        if st.button("Let Controller Decide", use_container_width=True):
            action = "controller"
    with b3:
        if st.button("Advance Turn (Hold)", use_container_width=True):
            action = "next"

    return setpoints, action
