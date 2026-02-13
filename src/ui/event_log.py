"""Event log display for alarms, interlocks, and operator actions."""

from __future__ import annotations

from typing import List, Dict

import streamlit as st


def render_event_log(log: List[Dict[str, str]], max_display: int = 20) -> None:
    """Render the event log as a scrollable list."""

    st.markdown("### Event Log")

    if not log:
        st.caption("No events recorded yet.")
        return

    recent = log[-max_display:]
    recent.reverse()

    for entry in recent:
        severity = entry.get("severity", "info")
        turn = entry.get("turn", "?")
        msg = entry.get("message", "")

        if severity == "esd":
            st.markdown(f"` T{turn} ` :red[**ESD** {msg}]")
        elif severity == "interlock":
            st.markdown(f"` T{turn} ` :orange[**INTLK** {msg}]")
        elif severity == "alarm":
            st.markdown(f"` T{turn} ` :orange[**ALARM** {msg}]")
        elif severity == "action":
            st.markdown(f"` T{turn} ` {msg}")
        else:
            st.markdown(f"` T{turn} ` {msg}")
