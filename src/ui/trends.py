"""Historical trend charts for key process variables."""

from __future__ import annotations

from typing import List, Dict

import streamlit as st
import pandas as pd

from src.models.constants import LIMITS


def render_trends(history: List[Dict[str, float]]) -> None:
    """Render trend charts from plant state history."""

    if len(history) < 2:
        st.info("Trend charts will appear after 2+ turns.")
        return

    df = pd.DataFrame(history)
    df.index.name = "Turn"

    st.markdown("### Process Trends")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Benzene Purity (xB)**")
        purity_df = df[["xB_sd"]].copy()
        purity_df["Spec"] = LIMITS.xB_spec
        st.line_chart(purity_df, height=200)

    with c2:
        st.markdown("**Column dP (bar)**")
        dp_df = df[["dP_col"]].copy()
        dp_df["Alarm"] = LIMITS.dP_alarm
        dp_df["Interlock"] = LIMITS.dP_interlock
        st.line_chart(dp_df, height=200)

    c3, c4 = st.columns(2)

    with c3:
        st.markdown("**Overhead Temperature (C)**")
        t_df = df[["T_top"]].copy()
        t_df["Alarm"] = LIMITS.T_top_alarm
        st.line_chart(t_df, height=200)

    with c4:
        st.markdown("**Levels**")
        lvl_df = df[["L_Drum", "L_Bot"]].copy()
        lvl_df["Low Alarm"] = LIMITS.L_drum_alarm
        st.line_chart(lvl_df, height=200)


def render_score_trend(scores: List[float]) -> None:
    """Render the score history chart."""

    if len(scores) < 2:
        return

    st.markdown("### Performance Trend")
    df = pd.DataFrame({"Score": scores})
    df.index.name = "Turn"
    st.line_chart(df, height=180)
