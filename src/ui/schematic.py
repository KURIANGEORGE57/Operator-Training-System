"""Process flow diagram rendered with Pillow."""

from __future__ import annotations

from typing import List

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

from src.models.plant_state import PlantState


# Color palette
BG = (15, 20, 35)
PIPE = (100, 140, 180)
EQUIP = (50, 70, 100)
EQUIP_BORDER = (80, 120, 160)
TEXT_COLOR = (200, 215, 235)
BADGE_AMBER = (245, 180, 50)
BADGE_ORANGE = (240, 120, 40)
BADGE_RED = (220, 50, 50)
GREEN = (50, 200, 100)
BLUE_ACCENT = (70, 130, 220)


def _draw_rounded_rect(draw, xy, radius, fill, outline):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = xy
    r = radius
    draw.rectangle([x0 + r, y0, x1 - r, y1], fill=fill)
    draw.rectangle([x0, y0 + r, x1, y1 - r], fill=fill)
    draw.pieslice([x0, y0, x0 + 2 * r, y0 + 2 * r], 180, 270, fill=fill)
    draw.pieslice([x1 - 2 * r, y0, x1, y0 + 2 * r], 270, 360, fill=fill)
    draw.pieslice([x0, y1 - 2 * r, x0 + 2 * r, y1], 90, 180, fill=fill)
    draw.pieslice([x1 - 2 * r, y1 - 2 * r, x1, y1], 0, 90, fill=fill)
    # Outline
    draw.arc([x0, y0, x0 + 2 * r, y0 + 2 * r], 180, 270, fill=outline, width=2)
    draw.arc([x1 - 2 * r, y0, x1, y0 + 2 * r], 270, 360, fill=outline, width=2)
    draw.arc([x0, y1 - 2 * r, x0 + 2 * r, y1], 90, 180, fill=outline, width=2)
    draw.arc([x1 - 2 * r, y1 - 2 * r, x1, y1], 0, 90, fill=outline, width=2)
    draw.line([x0 + r, y0, x1 - r, y0], fill=outline, width=2)
    draw.line([x0 + r, y1, x1 - r, y1], fill=outline, width=2)
    draw.line([x0, y0 + r, x0, y1 - r], fill=outline, width=2)
    draw.line([x1, y0 + r, x1, y1 - r], fill=outline, width=2)


