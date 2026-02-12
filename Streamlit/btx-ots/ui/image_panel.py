"""Dynamic process schematic for the benzene column OTS.

Renders a simplified P&ID-style diagram using PIL and overlays live
status badges (alarm / interlock / ESD) based on the current plant state.
"""

from __future__ import annotations

from typing import Dict, Tuple

from PIL import Image, ImageDraw, ImageFont
import streamlit as st

# ═══════════════════════════════════════════════════════════════════════════
# Style constants
# ═══════════════════════════════════════════════════════════════════════════
CANVAS_W, CANVAS_H = 960, 1500
COLOR_BG        = (245, 247, 250, 255)
COLOR_STROKE    = (30, 30, 30, 255)
COLOR_TEXT      = (20, 20, 20, 255)
COLOR_PIPE      = (80, 80, 80, 255)
COLOR_FILL      = (230, 238, 248, 255)   # light blue fill for equipment
COLOR_ALARM     = (255, 160, 0, 255)     # amber
COLOR_ILK       = (240, 120, 0, 255)     # orange
COLOR_ESD       = (220, 0, 0, 255)       # red
COLOR_HUD_BG    = (10, 10, 30, 180)
COLOR_HUD_TXT   = (255, 255, 255, 230)
STROKE_W = 3

# ═══════════════════════════════════════════════════════════════════════════
# Equipment anchor positions — carefully spaced to avoid overlaps
#
# Layout (top → bottom):
#   y=100   Reflux Drum
#   y=195   Condenser
#   y=280   Column top
#   y=670   Column mid  (badges go here)
#   y=1060  Column bottom
#   y=1180  Reboiler (fired heater)
#   y=1320  Pumps (separate row, no overlap with reboiler)
# ═══════════════════════════════════════════════════════════════════════════
ANCHORS: Dict[str, Tuple[int, int]] = {
    "drum":        (480, 100),
    "condenser":   (480, 195),
    "column_top":  (480, 280),
    "column_bot":  (480, 1060),
    "reb_heater":  (480, 1180),
    "pump_reboil": (700, 1320),
    "pump_tol":    (260, 1320),
}

COL_W = 180  # column shell width (half = 90)


# ═══════════════════════════════════════════════════════════════════════════
# Font helper (cached by Streamlit across reruns)
# ═══════════════════════════════════════════════════════════════════════════
@st.cache_resource
def _font(size: int = 18) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default(size=size)


# ═══════════════════════════════════════════════════════════════════════════
# Drawing primitives
# ═══════════════════════════════════════════════════════════════════════════

def _pipe(draw: ImageDraw.ImageDraw, p1: Tuple[int, int], p2: Tuple[int, int], w: int = 5) -> None:
    draw.line([p1, p2], fill=COLOR_PIPE, width=w)


def _rect(draw: ImageDraw.ImageDraw, box, radius: int = 12, fill=COLOR_FILL, outline=COLOR_STROKE, width: int = STROKE_W) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _label(draw: ImageDraw.ImageDraw, xy: Tuple[int, int], txt: str, size: int = 17, color=COLOR_TEXT) -> None:
    draw.text(xy, txt, fill=color, font=_font(size))


