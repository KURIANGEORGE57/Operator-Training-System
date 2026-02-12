# ui/image_panel.py
from __future__ import annotations
from typing import Dict, Tuple
from PIL import Image, ImageDraw, ImageFont
import streamlit as st

# === STYLE ===
CANVAS = (900, 1420)                    # (width, height) px
COLOR_BG = (255, 255, 255, 255)
COLOR_STROKE = (25, 25, 25, 255)
COLOR_TEXT = (20, 20, 20, 255)
COLOR_LINE = (60, 60, 60, 255)
COLOR_BADGE_ALARM = (255, 160, 0, 255)  # amber
COLOR_BADGE_ILK   = (240, 120, 0, 255)  # orange
COLOR_BADGE_ESD   = (220, 0, 0, 255)    # red
COLOR_HUD_BG = (0, 0, 0, 150)
COLOR_HUD_TXT = (255, 255, 255, 230)
THICK = 4

# equipment anchor points (relative layout)
ANCHORS: Dict[str, Tuple[int, int]] = {
    "column_top":  (450, 240),
    "column_bot":  (450, 1100),
    "condenser":   (450, 170),
    "drum":        (450, 110),
    "reb_heater":  (450, 1200),
    "pump_reboil": (650, 1310),
    "pump_tol":    (250, 1310),
}

@st.cache_resource
def _font(size=18):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default(size=size)

