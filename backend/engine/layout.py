"""2D Control Panel Mounting Plate (중판) Automatic & Interactive Layout Engine.

Capabilities:
- IEC 61439 EMC zone placement + user drag-and-drop coordinate overrides (layout_overrides)
- Real-time physical overlap (collision), boundary overflow, and 100mm thermal clearance validation
- Wire-duct Manhattan routing wire length estimator (mm -> m) grouped by wire SQ / AWG -> feeds BOM!
- Standard EMC SVG, Thermal Heatmap SVG (with drag coordinate metadata), and 1:1 mm AutoCAD DXF
"""

from __future__ import annotations

import html
import math
import re
from collections import defaultdict

from backend.catalog import sq_to_awg
from backend.models import (
    LayoutComponent,
    LayoutIssue,
    LoadCalculationResult,
    PanelLayout,
    PlcModule,
    PowerSummary,
    Project,
    WireLengthEstimate,
)


WIRE_PRICE_PER_M_KRW: dict[float, int] = {
    0.75: 380,
    1.5: 620,
    2.5: 950,
    4.0: 1450,
    6.0: 2150,
    10.0: 3600,
    16.0: 5500,
    25.0: 8400,
    35.0: 11800,
    50.0: 16500,
}


def _parse_enclosure_dims(size_str: str) -> tuple[int, int, int]:
    nums = [int(x) for x in re.findall(r"\d{3,4}", size_str)]
    if len(nums) >= 3:
        return nums[0], nums[1], nums[2]
    return 1000, 1800, 500


def _heat_color(heat_w: float) -> tuple[str, str]:
    if heat_w >= 45:
        return "#fee2e2", "#dc2626"
    if heat_w >= 20:
        return "#ffedd5", "#ea580c"
    if heat_w >= 8:
        return "#fef9c3", "#ca8a04"
    return "#dcfce7", "#16a34a"


def _zone_color(zone: str) -> tuple[str, str]:
    return {
        "POWER": ("#eff6ff", "#1d4ed8"),
        "DRIVE": ("#ecfdf5", "#047857"),
        "CONTROL": ("#fefce8", "#a16207"),
        "TERMINAL": ("#f1f5f9", "#475569"),
    }.get(zone, ("#f8fafc", "#334155"))


def _detect_layout_issues(
    components: list[LayoutComponent],
    plate_w: int,
    plate_h: int,
) -> tuple[list[LayoutIssue], set[str]]:
    """Detect physical collisions, plate boundary overflows, and thermal airflow clearance violations."""
    issues: list[LayoutIssue] = []
    colliding_tags: set[str] = set()

    for c in components:
        if c.x_mm < 5 or c.y_mm < 5 or (c.x_mm + c.w_mm) > (plate_w - 5) or (c.y_mm + c.h_mm) > (plate_h - 5):
            colliding_tags.add(c.tag)
            issues.append(
                LayoutIssue(
                    severity="ERROR",
                    code="LAY-002",
                    targets=[c.tag],
                    message=f"Component {c.tag} exceeds mounting plate bounds ({plate_w}×{plate_h} mm).",
                )
            )

    n = len(components)
    for i in range(n):
        a = components[i]
        for j in range(i + 1, n):
            b = components[j]
            # Strict physical overlap (tolerance 1mm)
            overlap_x = (a.x_mm < b.x_mm + b.w_mm - 1.0) and (a.x_mm + a.w_mm - 1.0 > b.x_mm)
            overlap_y = (a.y_mm < b.y_mm + b.h_mm - 1.0) and (a.y_mm + a.h_mm - 1.0 > b.y_mm)
            if overlap_x and overlap_y:
                colliding_tags.add(a.tag)
                colliding_tags.add(b.tag)
                issues.append(
                    LayoutIssue(
                        severity="ERROR",
                        code="LAY-001",
                        targets=[a.tag, b.tag],
                        message=f"Physical collision detected between {a.tag} and {b.tag}. Drag apart to resolve.",
                    )
                )
                continue

            # Thermal vertical airflow clearance check for drives (clearance_mm > 0)
            req_cl = max(a.clearance_mm, b.clearance_mm)
            if req_cl > 0 and overlap_x:
                # Vertical gap between bottom of upper component and top of lower component
                gap_y = max(b.y_mm - (a.y_mm + a.h_mm), a.y_mm - (b.y_mm + b.h_mm))
                if 0 <= gap_y < req_cl * 0.45:
                    issues.append(
                        LayoutIssue(
                            severity="WARNING",
                            code="LAY-003",
                            targets=[a.tag, b.tag],
                            message=f"Thermal airflow clearance ({int(gap_y)} mm) between {a.tag} and {b.tag} is tighter than recommended ({int(req_cl * 0.45)} mm).",
                        )
                    )

    return issues, colliding_tags


