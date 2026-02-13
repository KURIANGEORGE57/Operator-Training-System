"""Process flow diagram rendered as interactive SVG.

Produces a crisp, DCS-style vector schematic of the benzene-toluene
distillation column with animated flow lines, instrument tags, and
real-time safety status.
"""

from __future__ import annotations

from typing import List

import streamlit as st
import streamlit.components.v1 as components

from src.models.plant_state import PlantState


def render_schematic(
    state: PlantState,
    alarms: List[str],
    interlock_active: bool,
    esd_triggered: bool,
) -> None:
    """Render the process flow diagram as an SVG with animated flows."""

    # Dynamic calculations
    drum_level = max(0.0, min(1.0, state.L_Drum))
    duty_pct = min(1.0, state.F_Reboil / 3.5)

    # Flame color based on reboiler duty
    flame_r = int(200 + 55 * duty_pct)
    flame_g = int(80 + 100 * (1 - duty_pct))
    flame_color = f"rgb({flame_r},{flame_g},30)"
    flame_color2 = f"rgb({min(255, flame_r + 30)},{min(255, flame_g + 40)},60)"
    flame_opacity = f"{0.4 + 0.6 * duty_pct:.2f}"

    # Safety badge
    if esd_triggered:
        badge_text = "ESD ACTIVE"
        badge_color = "#dc3545"
        badge_animate = True
    elif interlock_active:
        badge_text = "INTERLOCK"
        badge_color = "#f07828"
        badge_animate = True
    elif alarms:
        badge_text = f"{len(alarms)} ALARM(S)"
        badge_color = "#f5b432"
        badge_animate = True
    else:
        badge_text = "NORMAL"
        badge_color = "#32c864"
        badge_animate = False

    badge_w = len(badge_text) * 9 + 28
    pulse_class = ' class="badge-pulse"' if badge_animate else ""

    # Drum level geometry
    drum_x, drum_y, drum_w, drum_h = 720, 30, 155, 68
    level_fill_y = drum_y + drum_h * (1 - drum_level)
    level_fill_h = drum_h * drum_level

    svg_html = f"""<!DOCTYPE html>
<html><head><style>
body {{ margin:0; padding:0; background:transparent; overflow:hidden; }}

@keyframes flowRight {{
  from {{ stroke-dashoffset: 24; }} to {{ stroke-dashoffset: 0; }}
}}
@keyframes flowLeft {{
  from {{ stroke-dashoffset: -24; }} to {{ stroke-dashoffset: 0; }}
}}
@keyframes flowDown {{
  from {{ stroke-dashoffset: 24; }} to {{ stroke-dashoffset: 0; }}
}}
@keyframes pulse {{
  0%,100% {{ opacity:1; }} 50% {{ opacity:0.55; }}
}}
@keyframes flicker {{
  0%,100% {{ transform:scaleY(1) scaleX(1); }}
  33%     {{ transform:scaleY(1.1) scaleX(0.94); }}
  66%     {{ transform:scaleY(0.92) scaleX(1.06); }}
}}

.pipe {{
  fill:none; stroke:#5a8ab4; stroke-width:4;
  stroke-linecap:round; stroke-linejoin:round;
}}
.pipe-product {{
  fill:none; stroke:#3cc868; stroke-width:4;
  stroke-linecap:round; stroke-linejoin:round;
}}
.pipe-feed {{
  fill:none; stroke:#5ab480; stroke-width:4;
  stroke-linecap:round; stroke-linejoin:round;
}}
.flow-r {{ stroke-dasharray:12 12; animation:flowRight .8s linear infinite; }}
.flow-l {{ stroke-dasharray:12 12; animation:flowLeft .8s linear infinite; }}
.flow-d {{ stroke-dasharray:12 12; animation:flowDown .8s linear infinite; }}
.equip-label {{
  font-family:'Segoe UI',Arial,sans-serif; font-size:11px;
  font-weight:600; fill:#c8d8e8; letter-spacing:.5px;
}}
.equip-sub {{
  font-family:monospace; font-size:8px; fill:#5a7a98;
}}
.stream-label {{
  font-family:'Segoe UI',Arial,sans-serif; font-size:11px;
  font-weight:700; letter-spacing:.5px;
}}
.tag-box {{ fill:#0c1525; stroke:#3a5a7a; stroke-width:1; }}
.tag-name {{
  font-family:'Consolas','Courier New',monospace;
  font-size:9px; fill:#7a9ab8;
}}
.tag-value {{
  font-family:'Consolas','Courier New',monospace;
  font-size:12px; font-weight:700; fill:#e0f0ff;
}}
.tag-unit {{
  font-family:'Consolas','Courier New',monospace;
  font-size:9px; fill:#6a8aa0;
}}
.badge-pulse {{ animation:pulse 1.2s ease-in-out infinite; }}
</style></head>
<body>
<svg viewBox="0 0 960 540" xmlns="http://www.w3.org/2000/svg"
     style="width:100%;height:100%;background:#0f1423;border-radius:10px;">
<defs>
  <!-- Equipment gradients -->
  <linearGradient id="colG" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%"   stop-color="#243850"/>
    <stop offset="30%"  stop-color="#385a78"/>
    <stop offset="70%"  stop-color="#385a78"/>
    <stop offset="100%" stop-color="#203448"/>
  </linearGradient>
  <linearGradient id="eqG" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%"   stop-color="#2e4560"/>
    <stop offset="50%"  stop-color="#1e3048"/>
    <stop offset="100%" stop-color="#162538"/>
  </linearGradient>
  <linearGradient id="liqG" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%"   stop-color="#4488cc"/>
    <stop offset="100%" stop-color="#2a6090"/>
  </linearGradient>
  <radialGradient id="flG" cx=".5" cy=".7" r=".6">
    <stop offset="0%"   stop-color="{flame_color2}"/>
    <stop offset="60%"  stop-color="{flame_color}"/>
    <stop offset="100%" stop-color="transparent"/>
  </radialGradient>
  <!-- Filters -->
  <filter id="sh"><feDropShadow dx="2" dy="2" stdDeviation="4" flood-color="#000" flood-opacity=".45"/></filter>
  <filter id="gl"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <!-- Arrow markers -->
  <marker id="aG" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
    <path d="M0,0 L8,3 L0,6Z" fill="#3cc868"/></marker>
  <marker id="aB" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
    <path d="M0,0 L8,3 L0,6Z" fill="#5a8ab4"/></marker>
  <marker id="aF" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
    <path d="M0,0 L8,3 L0,6Z" fill="#5ab480"/></marker>
  <!-- Drum clip -->
  <clipPath id="dClip">
    <rect x="{drum_x+2}" y="{drum_y+2}" width="{drum_w-4}" height="{drum_h-4}" rx="32" ry="32"/>
  </clipPath>
</defs>

<!-- ===================== PIPES (behind equipment) ===================== -->

<!-- Overhead vapor: column top center → up → condenser left -->
<polyline points="430,75 430,50 555,50" class="pipe flow-r"/>
<text x="490" y="44" text-anchor="middle" class="equip-sub" fill="#5a7a98">VAPOR</text>

<!-- Condenser → Drum -->
<line x1="675" y1="58" x2="720" y2="58" class="pipe flow-r"/>

<!-- Reflux return: drum bottom → down → left → column right -->
<polyline points="798,98 798,158 480,158" class="pipe flow-l"/>
<text x="640" y="152" text-anchor="middle" class="equip-sub" fill="#5a7a98">REFLUX</text>
<line x1="480" y1="158" x2="482" y2="158" class="pipe" marker-end="url(#aB)" stroke="#5a8ab4"/>

<!-- Feed inlet → column left -->
<line x1="170" y1="195" x2="380" y2="195" class="pipe-feed flow-r"/>
<line x1="375" y1="195" x2="382" y2="195" class="pipe-feed" marker-end="url(#aF)"/>

<!-- Benzene side draw: column left → left -->
<line x1="380" y1="275" x2="170" y2="275" class="pipe-product flow-l"/>
<line x1="170" y1="275" x2="120" y2="275" class="pipe-product" marker-end="url(#aG)"/>

<!-- Column bottom → reboiler top -->
<line x1="430" y1="392" x2="430" y2="425" class="pipe flow-d"/>

<!-- Reboiler right → toluene out -->
<line x1="510" y1="452" x2="660" y2="452" class="pipe-product flow-r"/>
<line x1="660" y1="452" x2="700" y2="452" class="pipe-product" marker-end="url(#aG)"/>


<!-- ===================== COLUMN ===================== -->
<g filter="url(#sh)">
  <rect x="380" y="75" width="100" height="317" rx="14" ry="14"
        fill="url(#colG)" stroke="#5a7a98" stroke-width="2"/>
  <!-- Top/bottom caps for 3D -->
  <ellipse cx="430" cy="79" rx="50" ry="8" fill="#3a5878" stroke="#5a7a98" stroke-width="1.5"/>
  <ellipse cx="430" cy="388" rx="50" ry="8" fill="#283f58" stroke="#5a7a98" stroke-width="1.5"/>
  <!-- 8 Trays -->
  <line x1="394" y1="118" x2="466" y2="118" stroke="#4a6a88" stroke-width="1" stroke-dasharray="4,3"/>
  <line x1="394" y1="155" x2="466" y2="155" stroke="#4a6a88" stroke-width="1" stroke-dasharray="4,3"/>
  <line x1="394" y1="192" x2="466" y2="192" stroke="#4a6a88" stroke-width="1" stroke-dasharray="4,3"/>
  <line x1="394" y1="229" x2="466" y2="229" stroke="#4a6a88" stroke-width="1" stroke-dasharray="4,3"/>
  <line x1="394" y1="266" x2="466" y2="266" stroke="#4a6a88" stroke-width="1" stroke-dasharray="4,3"/>
  <line x1="394" y1="303" x2="466" y2="303" stroke="#4a6a88" stroke-width="1" stroke-dasharray="4,3"/>
  <line x1="394" y1="340" x2="466" y2="340" stroke="#4a6a88" stroke-width="1" stroke-dasharray="4,3"/>
  <line x1="394" y1="377" x2="466" y2="377" stroke="#4a6a88" stroke-width="1" stroke-dasharray="4,3"/>
  <!-- Tray numbers -->
  <text x="470" y="121" font-size="7" fill="#4a6a88" font-family="monospace">1</text>
  <text x="470" y="158" font-size="7" fill="#4a6a88" font-family="monospace">2</text>
  <text x="470" y="195" font-size="7" fill="#4a6a88" font-family="monospace">3</text>
  <text x="470" y="232" font-size="7" fill="#4a6a88" font-family="monospace">4</text>
  <text x="470" y="269" font-size="7" fill="#4a6a88" font-family="monospace">5</text>
  <text x="470" y="306" font-size="7" fill="#4a6a88" font-family="monospace">6</text>
  <text x="470" y="343" font-size="7" fill="#4a6a88" font-family="monospace">7</text>
  <text x="470" y="380" font-size="7" fill="#4a6a88" font-family="monospace">8</text>
</g>
<text x="430" y="97" text-anchor="middle" class="equip-label">COLUMN</text>
<text x="430" y="109" text-anchor="middle" class="equip-sub">8 TRAYS</text>


<!-- ===================== CONDENSER ===================== -->
<g filter="url(#sh)">
  <rect x="555" y="32" width="120" height="52" rx="10" ry="10"
        fill="url(#eqG)" stroke="#5a7a98" stroke-width="2"/>
  <!-- Cooling tube lines -->
  <line x1="572" y1="44" x2="572" y2="72" stroke="#4488cc" stroke-width="2" opacity=".4"/>
  <line x1="587" y1="44" x2="587" y2="72" stroke="#4488cc" stroke-width="2" opacity=".4"/>
  <line x1="602" y1="44" x2="602" y2="72" stroke="#4488cc" stroke-width="2" opacity=".4"/>
  <line x1="617" y1="44" x2="617" y2="72" stroke="#4488cc" stroke-width="2" opacity=".4"/>
  <line x1="632" y1="44" x2="632" y2="72" stroke="#4488cc" stroke-width="2" opacity=".4"/>
  <line x1="647" y1="44" x2="647" y2="72" stroke="#4488cc" stroke-width="2" opacity=".4"/>
  <line x1="662" y1="44" x2="662" y2="72" stroke="#4488cc" stroke-width="2" opacity=".4"/>
</g>
<text x="615" y="61" text-anchor="middle" class="equip-label">CONDENSER</text>


<!-- ===================== REFLUX DRUM ===================== -->
<g filter="url(#sh)">
  <rect x="{drum_x}" y="{drum_y}" width="{drum_w}" height="{drum_h}"
        rx="34" ry="34" fill="url(#eqG)" stroke="#5a7a98" stroke-width="2"/>
  <!-- Liquid level fill -->
  <rect x="{drum_x}" y="{level_fill_y:.1f}" width="{drum_w}" height="{level_fill_h:.1f}"
        fill="url(#liqG)" opacity=".55" clip-path="url(#dClip)"/>
  <!-- Level gauge marks -->
  <line x1="{drum_x + drum_w - 8}" y1="{drum_y + 10}" x2="{drum_x + drum_w - 8}" y2="{drum_y + drum_h - 10}"
        stroke="#5a7a98" stroke-width="1" stroke-dasharray="2,4"/>
</g>
<text x="{drum_x + drum_w // 2}" y="60" text-anchor="middle" class="equip-label">REFLUX DRUM</text>
<text x="{drum_x + drum_w // 2}" y="76" text-anchor="middle"
      style="font-family:monospace;font-size:10px;font-weight:700;fill:#7ab8e0">{drum_level:.0%}</text>


<!-- ===================== REBOILER ===================== -->
<g filter="url(#sh)">
  <rect x="350" y="425" width="160" height="58" rx="12" ry="12"
        fill="url(#eqG)" stroke="#5a7a98" stroke-width="2"/>
  <!-- Flame glow -->
  <g style="animation:flicker .5s ease-in-out infinite;transform-origin:485px 458px;">
    <ellipse cx="485" cy="458" rx="18" ry="22" fill="url(#flG)" opacity="{flame_opacity}"/>
    <ellipse cx="485" cy="452" rx="9" ry="13" fill="{flame_color2}" opacity="{float(flame_opacity)*0.7:.2f}"/>
  </g>
</g>
<text x="420" y="452" text-anchor="middle" class="equip-label">REBOILER</text>
<text x="420" y="468" text-anchor="middle"
      style="font-family:monospace;font-size:10px;font-weight:700;fill:#e8a840">{state.F_Reboil:.2f} MW</text>


<!-- ===================== STREAM LABELS ===================== -->
<!-- Feed -->
<rect x="110" y="182" width="55" height="22" rx="5" fill="#122818" stroke="#4a9060" stroke-width="1"/>
<text x="137" y="197" text-anchor="middle" class="stream-label" fill="#5ab480">FEED</text>

<!-- Benzene -->
<rect x="105" y="262" width="75" height="22" rx="5" fill="#122818" stroke="#3cc868" stroke-width="1"/>
<text x="142" y="277" text-anchor="middle" class="stream-label" fill="#3cc868">BENZENE</text>

<!-- Toluene -->
<rect x="705" y="440" width="78" height="22" rx="5" fill="#122818" stroke="#3cc868" stroke-width="1"/>
<text x="744" y="455" text-anchor="middle" class="stream-label" fill="#3cc868">TOLUENE</text>


<!-- ===================== INSTRUMENT TAGS ===================== -->
<!-- Tag: Benzene Purity -->
<g transform="translate(20,310)">
  <rect width="105" height="42" class="tag-box" rx="5"/>
  <text x="10" y="14" class="tag-name">xB PURITY</text>
  <text x="10" y="32" class="tag-value">{state.xB_sd:.4f}</text>
  <text x="68" y="32" class="tag-unit">mol fr</text>
</g>

<!-- Tag: Column dP -->
<g transform="translate(20,360)">
  <rect width="105" height="42" class="tag-box" rx="5"/>
  <text x="10" y="14" class="tag-name">dP COLUMN</text>
  <text x="10" y="32" class="tag-value">{state.dP_col:.3f}</text>
  <text x="68" y="32" class="tag-unit">bar</text>
</g>

<!-- Tag: Overhead Temperature -->
<g transform="translate(550,98)">
  <rect width="105" height="42" class="tag-box" rx="5"/>
  <text x="10" y="14" class="tag-name">T OVERHEAD</text>
  <text x="10" y="32" class="tag-value">{state.T_top:.1f}</text>
  <text x="62" y="32" class="tag-unit">&deg;C</text>
</g>

<!-- Tag: Reflux Flow -->
<g transform="translate(700,115)">
  <rect width="105" height="42" class="tag-box" rx="5"/>
  <text x="10" y="14" class="tag-name">F REFLUX</text>
  <text x="10" y="32" class="tag-value">{state.F_Reflux:.1f}</text>
  <text x="52" y="32" class="tag-unit">t/h</text>
</g>

<!-- Tag: Reboiler Duty -->
<g transform="translate(550,460)">
  <rect width="105" height="42" class="tag-box" rx="5"/>
  <text x="10" y="14" class="tag-name">Q REBOILER</text>
  <text x="10" y="32" class="tag-value">{state.F_Reboil:.2f}</text>
  <text x="60" y="32" class="tag-unit">MW</text>
</g>

<!-- Tag: Toluene Transfer -->
<g transform="translate(550,510)">
  <rect width="105" height="42" class="tag-box" rx="5"/>
  <text x="10" y="14" class="tag-name">F TOLUENE</text>
  <text x="10" y="32" class="tag-value">{state.F_ToTol:.1f}</text>
  <text x="42" y="32" class="tag-unit">t/h</text>
</g>


<!-- ===================== SAFETY BADGE ===================== -->
<g transform="translate(20,18)"{pulse_class}>
  <rect width="{badge_w}" height="30" rx="15" fill="{badge_color}" filter="url(#gl)"/>
  <text x="{badge_w // 2}" y="20" text-anchor="middle"
        style="font-family:'Segoe UI',Arial,sans-serif;font-size:12px;font-weight:700;fill:#000;">
    {badge_text}
  </text>
</g>

<!-- ===================== TITLE WATERMARK ===================== -->
<text x="940" y="530" text-anchor="end"
      style="font-family:'Segoe UI',Arial,sans-serif;font-size:9px;fill:#2a3a50;">
  BENZENE COLUMN OTS &bull; PROCESS SCHEMATIC
</text>

</svg>
</body></html>"""

    components.html(svg_html, height=560, scrolling=False)