def _draw_badge(draw: ImageDraw.ImageDraw, xy: Tuple[int,int], level: str, text: str):
    """Draw circular badge with label: level in {'ALARM','ILK','ESD'}."""
    x, y = xy
    r = 18
    if level == "ESD":
        col = COLOR_BADGE_ESD
    elif level == "ILK":
        col = COLOR_BADGE_ILK
    else:
        col = COLOR_BADGE_ALARM
    draw.ellipse([x-r, y-r, x+r, y+r], fill=col, outline=(255,255,255,200), width=2)
    # label bubble
    font = _font(18)
    tw, th = draw.textbbox((0,0), text, font=font)[2:]
    pad = 8
    rect = [x + r + 10, y - th//2 - 4, x + r + 10 + tw + 2*pad, y + th//2 + 4]
    draw.rounded_rectangle(rect, radius=8, fill=(255,255,255,220), outline=None)
    draw.text((rect[0]+pad, y - th//2), text, fill=(180,0,0,255), font=font)

def _pipe(draw: ImageDraw.ImageDraw, p1: Tuple[int,int], p2: Tuple[int,int], width=6):
    draw.line([p1, p2], fill=COLOR_LINE, width=width)

def _rounded_rect(draw: ImageDraw.ImageDraw, box, radius=14, outline=COLOR_STROKE, fill=None, width=THICK):
    draw.rounded_rectangle(box, radius=radius, outline=outline, fill=fill, width=width)

def _label(draw: ImageDraw.ImageDraw, xy: Tuple[int,int], txt: str, color=COLOR_TEXT, size=20):
    draw.text(xy, txt, fill=color, font=_font(size))

def _draw_equipment(draw: ImageDraw.ImageDraw):
    # Column shell
    top = ANCHORS["column_top"]; bot = ANCHORS["column_bot"]
    col_w = 180
    _rounded_rect(draw, [top[0]-col_w//2, top[1], top[0]+col_w//2, bot[1]], radius=30)

    # Condenser (box)
    c = ANCHORS["condenser"]
    _rounded_rect(draw, [c[0]-150, c[1]-30, c[0]+150, c[1]+30], radius=10)
    _label(draw, (c[0]+160, c[1]-10), "Condenser", size=18)

    # Reflux Drum (horizontal capsule)
    d = ANCHORS["drum"]
    _rounded_rect(draw, [d[0]-220, d[1]-24, d[0]+220, d[1]+24], radius=24)
    _label(draw, (d[0]+240, d[1]-12), "Reflux Drum", size=18)

    # Reboiler (fired heater)
    r = ANCHORS["reb_heater"]
    _rounded_rect(draw, [r[0]-160, r[1]-35, r[0]+160, r[1]+35], radius=10)
    _label(draw, (r[0]-100, r[1]-55), "Fired Heater (Reboiler)", size=18)

    # Pumps
    pr = ANCHORS["pump_reboil"]
    pt = ANCHORS["pump_tol"]
    _rounded_rect(draw, [pr[0]-60, pr[1]-25, pr[0]+60, pr[1]+25], radius=12)
    _label(draw, (pr[0]-55, pr[1]+30), "Pump (Reboiler)", size=16)
    _rounded_rect(draw, [pt[0]-60, pt[1]-25, pt[0]+60, pt[1]+25], radius=12)
    _label(draw, (pt[0]-65, pt[1]+30), "Pump (Tol Tower)", size=16)

    # Basic piping
    # Overhead vapor to condenser to drum to reflux/overhead line hints
    _pipe(draw, (top[0], top[1]), (c[0], c[1]+30))
    _pipe(draw, (c[0], c[1]-30), (d[0], d[1]+24))
    # Reflux back to top tray region
    _pipe(draw, (d[0], d[1]-24), (top[0], top[1]+80))
    # Bottoms to reboiler loop
    _pipe(draw, (bot[0], bot[1]), (r[0], r[1]-35))
    _pipe(draw, (r[0], r[1]+35), (bot[0], bot[1]-80))
    # Reboiler to reboiler pump
    _pipe(draw, (r[0]+160, r[1]), (pr[0]-60, pr[1]))
    # Bottoms to toluene transfer pump
    _pipe(draw, (bot[0]-col_w//2, bot[1]-20), (pt[0], pt[1]-25))

def _hud(draw: ImageDraw.ImageDraw, state: Dict):
    items = [
        f"xB_sd = {state['xB_sd']:.5f}",
        f"dP_col = {state['dP_col']:.3f} bar",
        f"T_top = {state['T_top']:.1f} °C",
        f"L_Drum = {state.get('L_Drum',0.0):.2f}",
        f"F_Reflux = {state['F_Reflux']:.1f} t/h",
        f"F_Reboil = {state['F_Reboil']:.2f} MW",
        f"F_ToTol = {state['F_ToTol']:.1f} t/h",
    ]
    x0, y0 = 28, 28
    pad = 8
    line_h = 26
    w = max([_font(18).getbbox(s)[2] for s in items]) + 2*pad
    h = line_h*len(items) + 2*pad
    draw.rounded_rectangle([x0, y0, x0+w, y0+h], radius=10, fill=COLOR_HUD_BG)
    for i, s in enumerate(items):
        draw.text((x0+pad, y0+pad + i*line_h), s, fill=COLOR_HUD_TXT, font=_font(18))

def render_process_panel(state: Dict, limits: Dict, events: Dict | None = None):
    """
    Auto-draw a simplified benzene column schematic and overlay status badges.
    Args:
        state: dict with keys xB_sd, dP_col, T_top, L_Drum, F_Reflux, F_Reboil, F_ToTol
        limits: dict with keys dP_alarm, dP_trip, dP_esd, T_top_alarm, T_top_esd, xB_spec, L_drum_min, L_drum_crit
        events: optional flags {'interlock': bool, 'esd': bool}
    """
    img = Image.new("RGBA", CANVAS, COLOR_BG)
    draw = ImageDraw.Draw(img)

    # Equipment & pipes
    _draw_equipment(draw)

    # --- BADGES based on current state/limits ---
    # Column ΔP (place mid-column)
    col_mid = (ANCHORS["column_top"][0], (ANCHORS["column_top"][1]+ANCHORS["column_bot"][1])//2)
    if state["dP_col"] >= limits["dP_esd"]:
        _draw_badge(draw, col_mid, "ESD", "ESD: High ΔP")
    elif state["dP_col"] >= limits["dP_trip"]:
        _draw_badge(draw, col_mid, "ILK", "Interlock: High ΔP")
    elif state["dP_col"] >= limits["dP_alarm"]:
        _draw_badge(draw, col_mid, "ALARM", f"ΔP {state['dP_col']:.2f} bar")

    # Overhead temperature near condenser
    if state["T_top"] >= limits["T_top_esd"]:
        _draw_badge(draw, ANCHORS["condenser"], "ESD", "ESD: High Overhead T")
    elif state["T_top"] >= limits["T_top_alarm"]:
        _draw_badge(draw, ANCHORS["condenser"], "ALARM", f"High T_top {state['T_top']:.1f}°C")

    # Reflux drum level
    if state.get("L_Drum", 0.5) <= limits["L_drum_crit"]:
        _draw_badge(draw, ANCHORS["drum"], "ESD", "ESD: Reflux Drum Very Low")
    elif state.get("L_Drum", 0.5) <= limits["L_drum_min"]:
        _draw_badge(draw, ANCHORS["drum"], "ALARM", "Low Reflux Drum Level")

    # Off-spec benzene purity (offset below condenser to avoid overlap with T_top badge)
    if state["xB_sd"] < limits["xB_spec"]:
        cond = ANCHORS["condenser"]
        _draw_badge(draw, (cond[0], cond[1] + 50), "ALARM", f"Off-Spec xB {state['xB_sd']:.5f}")

    # Interlock/ESD event overlays
    if events and events.get("interlock"):
        _draw_badge(draw, ANCHORS["reb_heater"], "ILK", "Interlock Active")
    if events and events.get("esd"):
        _draw_badge(draw, (col_mid[0], col_mid[1]-120), "ESD", "ESD TRIPPED")

    # HUD tiles with live tags
    _hud(draw, state)

    # Render to Streamlit
    st.image(img, use_container_width=True)