def _estimate_duct_wire_lengths(
    components: list[LayoutComponent],
    calcs: list[LoadCalculationResult],
    summary: PowerSummary,
    duct_ys: list[float],
    plate_w: int,
) -> tuple[list[WireLengthEstimate], float]:
    """Compute realistic Manhattan wire-duct routing distances (m) from 2D component positions."""
    comp_map = {c.tag: c for c in components}

    def center(c: LayoutComponent) -> tuple[float, float]:
        return c.x_mm + c.w_mm / 2.0, c.y_mm + c.h_mm / 2.0

    def duct_route_m(c1: LayoutComponent, c2: LayoutComponent) -> float:
        x1, y1 = center(c1)
        x2, y2 = center(c2)
        # Route vertically to nearest horizontal duct, travel horizontally, plus side-duct hop if different rows
        nearest_d1 = min(duct_ys, key=lambda dy: abs(dy - y1)) if duct_ys else y1
        nearest_d2 = min(duct_ys, key=lambda dy: abs(dy - y2)) if duct_ys else y2
        if abs(nearest_d1 - nearest_d2) < 10.0:
            dist_mm = abs(y1 - nearest_d1) + abs(x1 - x2) + abs(y2 - nearest_d1)
        else:
            # Route via nearest vertical side duct (left 35mm or right plate_w - 35mm)
            side_x = 35.0 if (x1 + x2) < plate_w else (plate_w - 35.0)
            dist_mm = (
                abs(y1 - nearest_d1)
                + abs(x1 - side_x)
                + abs(nearest_d1 - nearest_d2)
                + abs(x2 - side_x)
                + abs(y2 - nearest_d2)
            )
        return (dist_mm / 1000.0) * 1.18  # +18% terminal strip & bend slack

    sq_acc: dict[float, dict] = defaultdict(lambda: {"length_m": 0.0, "routes": 0, "purpose": set()})

    q0 = comp_map.get("-Q0")
    x1 = comp_map.get("-X1")
    x2 = comp_map.get("-X2")
    g1 = comp_map.get("-G1")

    # 1. Power feeders: Main MCCB -> Branch MCCBs -> Drives/MCs -> Power Terminal Strip -X1
    power_calcs = [c for c in calcs if c.load_type in ("motor_dol", "motor_inv", "servo", "heater")]
    for idx, calc in enumerate(power_calcs, start=1):
        q_comp = comp_map.get(f"-Q{idx}")
        d_comp = comp_map.get(calc.tag)
        sq = calc.wire_sq
        if q0 and q_comp:
            sq_acc[summary.main_wire_sq]["length_m"] += duct_route_m(q0, q_comp) * 3.0  # 3-phase L1/L2/L3
            sq_acc[summary.main_wire_sq]["routes"] += 3
            sq_acc[summary.main_wire_sq]["purpose"].add("Main Bus Distribution")
        if q_comp and d_comp:
            sq_acc[sq]["length_m"] += duct_route_m(q_comp, d_comp) * 3.0
            sq_acc[sq]["routes"] += 3
            sq_acc[sq]["purpose"].add("Power Feeder (MCCB→Drive)")
        if d_comp and x1:
            sq_acc[sq]["length_m"] += duct_route_m(d_comp, x1) * 4.0  # U/V/W/PE
            sq_acc[sq]["routes"] += 4
            sq_acc[sq]["purpose"].add("Drive Output (Drive→-X1)")

    # 2. Control & PLC I/O wires: SMPS / Safety / PLC Slots -> Control Terminal Strip -X2
    ctrl_sq = 0.75
    for c in components:
        if c.zone == "CONTROL" and x2:
            conductors = 16 if c.tag.startswith("S") else 6
            sq_acc[ctrl_sq]["length_m"] += duct_route_m(c, x2) * conductors
            sq_acc[ctrl_sq]["routes"] += conductors
            sq_acc[ctrl_sq]["purpose"].add("Control / PLC I/O (DC24V)")
        if g1 and c.zone == "CONTROL" and c.tag != "-G1":
            sq_acc[ctrl_sq]["length_m"] += duct_route_m(g1, c) * 2.0
            sq_acc[ctrl_sq]["routes"] += 2
            sq_acc[ctrl_sq]["purpose"].add("DC24V Bus Distribution")

    estimates: list[WireLengthEstimate] = []
    total_m = 0.0
    for sq in sorted(sq_acc.keys()):
        raw_m = math.ceil(sq_acc[sq]["length_m"])
        if raw_m <= 0:
            continue
        unit_price = WIRE_PRICE_PER_M_KRW.get(sq, int(450 * sq))
        total_m += raw_m
        estimates.append(
            WireLengthEstimate(
                wire_sq=sq,
                wire_awg=sq_to_awg(sq),
                purpose=", ".join(sorted(sq_acc[sq]["purpose"])),
                route_count=sq_acc[sq]["routes"],
                total_length_m=float(raw_m),
                unit_price_per_m_krw=unit_price,
                total_price_krw=int(raw_m * unit_price),
            )
        )
    return estimates, round(total_m, 1)


