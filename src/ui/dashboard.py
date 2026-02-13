"""KPI dashboard with real-time metric display."""

from __future__ import annotations

import streamlit as st

from src.models.constants import LIMITS
from src.models.plant_state import PlantState
from src.scoring.tracker import ScoreTracker


def render_dashboard(state: PlantState, scorer: ScoreTracker) -> None:
    """Render the top KPI bar with key process metrics."""

    st.markdown("### Key Process Indicators")

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        xB_delta = state.xB_sd - LIMITS.xB_spec
        st.metric(
            "Benzene Purity",
            f"{state.xB_sd:.4f}",
            delta=f"{xB_delta:+.4f}",
            delta_color="normal" if xB_delta >= 0 else "inverse",
        )

    with c2:
        st.metric(
            "Column dP",
            f"{state.dP_col:.3f} bar",
            delta=f"{state.dP_col - 0.08:+.3f}",
            delta_color="inverse",
        )

    with c3:
        st.metric(
            "Overhead T",
            f"{state.T_top:.1f} C",
            delta=f"{state.T_top - 84.5:+.1f}",
            delta_color="inverse",
        )

    with c4:
        st.metric(
            "Drum Level",
            f"{state.L_Drum:.2f}",
            delta=f"{state.L_Drum - 0.50:+.2f}",
            delta_color="normal",
        )

    with c5:
        avg = scorer.average_score
        grade = scorer.overall_grade
        st.metric("Score", f"{avg:.0f} ({grade})")
