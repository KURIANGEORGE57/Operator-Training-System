"""Small layout utilities used across the Streamlit application."""

from __future__ import annotations

import streamlit as st


def render_header(title: str, subtitle: str | None = None) -> None:
    """Render a page header with an optional subtitle."""
    st.title(title)
    if subtitle:
        st.caption(subtitle)