def _render_layout_svg(
    project: Project,
    summary: PowerSummary,
    enc_w: int,
    enc_h: int,
    plate_w: int,
    plate_h: int,
    components: list[LayoutComponent],
    duct_ys: list[float],
    colliding_tags: set[str],
    total_wire_m: float,
    thermal_mode: bool = False,
) -> str:
    esc = html.escape
    margin_left, margin_top = 80, 58
    draw_max_w, draw_max_h = 680, 590
    scale = min(draw_max_w / enc_w, draw_max_h / enc_h)

    def sx(mm: float) -> float:
        return margin_left + mm * scale

    def sy(mm: float) -> float:
        return margin_top + mm * scale

    ew_px, eh_px = enc_w * scale, enc_h * scale
    plate_off_x = (enc_w - plate_w) / 2.0
    plate_off_y = (enc_h - plate_h) / 2.0
    pw_px, ph_px = plate_w * scale, plate_h * scale

    parts: list[str] = []

    # Outer Enclosure & Mounting Plate
    parts.append(
        f'<rect x="{sx(0):.1f}" y="{sy(0):.1f}" width="{ew_px:.1f}" height="{eh_px:.1f}" rx="4" '
        f'fill="#e2e8f0" stroke="#1e293b" stroke-width="2"/>'
    )
    parts.append(
        f'<rect x="{sx(plate_off_x):.1f}" y="{sy(plate_off_y):.1f}" width="{pw_px:.1f}" height="{ph_px:.1f}" '
        f'fill="#f8fafc" stroke="#475569" stroke-width="1.4"/>'
    )

    parts.append(
        f'<line x1="{sx(0):.1f}" y1="{sy(0) - 22:.1f}" x2="{sx(enc_w):.1f}" y2="{sy(0) - 22:.1f}" stroke="#334155" stroke-width="1"/>'
        f'<text x="{sx(enc_w / 2):.1f}" y="{sy(0) - 27:.1f}" text-anchor="middle" font-size="11" font-weight="700" fill="#0f172a" font-family="monospace">W = {enc_w} mm (Plate {plate_w} mm)</text>'
    )
    parts.append(
        f'<line x1="{sx(0) - 26:.1f}" y1="{sy(0):.1f}" x2="{sx(0) - 26:.1f}" y2="{sy(enc_h):.1f}" stroke="#334155" stroke-width="1"/>'
        f'<text x="{sx(0) - 34:.1f}" y="{sy(enc_h / 2):.1f}" text-anchor="middle" font-size="11" font-weight="700" fill="#0f172a" font-family="monospace" transform="rotate(-90 {sx(0) - 34:.1f} {sy(enc_h / 2):.1f})">H = {enc_h} mm (Plate {plate_h} mm)</text>'
    )

    for dy in duct_ys:
        parts.append(
            f'<rect x="{sx(plate_off_x + 25):.1f}" y="{sy(plate_off_y + dy):.1f}" '
            f'width="{(plate_w - 50) * scale:.1f}" height="{50 * scale:.1f}" '
            f'fill="#cbd5e1" stroke="#64748b" stroke-width="0.9" stroke-dasharray="4,2"/>'
        )
        parts.append(
            f'<text x="{sx(plate_off_x + plate_w - 32):.1f}" y="{sy(plate_off_y + dy + 32):.1f}" text-anchor="end" '
            f'font-size="8.5" fill="#475569" font-family="monospace">WIRE DUCT 50×60</text>'
        )

    for vx in (plate_off_x + 15, plate_off_x + plate_w - 55):
        parts.append(
            f'<rect x="{sx(vx):.1f}" y="{sy(plate_off_y + 25):.1f}" width="{40 * scale:.1f}" height="{(plate_h - 50) * scale:.1f}" '
            f'fill="#dbeafe" fill-opacity="0.35" stroke="#94a3b8" stroke-width="0.8"/>'
        )

    parts.append(
        f'<rect x="{sx(plate_off_x + plate_w - 190):.1f}" y="{sy(plate_off_y + 8):.1f}" '
        f'width="{130 * scale:.1f}" height="{24 * scale:.1f}" rx="3" fill="#e0f2fe" stroke="#0284c7" stroke-width="1.2"/>'
        f'<text x="{sx(plate_off_x + plate_w - 125):.1f}" y="{sy(plate_off_y + 24):.1f}" text-anchor="middle" '
        f'font-size="8.5" font-weight="700" fill="#0369a1" font-family="monospace">COOLING ({summary.total_heat_loss_w}W)</text>'
    )

    # Draggable Components
    for comp in components:
        cx = sx(plate_off_x + comp.x_mm)
        cy = sy(plate_off_y + comp.y_mm)
        cw = max(comp.w_mm * scale, 18.0)
        ch = max(comp.h_mm * scale, 18.0)

        is_col = comp.tag in colliding_tags
        fill, stroke = _heat_color(comp.heat_w) if thermal_mode else _zone_color(comp.zone)
        if is_col:
            fill, stroke = "#fef2f2", "#dc2626"

        cl_svg = ""
        if comp.clearance_mm > 0:
            cl_px = comp.clearance_mm * scale
            cl_svg = (
                f'<rect x="0" y="{-cl_px * 0.45:.1f}" width="{cw:.1f}" height="{ch + cl_px * 0.9:.1f}" '
                f'fill="none" stroke="#f97316" stroke-width="0.9" stroke-dasharray="3,2" pointer-events="none"/>'
            )

        desc = (
            f"{comp.label} | P/N: {comp.part_number} | Pos: ({int(comp.x_mm)}, {int(comp.y_mm)}) mm | "
            f"Size: {int(comp.w_mm)}×{int(comp.h_mm)}×{int(comp.d_mm)} mm | Heat: {comp.heat_w}W"
        )
        parts.append(
            f'<g class="sch-device layout-comp" transform="translate({cx:.1f},{cy:.1f})" '
            f'data-device="{esc(comp.tag)}" data-desc="{esc(desc)}" '
            f'data-x-mm="{comp.x_mm:.1f}" data-y-mm="{comp.y_mm:.1f}" data-w-mm="{comp.w_mm:.1f}" data-h-mm="{comp.h_mm:.1f}">'
            f'{cl_svg}'
            f'<rect x="0" y="0" width="{cw:.1f}" height="{ch:.1f}" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="{2.6 if is_col else 1.4}"/>'
            f'<text x="{cw / 2:.1f}" y="{ch / 2 - 2:.1f}" text-anchor="middle" font-size="9" font-weight="700" fill="#0f172a" font-family="monospace" pointer-events="none">{esc(comp.tag[:12])}</text>'
            f'<text x="{cw / 2:.1f}" y="{ch / 2 + 10:.1f}" text-anchor="middle" font-size="7.5" fill="#334155" font-family="monospace" pointer-events="none">'
            f'{f"{comp.heat_w}W" if thermal_mode else f"{int(comp.w_mm)}×{int(comp.h_mm)}"}</text>'
            f'</g>'
        )

    leg_x = sx(enc_w) + 34
    mode_title = "Thermal Heatmap Overlay" if thermal_mode else "Interactive EMC Zone Layout (Drag to Move)"
    legend_items = (
        [
            ("#fee2e2", "#dc2626", "High Heat (>= 45W)"),
            ("#ffedd5", "#ea580c", "Medium Heat (20-44W)"),
            ("#fef9c3", "#ca8a04", "Low Heat (8-19W)"),
            ("#dcfce7", "#16a34a", "Cool (< 8W)"),
        ]
        if thermal_mode
        else [
            ("#eff6ff", "#1d4ed8", "Zone 1: Power / MCCB"),
            ("#ecfdf5", "#047857", "Zone 2: VFD / Servo Drives"),
            ("#fefce8", "#a16207", "Zone 3: Control / PLC / Safety"),
            ("#f1f5f9", "#475569", "Zone 4: -X1 / -X2 Terminals"),
        ]
    )
    leg_rows = "".join(
        f'<rect x="{leg_x + 14:.1f}" y="{146 + i * 28}" width="14" height="14" rx="2" fill="{fl}" stroke="{st}" stroke-width="1.2"/>'
        f'<text x="{leg_x + 36:.1f}" y="{157 + i * 28}" font-size="10.5" fill="#1e293b" font-family="sans-serif">{lbl}</text>'
        for i, (fl, st, lbl) in enumerate(legend_items)
    )

    parts.append(
        f'<g>'
        f'<rect x="{leg_x:.1f}" y="58" width="295" height="320" rx="6" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.2"/>'
        f'<text x="{leg_x + 14:.1f}" y="84" font-size="12" font-weight="700" fill="#0f172a" font-family="sans-serif">Mounting Plate 2D CAD (IEC 61439)</text>'
        f'<text x="{leg_x + 14:.1f}" y="104" font-size="10" fill="#1d4ed8" font-weight="700" font-family="sans-serif">{mode_title}</text>'
        f'<line x1="{leg_x + 14:.1f}" y1="118" x2="{leg_x + 281:.1f}" y2="118" stroke="#e2e8f0"/>'
        f'<text x="{leg_x + 14:.1f}" y="136" font-size="10" font-weight="700" fill="#64748b" font-family="sans-serif">Legend</text>'
        f'{leg_rows}'
        f'<line x1="{leg_x + 14:.1f}" y1="264" x2="{leg_x + 281:.1f}" y2="264" stroke="#e2e8f0"/>'
        f'<text x="{leg_x + 14:.1f}" y="286" font-size="10" fill="#334155" font-family="monospace">Enclosure : {esc(summary.enclosure_part)}</text>'
        f'<text x="{leg_x + 14:.1f}" y="306" font-size="10" fill="#334155" font-family="monospace">Plate     : {plate_w}×{plate_h} mm</text>'
        f'<text x="{leg_x + 14:.1f}" y="326" font-size="10" fill="#334155" font-family="monospace">Components: {len(components)} | Heat: {summary.total_heat_loss_w}W</text>'
        f'<text x="{leg_x + 14:.1f}" y="346" font-size="10" font-weight="700" fill="#047857" font-family="monospace">Panel Wire: {total_wire_m} m (Duct Routed)</text>'
        f'<text x="{leg_x + 14:.1f}" y="366" font-size="10" font-weight="700" fill="{"#dc2626" if colliding_tags else "#059669"}" font-family="monospace">Collisions: {len(colliding_tags)} tag(s)</text>'
        f'</g>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 700" class="schematic-svg interactive-layout-svg" '
        f'data-scale="{scale:.6f}" data-margin-left="{margin_left}" data-margin-top="{margin_top}" '
        f'data-plate-off-x="{plate_off_x:.2f}" data-plate-off-y="{plate_off_y:.2f}" '
        f'data-plate-w="{plate_w}" data-plate-h="{plate_h}">'
        '<rect x="0" y="0" width="1120" height="700" fill="#ffffff"/>'
        + "\n".join(parts)
        + "</svg>"
    )