def _centered_label(draw: ImageDraw.ImageDraw, center: Tuple[int, int], txt: str, size: int = 16, color=COLOR_TEXT) -> None:
    """Draw text horizontally centered on the given point."""
    font = _font(size)
    bbox = draw.textbbox((0, 0), txt, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((center[0] - tw // 2, center[1] - th // 2), txt, fill=color, font=font)


# ═══════════════════════════════════════════════════════════════════════════
# Badge (alarm / interlock / ESD indicator)
# ═══════════════════════════════════════════════════════════════════════════

def _badge(draw: ImageDraw.ImageDraw, xy: Tuple[int, int], level: str, text: str) -> None:
    """Draw a colour-coded circle + label bubble."""
    x, y = xy
    r = 16
    colour = {"ESD": COLOR_ESD, "ILK": COLOR_ILK}.get(level, COLOR_ALARM)

    # Circle
    draw.ellipse([x - r, y - r, x + r, y + r], fill=colour, outline=(255, 255, 255, 200), width=2)

    # Label bubble to the right
    font = _font(16)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2], bbox[3]
    pad = 6
    rx0 = x + r + 8
    ry0 = y - th // 2 - 3
    draw.rounded_rectangle(
        [rx0, ry0, rx0 + tw + 2 * pad, ry0 + th + 6],
        radius=6, fill=(255, 255, 255, 220),
    )
    draw.text((rx0 + pad, ry0 + 3), text, fill=(160, 0, 0, 255), font=font)


# ═══════════════════════════════════════════════════════════════════════════
# Equipment drawing
# ═══════════════════════════════════════════════════════════════════════════

def _draw_equipment(draw: ImageDraw.ImageDraw) -> None:
    top = ANCHORS["column_top"]
    bot = ANCHORS["column_bot"]
    c = ANCHORS["condenser"]
    d = ANCHORS["drum"]
    rb = ANCHORS["reb_heater"]
    pr = ANCHORS["pump_reboil"]
    pt = ANCHORS["pump_tol"]

    # ── Column shell ──
    hw = COL_W // 2
    _rect(draw, [top[0] - hw, top[1], top[0] + hw, bot[1]], radius=28)
    _centered_label(draw, (top[0], (top[1] + bot[1]) // 2), "COLUMN", size=20, color=(100, 100, 120, 200))

    # ── Condenser ──
    _rect(draw, [c[0] - 140, c[1] - 28, c[0] + 140, c[1] + 28], radius=8)
    _label(draw, (c[0] + 150, c[1] - 9), "Condenser")

    # ── Reflux drum (horizontal capsule) ──
    _rect(draw, [d[0] - 200, d[1] - 22, d[0] + 200, d[1] + 22], radius=22)
    _label(draw, (d[0] + 210, d[1] - 9), "Reflux Drum")

    # ── Reboiler (fired heater) ──
    _rect(draw, [rb[0] - 140, rb[1] - 32, rb[0] + 140, rb[1] + 32], radius=10)
    _centered_label(draw, (rb[0], rb[1] - 48), "Fired Heater (Reboiler)", size=17)

    # ── Pumps (separate row below reboiler — no overlap) ──
    _rect(draw, [pr[0] - 55, pr[1] - 22, pr[0] + 55, pr[1] + 22], radius=10)
    _centered_label(draw, (pr[0], pr[1] + 35), "Pump (Reb)", size=15)

    _rect(draw, [pt[0] - 55, pt[1] - 22, pt[0] + 55, pt[1] + 22], radius=10)
    _centered_label(draw, (pt[0], pt[1] + 35), "Pump (Tol)", size=15)

    # ── Piping ──
    # Overhead vapour → condenser
    _pipe(draw, (top[0], top[1]), (c[0], c[1] + 28))
    # Condenser → drum
    _pipe(draw, (c[0], c[1] - 28), (d[0], d[1] + 22))
    # Reflux return (drum → top tray region)
    _pipe(draw, (d[0] - 200, d[1]), (top[0] - hw, top[1] + 60))
    # Bottoms → reboiler
    _pipe(draw, (bot[0], bot[1]), (rb[0], rb[1] - 32))
    # Reboiler return → column
    _pipe(draw, (rb[0] + 140, rb[1]), (bot[0] + hw, bot[1] - 60))
    # Reboiler → reboiler pump
    _pipe(draw, (rb[0] + 140, rb[1] + 10), (pr[0], pr[1] - 22))
    # Bottoms → toluene pump
    _pipe(draw, (bot[0] - hw, bot[1] - 15), (pt[0], pt[1] - 22))


# ═══════════════════════════════════════════════════════════════════════════
# HUD overlay (live tag values)
# ═══════════════════════════════════════════════════════════════════════════

def _hud(draw: ImageDraw.ImageDraw, state: Dict) -> None:
    items = [
        f"xB_sd  = {state['xB_sd']:.5f}",
        f"dP_col = {state['dP_col']:.3f} bar",
        f"T_top  = {state['T_top']:.1f} \u00b0C",
        f"L_Drum = {state.get('L_Drum', 0.0):.2f}",
        f"F_Reflux = {state['F_Reflux']:.1f} t/h",
        f"F_Reboil = {state['F_Reboil']:.2f} MW",
        f"F_ToTol  = {state['F_ToTol']:.1f} t/h",
    ]
    font = _font(17)
    x0, y0 = 24, 24
    pad = 8
    line_h = 24
    w = max(font.getbbox(s)[2] for s in items) + 2 * pad
    h = line_h * len(items) + 2 * pad
    draw.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=10, fill=COLOR_HUD_BG)
    for i, s in enumerate(items):
        draw.text((x0 + pad, y0 + pad + i * line_h), s, fill=COLOR_HUD_TXT, font=font)


# ═══════════════════════════════════════════════════════════════════════════
# Public entry point
# ═══════════════════════════════════════════════════════════════════════════

def render_process_panel(state: Dict, limits: Dict, events: Dict | None = None) -> None:
    """Render the process schematic with live status badges into Streamlit."""
    img = Image.new("RGBA", (CANVAS_W, CANVAS_H), COLOR_BG)
    draw = ImageDraw.Draw(img)

    _draw_equipment(draw)

    # ── Badges based on live state vs limits ──

    col_mid_y = (ANCHORS["column_top"][1] + ANCHORS["column_bot"][1]) // 2
    col_mid = (ANCHORS["column_top"][0], col_mid_y)

    # Column ΔP
    if state["dP_col"] > limits["dP_esd"]:
        _badge(draw, col_mid, "ESD", "ESD: High \u0394P")
    elif state["dP_col"] > limits["dP_trip"]:
        _badge(draw, col_mid, "ILK", "Interlock: High \u0394P")
    elif state["dP_col"] > limits["dP_alarm"]:
        _badge(draw, col_mid, "ALARM", f"\u0394P {state['dP_col']:.2f} bar")

    # Overhead temperature (near condenser)
    if state["T_top"] > limits["T_top_esd"]:
        _badge(draw, ANCHORS["condenser"], "ESD", "ESD: High Overhead T")
    elif state["T_top"] > limits["T_top_alarm"]:
        _badge(draw, ANCHORS["condenser"], "ALARM", f"High T_top {state['T_top']:.1f}\u00b0C")

    # Reflux drum level
    drum_level = state.get("L_Drum", 0.5)
    if drum_level < limits["L_drum_crit"]:
        _badge(draw, ANCHORS["drum"], "ESD", "ESD: Drum Very Low")
    elif drum_level < limits["L_drum_min"]:
        _badge(draw, ANCHORS["drum"], "ALARM", "Low Drum Level")

    # Off-spec benzene purity (offset below condenser to avoid overlap)
    if state["xB_sd"] < limits["xB_spec"]:
        cond = ANCHORS["condenser"]
        _badge(draw, (cond[0], cond[1] + 50), "ALARM", f"Off-Spec xB {state['xB_sd']:.5f}")

    # Interlock / ESD event overlays
    if events and events.get("interlock"):
        _badge(draw, ANCHORS["reb_heater"], "ILK", "Interlock Active")
    if events and events.get("esd"):
        _badge(draw, (col_mid[0], col_mid[1] - 100), "ESD", "ESD TRIPPED")

    _hud(draw, state)

    st.image(img, use_container_width=True)
