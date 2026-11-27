"""Auto-paginated multi-sheet IEC 61082 SVG schematic synthesizer, terminal strip builder, and multi-sheet AutoCAD DXF exporter."""

from __future__ import annotations

import html
import math

from backend.models import (
    LoadCalculationResult,
    PlcChannel,
    PlcModule,
    PowerSummary,
    Project,
    SchematicSheet,
    TerminalRow,
)


def build_terminals(
    calcs: list[LoadCalculationResult],
    plc_channels: list[PlcChannel],
) -> list[TerminalRow]:
    """Build synchronized power (-X1) and control/IO (-X2) terminal strips."""
    rows: list[TerminalRow] = []
    t1 = 1
    for c in calcs:
        if c.load_type in ("motor_dol", "motor_inv", "servo", "heater"):
            for phase, color in [("U", "BK"), ("V", "BR"), ("W", "GY"), ("PE", "GN/YE")]:
                rows.append(
                    TerminalRow(
                        strip="-X1",
                        terminal_no=t1,
                        wire_number=f"P{t1:03d}-{phase}",
                        wire_sq=c.wire_sq,
                        wire_color=color,
                        from_device=c.drive_part or c.contactor_part or c.breaker_part,
                        to_device=f"{c.iec_device_tag} ({c.tag})",
                        signal=f"{c.name} {phase}",
                    )
                )
                t1 += 1

    for idx, ch in enumerate(plc_channels, start=1):
        color = "BU" if ch.io_type in ("DI", "DO") else "WH/SHIELD"
        sq = 0.75 if ch.io_type in ("DI", "DO") else 0.5
        rows.append(
            TerminalRow(
                strip="-X2",
                terminal_no=idx,
                wire_number=ch.wire_number,
                wire_sq=sq,
                wire_color=color,
                from_device=f"PLC Slot {ch.slot} ({ch.plc_address})",
                to_device=f"{ch.unit_tag}",
                signal=ch.signal_name,
            )
        )
    return rows