def build_panel_layout(
    project: Project,
    summary: PowerSummary,
    calcs: list[LoadCalculationResult],
    plc_modules: list[PlcModule],
) -> PanelLayout:
    """Compute physical 2D layout, apply user drag overrides, validate collisions/clearance & route wires."""
    enc_w, enc_h, enc_d = _parse_enclosure_dims(summary.enclosure_size_mm)
    plate_w = enc_w - 100
    plate_h = enc_h - 140

    components: list[LayoutComponent] = []
    usable_x = 75.0
    max_x = plate_w - 75.0

    y_row1 = 70.0
    duct1_y = y_row1 + 210.0

    cur_x = usable_x
    components.append(
        LayoutComponent(
            tag="-Q0", label="Main MCCB", part_number=summary.main_breaker_part, zone="POWER",
            x_mm=cur_x, y_mm=y_row1, w_mm=105, h_mm=165, d_mm=95,
            heat_w=round(2.5 + summary.main_breaker_rating_a * 0.06, 1),
        )
    )
    cur_x += 120

    components.append(
        LayoutComponent(
            tag="-F0", label="3P Surge Protector (SPD)", part_number="VAL-MS 320/3+1", zone="POWER",
            x_mm=cur_x, y_mm=y_row1 + 35, w_mm=72, h_mm=95, d_mm=65, heat_w=1.0,
        )
    )
    cur_x += 88

    power_calcs = [c for c in calcs if c.load_type in ("motor_dol", "motor_inv", "servo", "heater")]
    for idx, c in enumerate(power_calcs, start=1):
        if cur_x + 78 > max_x:
            break
        components.append(
            LayoutComponent(
                tag=f"-Q{idx}", label=f"{c.name} MCCB", part_number=c.breaker_part, zone="POWER",
                x_mm=cur_x, y_mm=y_row1 + 20, w_mm=75, h_mm=130, d_mm=80,
                heat_w=round(min(c.heat_loss_w * 0.15, 8.0), 1),
            )
        )
        cur_x += 86

    y_row2 = duct1_y + 95.0
    duct2_y = y_row2 + 235.0
    cur_x = usable_x
    for c in power_calcs:
        is_drive = c.load_type in ("motor_inv", "servo")
        w_mm = 115.0 if c.load_type == "motor_inv" else (85.0 if c.load_type == "servo" else 68.0)
        h_mm = 185.0 if is_drive else 115.0
        if cur_x + w_mm > max_x:
            break
        components.append(
            LayoutComponent(
                tag=c.tag, label=f"{c.name} ({'Drive' if is_drive else 'MC'})",
                part_number=c.drive_part or c.contactor_part or c.breaker_part,
                zone="DRIVE" if is_drive else "POWER",
                x_mm=cur_x, y_mm=y_row2, w_mm=w_mm, h_mm=h_mm, d_mm=155 if is_drive else 95,
                heat_w=c.heat_loss_w, clearance_mm=100.0 if is_drive else 0.0,
            )
        )
        cur_x += w_mm + (26 if is_drive else 16)

    y_row3 = min(duct2_y + 75.0, plate_h - 330.0)
    duct3_y = y_row3 + 175.0
    cur_x = usable_x

    components.append(
        LayoutComponent(
            tag="-G1", label="DC 24V SMPS", part_number=summary.smps_selected_part, zone="CONTROL",
            x_mm=cur_x, y_mm=y_row3, w_mm=85, h_mm=130, d_mm=125,
            heat_w=round(summary.total_dc24v_current_a * 24.0 * 0.14, 1), clearance_mm=40.0,
        )
    )
    cur_x += 105

    if any(l.load_type == "safety_circuit" for l in project.loads):
        components.append(
            LayoutComponent(
                tag="-K_SAF1", label="Safety Relay + Dual MC", part_number="Safety PLd/e Module", zone="CONTROL",
                x_mm=cur_x, y_mm=y_row3 + 10, w_mm=110, h_mm=115, d_mm=110, heat_w=10.5,
            )
        )
        cur_x += 126

    for mod in plc_modules:
        mw = 44.0 if mod.module_type in ("PSU", "CPU") else 34.0
        if cur_x + mw > max_x:
            break
        components.append(
            LayoutComponent(
                tag=f"S{mod.slot}", label=f"PLC {mod.module_type} (Slot {mod.slot})",
                part_number=mod.part_number, zone="CONTROL",
                x_mm=cur_x, y_mm=y_row3 + 6, w_mm=mw, h_mm=124, d_mm=110,
                heat_w=6.5 if mod.module_type in ("PSU", "CPU") else 4.2,
            )
        )
        cur_x += mw + 3

    y_row4 = min(duct3_y + 70.0, plate_h - 115.0)
    half_w = (max_x - usable_x - 30) / 2.0
    components.append(
        LayoutComponent(
            tag="-X1", label="Power Terminal Strip", part_number="Phoenix UT 4 / UT 10", zone="TERMINAL",
            x_mm=usable_x, y_mm=y_row4, w_mm=half_w, h_mm=65, d_mm=50, heat_w=2.0,
        )
    )
    components.append(
        LayoutComponent(
            tag="-X2", label="Control / PLC I/O Terminal Strip", part_number="Phoenix PT 2.5 Push-In", zone="TERMINAL",
            x_mm=usable_x + half_w + 30, y_mm=y_row4, w_mm=half_w, h_mm=65, d_mm=45, heat_w=1.5,
        )
    )

    # Apply persisted user drag-and-drop overrides (10mm grid snapped)
    overrides = project.layout_overrides or {}
    for comp in components:
        ov = overrides.get(comp.tag)
        if ov and "x_mm" in ov and "y_mm" in ov:
            comp.x_mm = round(float(ov["x_mm"]), 1)
            comp.y_mm = round(float(ov["y_mm"]), 1)

    duct_ys = [duct1_y, duct2_y, duct3_y]
    layout_issues, colliding_tags = _detect_layout_issues(components, plate_w, plate_h)
    wire_summary, total_wire_m = _estimate_duct_wire_lengths(components, calcs, summary, duct_ys, plate_w)

    comp_area = sum(c.w_mm * c.h_mm for c in components)
    duct_area = len(duct_ys) * (plate_w - 50) * 50 + 2 * (plate_h - 50) * 40
    utilization = min(98.0, round(((comp_area + duct_area) / max(plate_w * plate_h, 1)) * 100.0, 1))

    svg_std = _render_layout_svg(project, summary, enc_w, enc_h, plate_w, plate_h, components, duct_ys, colliding_tags, total_wire_m, thermal_mode=False)
    svg_thm = _render_layout_svg(project, summary, enc_w, enc_h, plate_w, plate_h, components, duct_ys, colliding_tags, total_wire_m, thermal_mode=True)

    return PanelLayout(
        enclosure_w_mm=enc_w,
        enclosure_h_mm=enc_h,
        enclosure_d_mm=enc_d,
        plate_w_mm=plate_w,
        plate_h_mm=plate_h,
        utilization_pct=utilization,
        components=components,
        layout_issues=layout_issues,
        wire_length_summary=wire_summary,
        total_panel_wire_m=total_wire_m,
        svg=svg_std,
        svg_thermal=svg_thm,
    )