def render_schematic(
    state: PlantState,
    alarms: List[str],
    interlock_active: bool,
    esd_triggered: bool,
) -> None:
    """Render the process flow diagram with status overlays."""

    W, H = 900, 520
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # --- Column (center tall rectangle) ---
    col_x, col_y = 350, 60
    col_w, col_h = 80, 340
    _draw_rounded_rect(
        draw,
        (col_x, col_y, col_x + col_w, col_y + col_h),
        12,
        EQUIP,
        EQUIP_BORDER,
    )
    # Column trays (horizontal lines)
    for i in range(1, 8):
        ty = col_y + i * (col_h // 8)
        draw.line(
            [col_x + 10, ty, col_x + col_w - 10, ty], fill=EQUIP_BORDER, width=1
        )
    draw.text((col_x + 10, col_y + 5), "COLUMN", fill=TEXT_COLOR)

    # --- Condenser (top right) ---
    cond_x, cond_y = 520, 40
    _draw_rounded_rect(
        draw, (cond_x, cond_y, cond_x + 100, cond_y + 50), 8, EQUIP, EQUIP_BORDER
    )
    draw.text((cond_x + 10, cond_y + 15), "CONDENSER", fill=TEXT_COLOR)

    # Overhead vapor pipe: column top -> condenser
    draw.line(
        [col_x + col_w, col_y + 25, cond_x, cond_y + 25], fill=PIPE, width=3
    )

    # --- Reflux Drum (right of condenser) ---
    drum_x, drum_y = 660, 35
    _draw_rounded_rect(
        draw,
        (drum_x, drum_y, drum_x + 120, drum_y + 60),
        15,
        EQUIP,
        EQUIP_BORDER,
    )
    draw.text((drum_x + 15, drum_y + 5), "REFLUX", fill=TEXT_COLOR)
    draw.text((drum_x + 20, drum_y + 22), "DRUM", fill=TEXT_COLOR)
    # Level indicator
    level_h = int(40 * state.L_Drum)
    draw.rectangle(
        [drum_x + 85, drum_y + 50 - level_h, drum_x + 105, drum_y + 50],
        fill=BLUE_ACCENT,
    )

    # Condenser -> drum pipe
    draw.line(
        [cond_x + 100, cond_y + 25, drum_x, drum_y + 30], fill=PIPE, width=3
    )

    # Reflux return pipe: drum bottom -> column top
    draw.line([drum_x + 60, drum_y + 60, drum_x + 60, 140], fill=PIPE, width=3)
    draw.line([drum_x + 60, 140, col_x + col_w, 140], fill=PIPE, width=3)

    # --- Reboiler (bottom) ---
    reb_x, reb_y = 320, 440
    _draw_rounded_rect(
        draw,
        (reb_x, reb_y, reb_x + 140, reb_y + 55),
        10,
        EQUIP,
        EQUIP_BORDER,
    )
    draw.text((reb_x + 15, reb_y + 8), "REBOILER", fill=TEXT_COLOR)
    # Flame indicator
    duty_pct = min(1.0, state.F_Reboil / 3.5)
    flame_color = (
        int(200 + 55 * duty_pct),
        int(100 + 80 * (1 - duty_pct)),
        30,
    )
    draw.ellipse(
        [reb_x + 100, reb_y + 20, reb_x + 130, reb_y + 45],
        fill=flame_color,
    )

    # Column bottom -> reboiler
    draw.line(
        [col_x + col_w // 2, col_y + col_h, col_x + col_w // 2, reb_y],
        fill=PIPE,
        width=3,
    )

    # --- Feed inlet (left) ---
    draw.line([150, 200, col_x, 200], fill=PIPE, width=3)
    draw.text((155, 185), "FEED", fill=GREEN)

    # --- Side draw (benzene product, left middle) ---
    draw.line([col_x, 280, 150, 280], fill=PIPE, width=3)
    draw.text((155, 265), "BENZENE", fill=GREEN)

    # --- Toluene transfer (bottom right) ---
    draw.line(
        [reb_x + 140, reb_y + 28, reb_x + 240, reb_y + 28], fill=PIPE, width=3
    )
    draw.text((reb_x + 150, reb_y + 10), "TOLUENE", fill=GREEN)

    # --- HUD: key values ---
    hud_y = 420
    hud_items = [
        f"xB: {state.xB_sd:.4f}",
        f"dP: {state.dP_col:.3f} bar",
        f"T: {state.T_top:.1f} C",
        f"Ref: {state.F_Reflux:.1f} t/h",
        f"Reb: {state.F_Reboil:.2f} MW",
        f"ToT: {state.F_ToTol:.1f} t/h",
    ]
    x_pos = 20
    for item in hud_items:
        draw.text((x_pos, H - 25), item, fill=TEXT_COLOR)
        x_pos += 145

    # --- Safety badges ---
    badge_y = col_y + 5
    if esd_triggered:
        _draw_badge(draw, 30, badge_y, "ESD ACTIVE", BADGE_RED)
    elif interlock_active:
        _draw_badge(draw, 30, badge_y, "INTERLOCK", BADGE_ORANGE)
    elif alarms:
        _draw_badge(draw, 30, badge_y, f"{len(alarms)} ALARM(S)", BADGE_AMBER)
    else:
        _draw_badge(draw, 30, badge_y, "NORMAL", GREEN)

    st.image(img, use_container_width=True)


def _draw_badge(draw, x, y, text, color):
    """Draw a status badge."""
    tw = len(text) * 9 + 20
    draw.rounded_rectangle([x, y, x + tw, y + 26], radius=6, fill=color)
    draw.text((x + 10, y + 5), text, fill=(0, 0, 0))