def _svg_frame(
    project: Project,
    tenant_name: str,
    sheet_no: int,
    total_sheets: int,
    code: str,
    title: str,
    body: str,
) -> str:
    """Wrap schematic elements inside an IEC 61082 A3 landscape title-block SVG frame."""
    esc = html.escape
    cols = "".join(
        f'<line x1="{40 + i * 135}" y1="20" x2="{40 + i * 135}" y2="38" stroke="#cbd5e1" stroke-width="1"/>'
        f'<text x="{40 + i * 135 + 67}" y="33" text-anchor="middle" font-size="10" fill="#64748b" font-family="monospace">{i + 1}</text>'
        for i in range(8)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1160 720" class="schematic-svg">
  <rect x="20" y="20" width="1120" height="680" fill="#ffffff" stroke="#1e293b" stroke-width="1.5"/>
  <rect x="40" y="38" width="1080" height="596" fill="#fcfdff" stroke="#94a3b8" stroke-width="0.9"/>
  {cols}
  {body}
  <g transform="translate(40, 634)">
    <rect x="0" y="0" width="1080" height="54" fill="#f8fafc" stroke="#1e293b" stroke-width="1.2"/>
    <line x1="295" y1="0" x2="295" y2="54" stroke="#1e293b" stroke-width="1"/>
    <line x1="650" y1="0" x2="650" y2="54" stroke="#1e293b" stroke-width="1"/>
    <line x1="875" y1="0" x2="875" y2="54" stroke="#1e293b" stroke-width="1"/>
    <line x1="985" y1="0" x2="985" y2="54" stroke="#1e293b" stroke-width="1"/>
    <text x="12" y="17" font-size="8.5" font-weight="700" fill="#475569" font-family="monospace">{esc(tenant_name[:38])}</text>
    <text x="12" y="39" font-size="12.5" font-weight="700" fill="#0f172a" font-family="sans-serif">{esc(project.name[:34])}</text>
    <text x="307" y="17" font-size="8.5" fill="#64748b" font-family="sans-serif">SHEET TITLE ({esc(code)})</text>
    <text x="307" y="39" font-size="12.5" font-weight="700" fill="#1d4ed8" font-family="sans-serif">{esc(title)}</text>
    <text x="662" y="17" font-size="8.5" fill="#64748b" font-family="sans-serif">STANDARD / POWER</text>
    <text x="662" y="38" font-size="10.5" fill="#0f172a" font-family="monospace">{esc(project.settings.standard_profile)} | {esc(project.settings.power_system)}</text>
    <text x="887" y="17" font-size="8.5" fill="#64748b" font-family="sans-serif">VENDOR / PLC</text>
    <text x="887" y="37" font-size="9.5" fill="#0f172a" font-family="monospace">{esc(project.settings.preferred_vendor[:13])}</text>
    <text x="998" y="17" font-size="8.5" fill="#64748b" font-family="sans-serif">SHEET</text>
    <text x="998" y="39" font-size="13.5" font-weight="700" fill="#0f172a" font-family="monospace">{sheet_no:02d} / {total_sheets:02d}</text>
  </g>
</svg>'''


def _sheet_power(project: Project, tenant_name: str, summary: PowerSummary, total_sheets: int) -> str:
    esc = html.escape
    wire_txt = f"{summary.main_wire_sq} SQ ({summary.main_wire_awg})" if project.settings.standard_profile == "UL 508A" else f"{summary.main_wire_sq} SQ"
    parts = [
        f'<text x="72" y="84" font-size="12" font-weight="700" fill="#0f172a" font-family="monospace">INCOMING {summary.phases}P {summary.system_voltage_v}V 60Hz | SCCR: {summary.panel_sccr_ka}kA</text>',
        f'<text x="72" y="102" font-size="10" fill="#475569" font-family="monospace">MAIN CABLE: {esc(wire_txt)} | DEMAND: {summary.total_demand_current_a}A</text>',
    ]
    for i, (lbl, clr) in enumerate([("L1 (R)", "#1e293b"), ("L2 (S)", "#92400e"), ("L3 (T)", "#64748b"), ("PE", "#15803d")]):
        x = 120 + i * 28
        dash = 'stroke-dasharray="6,3"' if lbl == "PE" else ""
        parts.append(f'<line x1="{x}" y1="118" x2="{x}" y2="210" stroke="{clr}" stroke-width="2" {dash}/>')
        parts.append(f'<text x="{x}" y="113" text-anchor="middle" font-size="9" font-family="monospace" fill="{clr}">{lbl}</text>')

    # Main MCCB -Q0
    parts.append(f'''
    <g class="sch-device" data-device="-Q0" data-desc="Main MCCB {esc(summary.main_breaker_part)} ({summary.main_breaker_rating_a}AT / {summary.main_breaker_icu_ka}kA Icu)">
      <rect x="98" y="210" width="110" height="78" rx="4" fill="#eff6ff" stroke="#1d4ed8" stroke-width="1.8"/>
      <line x1="120" y1="210" x2="112" y2="257" stroke="#1d4ed8" stroke-width="2"/>
      <line x1="148" y1="210" x2="140" y2="257" stroke="#1d4ed8" stroke-width="2"/>
      <line x1="176" y1="210" x2="168" y2="257" stroke="#1d4ed8" stroke-width="2"/>
      <line x1="114" y1="238" x2="174" y2="238" stroke="#1d4ed8" stroke-width="1.2" stroke-dasharray="3,2"/>
      <text x="218" y="232" font-size="12" font-weight="700" fill="#1d4ed8" font-family="monospace">-Q0 (MAIN MCCB)</text>
      <text x="218" y="250" font-size="10" fill="#0f172a" font-family="monospace">{esc(summary.main_breaker_part)}</text>
      <text x="218" y="266" font-size="10" fill="#475569" font-family="monospace">{summary.main_breaker_rating_a}AT / {summary.main_breaker_icu_ka}kA | {esc(wire_txt)}</text>
    </g>''')

    bus_ys = [("L1", 336, "#1e293b"), ("L2", 361, "#92400e"), ("L3", 386, "#64748b"), ("PE", 411, "#15803d")]
    for i, (lbl, y, clr) in enumerate(bus_ys):
        x = 120 + i * 28
        dash = 'stroke-dasharray="6,3"' if lbl == "PE" else ""
        parts.append(f'<line x1="{x}" y1="{288 if i < 3 else 210}" x2="{x}" y2="{y}" stroke="{clr}" stroke-width="2" {dash}/>')
        parts.append(f'<circle cx="{x}" cy="{y}" r="3.5" fill="{clr}"/>')
        parts.append(f'<line x1="{x}" y1="{y}" x2="1080" y2="{y}" stroke="{clr}" stroke-width="2" {dash}/>')
        parts.append(f'<text x="1086" y="{y + 4}" font-size="9.5" font-weight="700" fill="{clr}" font-family="monospace">{lbl} → SH-02</text>')

    # SPD -F0
    parts.append('''
    <g class="sch-device" data-device="-F0" data-desc="Type 2 3-Phase Surge Protector VAL-MS 320/3+1 (40kA)">
      <line x1="250" y1="336" x2="250" y2="465" stroke="#1e293b" stroke-width="1.5"/>
      <line x1="270" y1="361" x2="270" y2="465" stroke="#92400e" stroke-width="1.5"/>
      <line x1="290" y1="386" x2="290" y2="465" stroke="#64748b" stroke-width="1.5"/>
      <rect x="235" y="465" width="84" height="72" rx="4" fill="#fffbeb" stroke="#d97706" stroke-width="1.6"/>
      <text x="277" y="494" text-anchor="middle" font-size="11" font-weight="700" fill="#b45309" font-family="monospace">-F0 SPD</text>
      <text x="277" y="512" text-anchor="middle" font-size="9" fill="#475569" font-family="monospace">Type2 40kA</text>
      <line x1="277" y1="537" x2="277" y2="574" stroke="#15803d" stroke-width="1.8" stroke-dasharray="4,2"/>
      <line x1="263" y1="574" x2="291" y2="574" stroke="#15803d" stroke-width="2"/>
      <line x1="268" y1="580" x2="286" y2="580" stroke="#15803d" stroke-width="1.5"/>
    </g>''')

    # Optional Step-Down Transformer -T1 (380/480V -> 220V for Servos/Control)
    if summary.transformer_part:
        parts.append(f'''
        <g class="sch-device" data-device="-T1" data-desc="Step-Down Transformer {esc(summary.transformer_part)} ({summary.transformer_kva}kVA, {summary.system_voltage_v}V→220V)">
          <line x1="450" y1="336" x2="450" y2="465" stroke="#1e293b" stroke-width="1.5"/>
          <line x1="490" y1="361" x2="490" y2="465" stroke="#92400e" stroke-width="1.5"/>
          <rect x="425" y="465" width="155" height="90" rx="4" fill="#eff6ff" stroke="#1d4ed8" stroke-width="1.6"/>
          <circle cx="472" cy="500" r="14" fill="none" stroke="#1d4ed8" stroke-width="1.6"/>
          <circle cx="472" cy="522" r="14" fill="none" stroke="#1d4ed8" stroke-width="1.6"/>
          <text x="530" y="494" text-anchor="middle" font-size="11" font-weight="700" fill="#1d4ed8" font-family="monospace">-T1 TR</text>
          <text x="530" y="512" text-anchor="middle" font-size="9" fill="#0f172a" font-family="monospace">{summary.transformer_kva}kVA</text>
          <text x="530" y="528" text-anchor="middle" font-size="8.5" fill="#475569" font-family="monospace">{summary.system_voltage_v}→220V</text>
          <text x="502" y="548" text-anchor="middle" font-size="8" fill="#475569" font-family="monospace">{esc(summary.transformer_part)}</text>
        </g>''')

    # Control Power SMPS -G1
    parts.append(f'''
    <g class="sch-device" data-device="-G1" data-desc="DC 24V SMPS {esc(summary.smps_selected_part)} (Rated {summary.smps_capacity_a}A / Load {summary.total_dc24v_current_a}A)">
      <line x1="720" y1="336" x2="720" y2="465" stroke="#1e293b" stroke-width="1.5"/>
      <line x1="755" y1="361" x2="755" y2="465" stroke="#92400e" stroke-width="1.5"/>
      <rect x="695" y="465" width="175" height="90" rx="4" fill="#f0fdf4" stroke="#059669" stroke-width="1.8"/>
      <text x="782" y="488" text-anchor="middle" font-size="12" font-weight="700" fill="#047857" font-family="monospace">-G1 SMPS (DC 24V)</text>
      <text x="782" y="508" text-anchor="middle" font-size="10" fill="#0f172a" font-family="monospace">{esc(summary.smps_selected_part)}</text>
      <text x="782" y="526" text-anchor="middle" font-size="10" fill="#475569" font-family="monospace">CAP: {summary.smps_capacity_a}A | LOAD: {summary.total_dc24v_current_a}A</text>
      <line x1="870" y1="492" x2="1080" y2="492" stroke="#dc2626" stroke-width="2"/>
      <text x="1084" y="496" font-size="9.5" font-weight="700" fill="#dc2626" font-family="monospace">+24V → SH-03</text>
      <line x1="870" y1="530" x2="1080" y2="530" stroke="#2563eb" stroke-width="2"/>
      <text x="1084" y="534" font-size="9.5" font-weight="700" fill="#2563eb" font-family="monospace">0V (COM)</text>
    </g>''')

    parts.append(f'''
    <g transform="translate(695, 110)">
      <rect x="0" y="0" width="385" height="172" rx="6" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1.2"/>
      <text x="16" y="25" font-size="11" font-weight="700" fill="#0f172a" font-family="sans-serif">Enclosure, SCCR &amp; Thermal Summary (SSOT)</text>
      <line x1="16" y1="35" x2="369" y2="35" stroke="#e2e8f0"/>
      <text x="16" y="56" font-size="10" fill="#334155" font-family="monospace">Power / SCCR : {summary.total_connected_kw}kW (Dem {summary.total_demand_kw}kW) | {summary.panel_sccr_ka}kA</text>
      <text x="16" y="78" font-size="10" fill="#334155" font-family="monospace">Heat Loss    : {summary.total_heat_loss_w} W ({summary.cooling_required_m3h} m³/h)</text>
      <text x="16" y="100" font-size="10" fill="#334155" font-family="monospace">Enclosure    : {esc(summary.enclosure_part)}</text>
      <text x="16" y="122" font-size="10" fill="#334155" font-family="monospace">Dimensions   : {esc(summary.enclosure_size_mm[:34])}</text>
      <text x="16" y="144" font-size="10" fill="#1d4ed8" font-family="monospace">Transformer  : {esc(summary.transformer_part or "Not required (Direct Mains)")}</text>
    </g>''')

    return _svg_frame(project, tenant_name, 1, total_sheets, "SH-01", "Main Power Distribution & Control Supply", "\n".join(parts))


def _sheet_drives_page(
    project: Project,
    tenant_name: str,
    chunk: list[LoadCalculationResult],
    page_idx: int,
    total_drive_pages: int,
    sheet_no: int,
    total_sheets: int,
) -> tuple[str, str, str]:
    """Render one paginated Power Drive sheet (up to 4 circuits per page with EPLAN macro tags)."""
    esc = html.escape
    suffix = "" if total_drive_pages == 1 else chr(65 + page_idx)
    code = f"SH-02{suffix}"
    title = f"Power Drive Circuits ({page_idx + 1}/{total_drive_pages})"
    parts = []

    for lbl, y, clr in [("L1", 72, "#1e293b"), ("L2", 90, "#92400e"), ("L3", 108, "#64748b")]:
        parts.append(f'<line x1="65" y1="{y}" x2="1095" y2="{y}" stroke="{clr}" stroke-width="1.8"/>')
        parts.append(f'<text x="48" y="{y + 4}" font-size="9" font-weight="700" fill="{clr}" font-family="monospace">{lbl}</text>')
        if page_idx + 1 < total_drive_pages:
            nxt = f"SH-02{chr(65 + page_idx + 1)}"
            parts.append(f'<text x="1098" y="{y + 4}" font-size="8.5" font-weight="700" fill="{clr}" font-family="monospace">→{nxt}</text>')

    if not chunk:
        parts.append('<text x="580" y="340" text-anchor="middle" font-size="14" fill="#64748b">No power loads registered.</text>')
        return code, title, _svg_frame(project, tenant_name, sheet_no, total_sheets, code, title, "\n".join(parts))

    col_w = 1020 / max(len(chunk), 1)
    for idx, c in enumerate(chunk):
        cx = int(75 + idx * col_w + col_w / 2)
        for di, (by, clr) in enumerate([(72, "#1e293b"), (90, "#92400e"), (108, "#64748b")]):
            wx = cx - 18 + di * 18
            parts.append(f'<circle cx="{wx}" cy="{by}" r="2.8" fill="{clr}"/>')
            parts.append(f'<line x1="{wx}" y1="{by}" x2="{wx}" y2="160" stroke="{clr}" stroke-width="1.4"/>')
            parts.append(f'<line x1="{wx}" y1="220" x2="{wx}" y2="290" stroke="{clr}" stroke-width="1.4"/>')
            parts.append(f'<line x1="{wx}" y1="385" x2="{wx}" y2="460" stroke="{clr}" stroke-width="1.4"/>')
            parts.append(f'<line x1="{wx}" y1="480" x2="{wx}" y2="522" stroke="{clr}" stroke-width="1.4"/>')

        parts.append(f'''
        <g class="sch-device" data-device="{esc(c.tag)}-Q" data-desc="{esc(c.name)} MCCB {esc(c.breaker_part)} ({c.breaker_rating_a}AT / {c.breaker_icu_ka}kA) | Macro: {esc(c.eplan_macro)}">
          <rect x="{cx - 48}" y="160" width="96" height="60" rx="4" fill="#eff6ff" stroke="#1d4ed8" stroke-width="1.5"/>
          <text x="{cx}" y="183" text-anchor="middle" font-size="10" font-weight="700" fill="#1d4ed8" font-family="monospace">MCCB {c.breaker_rating_a}A</text>
          <text x="{cx}" y="201" text-anchor="middle" font-size="8.5" fill="#334155" font-family="monospace">{esc(c.breaker_part[:15])}</text>
        </g>''')

        mid_label = "INVERTER" if c.load_type == "motor_inv" else ("SERVO" if c.load_type == "servo" else ("SSR/MC" if c.load_type == "heater" else "MC + THR"))
        mid_part = c.drive_part or c.contactor_part or "-"
        mid_fill = "#f0fdf4" if c.load_type in ("motor_inv", "servo") else "#fffbeb"
        mid_stroke = "#059669" if c.load_type in ("motor_inv", "servo") else "#d97706"
        wire_lbl = f"{c.wire_sq}SQ/{c.wire_awg}" if project.settings.standard_profile == "UL 508A" else f"{c.wire_sq} SQ"

        parts.append(f'''
        <g class="sch-device" data-device="{esc(c.tag)}-DRV" data-desc="{esc(c.name)} Drive: {esc(mid_part)} | In={c.rated_current_a}A | {esc(wire_lbl)} (ΔV {c.voltage_drop_pct}%) | EPLAN: {esc(c.eplan_macro)}">
          <rect x="{cx - 72}" y="290" width="144" height="95" rx="5" fill="{mid_fill}" stroke="{mid_stroke}" stroke-width="1.6"/>
          <text x="{cx}" y="312" text-anchor="middle" font-size="10" font-weight="700" fill="{mid_stroke}" font-family="monospace">{mid_label}</text>
          <text x="{cx}" y="330" text-anchor="middle" font-size="8.5" fill="#0f172a" font-family="monospace">{esc(mid_part[:20])}</text>
          <text x="{cx}" y="348" text-anchor="middle" font-size="8.5" fill="#475569" font-family="monospace">In={c.rated_current_a}A | {esc(wire_lbl)}</text>
          <text x="{cx}" y="365" text-anchor="middle" font-size="8" fill="#64748b" font-family="monospace">ΔV={c.voltage_drop_pct}% | Q={c.heat_loss_w}W</text>
          <text x="{cx}" y="379" text-anchor="middle" font-size="7.5" fill="#1d4ed8" font-family="monospace">{esc(c.eplan_macro)}</text>
        </g>''')

        parts.append(f'''
        <rect x="{cx - 40}" y="460" width="80" height="20" fill="#f1f5f9" stroke="#475569" stroke-width="1.2"/>
        <text x="{cx}" y="474" text-anchor="middle" font-size="9" font-family="monospace" fill="#0f172a">-X1 U/V/W</text>''')

        sym_lbl = "E" if c.load_type == "heater" else "M 3~"
        parts.append(f'''
        <g class="sch-device" data-device="{esc(c.iec_device_tag)}" data-desc="{esc(c.tag)} ({esc(c.name)}) | {esc(c.formula_trace)}">
          <circle cx="{cx}" cy="548" r="26" fill="#ffffff" stroke="#0f172a" stroke-width="2"/>
          <text x="{cx}" y="553" text-anchor="middle" font-size="12" font-weight="700" fill="#0f172a" font-family="monospace">{sym_lbl}</text>
          <text x="{cx}" y="592" text-anchor="middle" font-size="10" font-weight="700" fill="#1d4ed8" font-family="monospace">{esc(c.tag)}</text>
          <text x="{cx}" y="608" text-anchor="middle" font-size="9" fill="#334155" font-family="sans-serif">{esc(c.name[:22])}</text>
        </g>''')

    return code, title, _svg_frame(project, tenant_name, sheet_no, total_sheets, code, title, "\n".join(parts))


def _sheet_safety(project: Project, tenant_name: str, sheet_no: int, total_sheets: int) -> str:
    esc = html.escape
    saf = next((l for l in project.loads if l.load_type == "safety_circuit"), None)
    lvl = (saf.safety_level or "PLd") if saf else "None"
    estop_cnt = saf.quantity if saf else 0

    parts = [
        '<line x1="80" y1="95" x2="1080" y2="95" stroke="#dc2626" stroke-width="2"/>',
        '<text x="50" y="99" font-size="10" font-weight="700" fill="#dc2626" font-family="monospace">+24V</text>',
        '<line x1="80" y1="565" x2="1080" y2="565" stroke="#2563eb" stroke-width="2"/>',
        '<text x="50" y="569" font-size="10" font-weight="700" fill="#2563eb" font-family="monospace">0V</text>',
    ]

    if not saf:
        parts.append('''
        <rect x="270" y="250" width="620" height="120" rx="8" fill="#fef2f2" stroke="#dc2626" stroke-width="1.5"/>
        <text x="580" y="300" text-anchor="middle" font-size="15" font-weight="700" fill="#b91c1c">No Safety Circuit (E-Stop / Safety Relay) Configured</text>
        <text x="580" y="330" text-anchor="middle" font-size="11" fill="#7f1d1d">Add a Safety Circuit unit (PLd/PLe) for IEC 60204-1 / ISO 13849-1 compliance.</text>
        ''')
    else:
        parts.append(f'''
        <g class="sch-device" data-device="-S_EMG" data-desc="Dual-Channel 2NC Emergency Stop Loop ({estop_cnt} stations, {esc(lvl)})">
          <line x1="210" y1="95" x2="210" y2="210" stroke="#dc2626" stroke-width="1.8"/>
          <line x1="270" y1="95" x2="270" y2="210" stroke="#dc2626" stroke-width="1.8"/>
          <rect x="175" y="155" width="130" height="65" rx="5" fill="#fef2f2" stroke="#dc2626" stroke-width="1.6"/>
          <text x="240" y="182" text-anchor="middle" font-size="11" font-weight="700" fill="#b91c1c" font-family="monospace">E-STOP ({estop_cnt}EA)</text>
          <text x="240" y="202" text-anchor="middle" font-size="9" fill="#7f1d1d" font-family="monospace">Dual-CH 2NC ({esc(lvl)})</text>
          <line x1="210" y1="220" x2="210" y2="290" stroke="#dc2626" stroke-width="1.8"/>
          <line x1="270" y1="220" x2="270" y2="290" stroke="#dc2626" stroke-width="1.8"/>
        </g>

        <g class="sch-device" data-device="-K_SAF1" data-desc="Safety Relay Module ({esc(lvl)} / Cat.3-4) — EPLAN_M_SAFETY_DUAL.ema">
          <rect x="170" y="290" width="320" height="165" rx="6" fill="#fffbeb" stroke="#d97706" stroke-width="2"/>
          <text x="330" y="320" text-anchor="middle" font-size="13" font-weight="700" fill="#b45309" font-family="monospace">-K_SAF1 SAFETY RELAY</text>
          <text x="330" y="344" text-anchor="middle" font-size="10" fill="#334155" font-family="monospace">CH1: S11-S12 | CH2: S21-S22 | RESET: S33-S34</text>
          <text x="330" y="368" text-anchor="middle" font-size="10" fill="#334155" font-family="monospace">SAFETY OUT: 13-14, 23-24, 33-34 (3NO)</text>
          <text x="330" y="392" text-anchor="middle" font-size="10" fill="#047857" font-family="monospace">AUX STATUS: 41-42 → PLC DI (SAFETY_OK)</text>
          <text x="330" y="424" text-anchor="middle" font-size="11" font-weight="700" fill="#0f172a" font-family="monospace">ISO 13849-1 : {esc(lvl)} Redundant + EDM</text>
          <line x1="240" y1="455" x2="240" y2="565" stroke="#2563eb" stroke-width="1.8"/>
        </g>

        <g class="sch-device" data-device="-K_S1 / -K_S2" data-desc="Redundant Safety Power Cutoff Contactors with EDM NC feedback">
          <line x1="490" y1="350" x2="820" y2="350" stroke="#dc2626" stroke-width="1.8"/>
          <line x1="670" y1="350" x2="670" y2="410" stroke="#dc2626" stroke-width="1.8"/>
          <line x1="820" y1="350" x2="820" y2="410" stroke="#dc2626" stroke-width="1.8"/>
          <rect x="615" y="410" width="110" height="72" rx="4" fill="#eff6ff" stroke="#1d4ed8" stroke-width="1.6"/>
          <text x="670" y="440" text-anchor="middle" font-size="12" font-weight="700" fill="#1d4ed8" font-family="monospace">-K_S1 (COIL)</text>
          <text x="670" y="460" text-anchor="middle" font-size="9" fill="#475569" font-family="monospace">Safety MC #1</text>
          <line x1="670" y1="482" x2="670" y2="565" stroke="#2563eb" stroke-width="1.8"/>
          <rect x="765" y="410" width="110" height="72" rx="4" fill="#eff6ff" stroke="#1d4ed8" stroke-width="1.6"/>
          <text x="820" y="440" text-anchor="middle" font-size="12" font-weight="700" fill="#1d4ed8" font-family="monospace">-K_S2 (COIL)</text>
          <text x="820" y="460" text-anchor="middle" font-size="9" fill="#475569" font-family="monospace">Safety MC #2</text>
          <line x1="820" y1="482" x2="820" y2="565" stroke="#2563eb" stroke-width="1.8"/>
          <rect x="615" y="155" width="260" height="80" rx="5" fill="#f0fdf4" stroke="#059669" stroke-width="1.5"/>
          <text x="745" y="184" text-anchor="middle" font-size="11" font-weight="700" fill="#047857" font-family="monospace">EDM FEEDBACK LOOP</text>
          <text x="745" y="206" text-anchor="middle" font-size="9.5" fill="#334155" font-family="monospace">-K_S1(NC) ─ -K_S2(NC) ─ RESET PB → S34</text>
          <path d="M 615 195 L 430 195 L 430 290" fill="none" stroke="#059669" stroke-width="1.5" stroke-dasharray="5,3"/>
        </g>''')

    return _svg_frame(project, tenant_name, sheet_no, total_sheets, "SH-03", "Safety Circuit & Redundant Interlock (ISO 13849-1)", "\n".join(parts))


def _sheet_plc_page(
    project: Project,
    tenant_name: str,
    modules: list[PlcModule],
    inputs: list[PlcChannel],
    outputs: list[PlcChannel],
    page_idx: int,
    total_plc_pages: int,
    sheet_no: int,
    total_sheets: int,
) -> tuple[str, str, str]:
    esc = html.escape
    suffix = "" if total_plc_pages == 1 else chr(65 + page_idx)
    code = f"SH-04{suffix}"
    title = f"PLC I/O Wiring ({page_idx + 1}/{total_plc_pages})"
    parts = [
        f'<text x="75" y="76" font-size="12" font-weight="700" fill="#0f172a" font-family="monospace">PLC RACK: {esc(project.settings.plc_vendor)} ({len(modules)} SLOTS | SHEET {page_idx + 1}/{total_plc_pages})</text>',
        '''<rect x="75" y="96" width="235" height="500" rx="5" fill="#eff6ff" stroke="#1d4ed8" stroke-width="1.6"/>
        <text x="192" y="120" text-anchor="middle" font-size="11" font-weight="700" fill="#1d4ed8" font-family="monospace">PLC INPUT (DI / AI)</text>
        <line x1="75" y1="130" x2="310" y2="130" stroke="#93c5fd"/>''',
    ]
    for idx, ch in enumerate(inputs):
        y = 158 + idx * 36
        parts.append(f'''
        <g class="sch-device" data-device="{esc(ch.plc_address)}" data-desc="{esc(ch.io_type)} {esc(ch.plc_address)} | {esc(ch.signal_name)} | {esc(ch.terminal_tag)} / {esc(ch.wire_number)}">
          <text x="86" y="{y + 4}" font-size="9.5" font-weight="700" fill="#0f172a" font-family="monospace">{esc(ch.plc_address[:16])}</text>
          <text x="235" y="{y + 4}" font-size="8.5" fill="#475569" font-family="monospace">{esc(ch.wire_number)}</text>
          <line x1="310" y1="{y}" x2="372" y2="{y}" stroke="#1d4ed8" stroke-width="1.4"/>
          <rect x="372" y="{y - 9}" width="62" height="18" fill="#f8fafc" stroke="#475569"/>
          <text x="403" y="{y + 3}" text-anchor="middle" font-size="8.5" font-family="monospace" fill="#0f172a">{esc(ch.terminal_tag)}</text>
          <text x="442" y="{y + 4}" font-size="8.5" fill="#334155" font-family="sans-serif">{esc(ch.signal_name[:20])}</text>
        </g>''')

    parts.append('''
    <rect x="600" y="96" width="235" height="500" rx="5" fill="#f0fdf4" stroke="#059669" stroke-width="1.6"/>
    <text x="717" y="120" text-anchor="middle" font-size="11" font-weight="700" fill="#047857" font-family="monospace">PLC OUTPUT (DO / AO)</text>
    <line x1="600" y1="130" x2="835" y2="130" stroke="#86efac"/>''')

    for idx, ch in enumerate(outputs):
        y = 158 + idx * 36
        parts.append(f'''
        <g class="sch-device" data-device="{esc(ch.plc_address)}" data-desc="{esc(ch.io_type)} {esc(ch.plc_address)} | {esc(ch.signal_name)} | {esc(ch.terminal_tag)} / {esc(ch.wire_number)}">
          <text x="612" y="{y + 4}" font-size="9.5" font-weight="700" fill="#0f172a" font-family="monospace">{esc(ch.plc_address[:16])}</text>
          <text x="760" y="{y + 4}" font-size="8.5" fill="#475569" font-family="monospace">{esc(ch.wire_number)}</text>
          <line x1="835" y1="{y}" x2="895" y2="{y}" stroke="#059669" stroke-width="1.4"/>
          <rect x="895" y="{y - 9}" width="62" height="18" fill="#f8fafc" stroke="#475569"/>
          <text x="926" y="{y + 3}" text-anchor="middle" font-size="8.5" font-family="monospace" fill="#0f172a">{esc(ch.terminal_tag)}</text>
          <text x="965" y="{y + 4}" font-size="8.5" fill="#334155" font-family="sans-serif">{esc(ch.signal_name[:18])}</text>
        </g>''')

    return code, title, _svg_frame(project, tenant_name, sheet_no, total_sheets, code, title, "\n".join(parts))


def synthesize_schematics(
    project: Project,
    summary: PowerSummary,
    calcs: list[LoadCalculationResult],
    modules: list[PlcModule],
    channels: list[PlcChannel],
    tenant_name: str = "PanelCraft Organization",
) -> list[SchematicSheet]:
    """Synthesize auto-paginated multi-sheet IEC 61082 schematics covering 100% of power loads & PLC I/O."""
    power_loads = [c for c in calcs if c.load_type in ("motor_dol", "motor_inv", "servo", "heater")]
    drive_pages = [power_loads[i : i + 4] for i in range(0, max(len(power_loads), 1), 4)]

    all_in = [c for c in channels if c.io_type in ("DI", "AI")]
    all_out = [c for c in channels if c.io_type in ("DO", "AO")]
    plc_page_count = max(1, math.ceil(max(len(all_in), len(all_out)) / 12))

    total_sheets = 1 + len(drive_pages) + 1 + plc_page_count
    sheets: list[SchematicSheet] = []
    sn = 1

    # Sheet 01: Power Distribution
    sheets.append(
        SchematicSheet(
            sheet_no=sn,
            code="SH-01",
            title="Main Power Distribution",
            svg=_sheet_power(project, tenant_name, summary, total_sheets),
        )
    )
    sn += 1

    # Sheet 02x: Auto-Paginated Drive Circuits
    for idx, chunk in enumerate(drive_pages):
        code, title, svg = _sheet_drives_page(project, tenant_name, chunk, idx, len(drive_pages), sn, total_sheets)
        sheets.append(SchematicSheet(sheet_no=sn, code=code, title=title, svg=svg))
        sn += 1

    # Sheet 03: Safety Circuit
    sheets.append(
        SchematicSheet(
            sheet_no=sn,
            code="SH-03",
            title="Safety Circuit (ISO 13849-1)",
            svg=_sheet_safety(project, tenant_name, sn, total_sheets),
        )
    )
    sn += 1

    # Sheet 04x: Auto-Paginated PLC I/O Wiring
    for p_idx in range(plc_page_count):
        in_chunk = all_in[p_idx * 12 : (p_idx + 1) * 12]
        out_chunk = all_out[p_idx * 12 : (p_idx + 1) * 12]
        code, title, svg = _sheet_plc_page(project, tenant_name, modules, in_chunk, out_chunk, p_idx, plc_page_count, sn, total_sheets)
        sheets.append(SchematicSheet(sheet_no=sn, code=code, title=title, svg=svg))
        sn += 1

    return sheets


def export_dxf(
    project: Project,
    summary: PowerSummary,
    calcs: list[LoadCalculationResult],
) -> str:
    """Export a multi-sheet AutoCAD R12 DXF schematic set (A3 frames laid out in model space)."""
    entities: list[str] = []

    def add_line(x1: float, y1: float, x2: float, y2: float, layer: str = "WIRE") -> None:
        entities.extend([
            "0", "LINE", "8", layer,
            "10", f"{x1:.2f}", "20", f"{y1:.2f}", "30", "0.0",
            "11", f"{x2:.2f}", "21", f"{y2:.2f}", "31", "0.0",
        ])

    def add_rect(x: float, y: float, w: float, h: float, layer: str = "DEVICE") -> None:
        add_line(x, y, x + w, y, layer)
        add_line(x + w, y, x + w, y + h, layer)
        add_line(x + w, y + h, x, y + h, layer)
        add_line(x, y + h, x, y, layer)

    def add_text(x: float, y: float, text: str, height: float = 3.5, layer: str = "TEXT") -> None:
        safe = text.encode("ascii", "replace").decode("ascii").replace("\n", " ")
        entities.extend([
            "0", "TEXT", "8", layer,
            "10", f"{x:.2f}", "20", f"{y:.2f}", "30", "0.0",
            "40", f"{height:.2f}", "1", safe,
        ])

    def add_circle(cx: float, cy: float, r: float, layer: str = "DEVICE") -> None:
        entities.extend([
            "0", "CIRCLE", "8", layer,
            "10", f"{cx:.2f}", "20", f"{cy:.2f}", "30", "0.0",
            "40", f"{r:.2f}",
        ])

    power_loads = [c for c in calcs if c.load_type in ("motor_dol", "motor_inv", "servo", "heater")]
    pages = [power_loads[i : i + 5] for i in range(0, max(len(power_loads), 1), 5)]

    for page_idx, chunk in enumerate(pages):
        ox = page_idx * 450.0  # Separate A3 sheets horizontally by 450mm
        add_rect(ox + 0, 0, 420, 297, "BORDER")
        add_rect(ox + 10, 10, 400, 277, "BORDER")
        add_rect(ox + 10, 10, 400, 22, "TITLEBLOCK")
        add_text(ox + 15, 22, f"PANELCRAFT AI - {project.id} | SH-{page_idx + 1:02d}/{len(pages):02d} | {project.settings.standard_profile} | {project.settings.power_system}", 3.8, "TEXT")
        add_text(ox + 15, 14, f"MAIN: {summary.main_breaker_part} ({summary.main_breaker_rating_a}A/{summary.panel_sccr_ka}kA) | SMPS: {summary.smps_selected_part} | TR: {summary.transformer_part or 'NONE'}", 2.8, "TEXT")

        add_line(ox + 25, 245, ox + 395, 245, "POWER_BUS")
        add_text(ox + 15, 244, "L1-L3", 3.0, "TEXT")
        if page_idx == 0:
            add_rect(ox + 25, 255, 38, 18, "DEVICE")
            add_text(ox + 28, 262, f"-Q0 {summary.main_breaker_rating_a}A", 3.0, "TEXT")
            add_line(ox + 44, 255, ox + 44, 245, "POWER_BUS")

        step = min(68.0, 340.0 / max(len(chunk), 1))
        for i, c in enumerate(chunk):
            cx = ox + 60.0 + i * step
            add_line(cx, 245, cx, 215, "WIRE")
            add_rect(cx - 15, 195, 30, 20, "DEVICE")
            add_text(cx - 12, 204, f"Q {c.breaker_rating_a}A", 2.8, "TEXT")
            add_line(cx, 195, cx, 165, "WIRE")
            add_rect(cx - 19, 130, 38, 35, "DEVICE")
            add_text(cx - 16, 152, c.load_type.upper()[:10], 2.5, "TEXT")
            add_text(cx - 16, 142, f"{c.rated_current_a}A {c.wire_sq}SQ", 2.4, "TEXT")
            add_line(cx, 130, cx, 95, "WIRE")
            add_circle(cx, 82, 13, "DEVICE")
            add_text(cx - 5, 80, "M3~", 3.5, "TEXT")
            add_text(cx - 16, 60, c.tag, 3.0, "TEXT")

    dxf_lines = [
        "0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "0", "ENDSEC",
        "0", "SECTION", "2", "ENTITIES",
        *entities,
        "0", "ENDSEC", "0", "EOF",
    ]
    return "\n".join(dxf_lines) + "\n"