def export_layout_dxf(project: Project, layout: PanelLayout) -> str:
    """Export physical 1:1 millimeter Mounting Plate 2D CAD Layout as AutoCAD R12 DXF."""
    entities: list[str] = []

    def add_line(x1: float, y1: float, x2: float, y2: float, layer: str) -> None:
        entities.extend([
            "0", "LINE", "8", layer,
            "10", f"{x1:.2f}", "20", f"{y1:.2f}", "30", "0.0",
            "11", f"{x2:.2f}", "21", f"{y2:.2f}", "31", "0.0",
        ])

    def add_rect(x: float, y: float, w: float, h: float, layer: str) -> None:
        add_line(x, y, x + w, y, layer)
        add_line(x + w, y, x + w, y + h, layer)
        add_line(x + w, y + h, x, y + h, layer)
        add_line(x, y + h, x, y, layer)

    def add_text(x: float, y: float, text: str, h: float, layer: str) -> None:
        safe = text.encode("ascii", "replace").decode("ascii")
        entities.extend([
            "0", "TEXT", "8", layer,
            "10", f"{x:.2f}", "20", f"{y:.2f}", "30", "0.0",
            "40", f"{h:.2f}", "1", safe,
        ])

    eh = float(layout.enclosure_h_mm)
    add_rect(0, 0, layout.enclosure_w_mm, layout.enclosure_h_mm, "ENCLOSURE")
    off_x = (layout.enclosure_w_mm - layout.plate_w_mm) / 2.0
    off_y = (layout.enclosure_h_mm - layout.plate_h_mm) / 2.0
    add_rect(off_x, off_y, layout.plate_w_mm, layout.plate_h_mm, "MOUNTING_PLATE")
    add_text(off_x + 20, eh - 35, f"PANELCRAFT 2D LAYOUT - {project.id} ({layout.enclosure_w_mm}x{layout.enclosure_h_mm}x{layout.enclosure_d_mm}mm)", 18.0, "TEXT")

    for c in layout.components:
        cad_x = off_x + c.x_mm
        cad_y = eh - (off_y + c.y_mm + c.h_mm)
        add_rect(cad_x, cad_y, c.w_mm, c.h_mm, f"ZONE_{c.zone}")
        add_text(cad_x + 4, cad_y + c.h_mm / 2.0, c.tag, 12.0, "TEXT")

    lines = [
        "0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "0", "ENDSEC",
        "0", "SECTION", "2", "ENTITIES",
        *entities,
        "0", "ENDSEC", "0", "EOF",
    ]
    return "\n".join(lines) + "\n"
