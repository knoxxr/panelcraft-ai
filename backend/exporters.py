"""Synchronized artifact exporters (EPLAN AML/XML, BOM CSV, I/O CSV, Terminal CSV, ST, DXF, Layout DXF, FAT)."""

from __future__ import annotations

import csv
import io
import uuid
import xml.etree.ElementTree as ET
from xml.dom import minidom

from backend.engine.layout import export_layout_dxf
from backend.engine.schematic import export_dxf
from backend.models import ComputedDesign


def export_bom_csv(design: ComputedDesign) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["No", "Category", "IEC Tags", "Manufacturer", "Part Number", "Specification", "Status", "Qty", "Unit", "Unit Price (KRW)", "Total Price (KRW)", "Lead Time (Days)"])
    for b in design.bom:
        writer.writerow([
            b.line_no,
            b.category,
            ", ".join(b.iec_tags),
            b.manufacturer,
            b.part_number,
            b.spec,
            b.lifecycle_status,
            b.quantity,
            b.unit,
            b.unit_price_krw,
            b.total_price_krw,
            b.lead_time_days,
        ])
    writer.writerow(["", "", "", "", "", "TOTAL", "", "", "", "", design.bom_total_krw, ""])
    return "\ufeff" + buf.getvalue()


def export_io_csv(design: ComputedDesign) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["IO Type", "PLC Address", "Rack Slot", "Point", "Terminal", "Wire No", "Unit Tag", "Signal Name", "Voltage"])
    for ch in design.plc_channels:
        writer.writerow([
            ch.io_type,
            ch.plc_address,
            ch.slot,
            ch.point_index,
            ch.terminal_tag,
            ch.wire_number,
            ch.unit_tag,
            ch.signal_name,
            ch.voltage,
        ])
    return "\ufeff" + buf.getvalue()


def export_terminals_csv(design: ComputedDesign) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Strip", "Terminal No", "Wire No", "SQ (mm2)", "Color", "From Device", "To Device", "Signal"])
    for t in design.terminals:
        writer.writerow([t.strip, t.terminal_no, t.wire_number, t.wire_sq, t.wire_color, t.from_device, t.to_device, t.signal])
    return "\ufeff" + buf.getvalue()


def export_eplan_aml(design: ComputedDesign) -> str:
    """Export AutomationML (CAEX 2.15) XML compatible with EPLAN Electric P8 Data Exchange."""
    p = design.project
    s = design.power_summary

    def _uid() -> str:
        return str(uuid.uuid4())

    def _add_attr(parent: ET.Element, name: str, value: str, unit: str | None = None) -> None:
        attrib = {"Name": name, "AttributeDataType": "xs:string"}
        if unit:
            attrib["Unit"] = unit
        a = ET.SubElement(parent, "Attribute", attrib)
        v = ET.SubElement(a, "Value")
        v.text = str(value)

    caex = ET.Element(
        "CAEXFile",
        {
            "FileName": f"{p.id}_EPLAN.aml",
            "SchemaVersion": "2.15",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        },
    )
    add_info = ET.SubElement(caex, "AdditionalInformation", {"AutomationMLVersion": "2.0"})
    writer_hdr = ET.SubElement(add_info, "WriterHeader")
    ET.SubElement(writer_hdr, "WriterName").text = "PanelCraft AI SSOT Engine"
    ET.SubElement(writer_hdr, "WriterID").text = "PanelCraft-AI"
    ET.SubElement(writer_hdr, "WriterVendor").text = "PanelCraft"
    ET.SubElement(writer_hdr, "WriterVersion").text = "0.2.0"

    ih = ET.SubElement(caex, "InstanceHierarchy", {"Name": f"PanelCraft_{p.id}"})
    panel_el = ET.SubElement(ih, "InternalElement", {"Name": "=A1+P1", "ID": _uid()})
    _add_attr(panel_el, "ProjectName", p.name)
    _add_attr(panel_el, "Client", p.client)
    _add_attr(panel_el, "StandardProfile", p.settings.standard_profile)
    _add_attr(panel_el, "PowerSystem", p.settings.power_system)
    _add_attr(panel_el, "EnclosurePartNumber", s.enclosure_part)
    _add_attr(panel_el, "EnclosureDimensions", s.enclosure_size_mm)
    _add_attr(panel_el, "TotalHeatDissipation", str(s.total_heat_loss_w), "W")

    # 1. Electrical Devices & BOM Parts
    dev_group = ET.SubElement(panel_el, "InternalElement", {"Name": "ElectricalDevices", "ID": _uid()})
    for b in design.bom:
        ie = ET.SubElement(dev_group, "InternalElement", {"Name": ", ".join(b.iec_tags) or f"ITEM_{b.line_no}", "ID": _uid()})
        _add_attr(ie, "Category", b.category)
        _add_attr(ie, "Manufacturer", b.manufacturer)
        _add_attr(ie, "OrderNumber", b.part_number)
        _add_attr(ie, "Specification", b.spec)
        _add_attr(ie, "Quantity", str(b.quantity), b.unit)
        _add_attr(ie, "LifecycleStatus", b.lifecycle_status)

    # 2. Functional Power Loads & Wiring Specs (with EPLAN Macro mapping)
    loads_group = ET.SubElement(panel_el, "InternalElement", {"Name": "PowerCircuits", "ID": _uid()})
    for c in design.load_calculations:
        ie = ET.SubElement(loads_group, "InternalElement", {"Name": c.tag, "ID": _uid()})
        _add_attr(ie, "IECDeviceTag", c.iec_device_tag)
        _add_attr(ie, "EPLANMacro", c.eplan_macro)
        _add_attr(ie, "Description", c.name)
        _add_attr(ie, "RatedCurrent", str(c.rated_current_a), "A")
        _add_attr(ie, "WireCrossSection", str(c.wire_sq), "mm2")
        _add_attr(ie, "VoltageDrop", str(c.voltage_drop_pct), "%")
        _add_attr(ie, "BreakerPartNumber", c.breaker_part)
        if c.drive_part:
            _add_attr(ie, "DrivePartNumber", c.drive_part)

    # 3. PLC Hardware Rack & I/O Channels (EPLAN PLC Exchange)
    plc_el = ET.SubElement(panel_el, "InternalElement", {"Name": f"PLC_Rack_{p.settings.plc_vendor}", "ID": _uid()})
    _add_attr(plc_el, "PLCVendor", p.settings.plc_vendor)
    for mod in design.plc_modules:
        m_el = ET.SubElement(plc_el, "InternalElement", {"Name": f"Slot_{mod.slot}_{mod.module_type}", "ID": _uid()})
        _add_attr(m_el, "Slot", str(mod.slot))
        _add_attr(m_el, "OrderNumber", mod.part_number)
        _add_attr(m_el, "Manufacturer", mod.manufacturer)
        _add_attr(m_el, "StartAddress", mod.start_address)
        _add_attr(m_el, "EndAddress", mod.end_address)
        for ch in [x for x in design.plc_channels if x.slot == mod.slot]:
            ch_el = ET.SubElement(m_el, "InternalElement", {"Name": ch.channel_id, "ID": _uid()})
            _add_attr(ch_el, "IOType", ch.io_type)
            _add_attr(ch_el, "LogicalAddress", ch.plc_address)
            _add_attr(ch_el, "TerminalDesignation", ch.terminal_tag)
            _add_attr(ch_el, "WireNumber", ch.wire_number)
            _add_attr(ch_el, "SymbolicName", ch.unit_tag)
            _add_attr(ch_el, "Comment", ch.signal_name)

    # 4. Mounting Plate 2D Layout Coordinates (EPLAN Pro Panel Exchange)
    layout_el = ET.SubElement(panel_el, "InternalElement", {"Name": "MountingPlate2DLayout", "ID": _uid()})
    _add_attr(layout_el, "PlateWidth", str(design.panel_layout.plate_w_mm), "mm")
    _add_attr(layout_el, "PlateHeight", str(design.panel_layout.plate_h_mm), "mm")
    for comp in design.panel_layout.components:
        ce = ET.SubElement(layout_el, "InternalElement", {"Name": comp.tag, "ID": _uid()})
        _add_attr(ce, "OrderNumber", comp.part_number)
        _add_attr(ce, "Zone", comp.zone)
        _add_attr(ce, "PosX", str(comp.x_mm), "mm")
        _add_attr(ce, "PosY", str(comp.y_mm), "mm")
        _add_attr(ce, "Width", str(comp.w_mm), "mm")
        _add_attr(ce, "Height", str(comp.h_mm), "mm")
        _add_attr(ce, "Depth", str(comp.d_mm), "mm")

    rough = ET.tostring(caex, encoding="utf-8")
    pretty = minidom.parseString(rough).toprettyxml(indent="  ", encoding="utf-8")
    return pretty.decode("utf-8")


def export_plcopen_xml(design: ComputedDesign) -> str:
    """Export IEC 61131-3 PLCopen TC6 XML compatible with TIA Portal, TwinCAT, Sysmac, GX Works, XG5000, Studio 5000."""
    p = design.project
    proj = ET.Element(
        "project",
        {"xmlns": "http://www.plcopen.org/xml/tc6_0201"},
    )
    ET.SubElement(
        proj,
        "fileHeader",
        {
            "companyName": design.tenant_name,
            "productName": "PanelCraft AI",
            "productVersion": "0.4.0",
            "creationDateTime": p.updated_at,
        },
    )
    ET.SubElement(proj, "contentHeader", {"name": f"{p.id}_{p.settings.plc_vendor}"})
    types_el = ET.SubElement(proj, "types")
    ET.SubElement(types_el, "dataTypes")
    pous_el = ET.SubElement(types_el, "pous")
    pou = ET.SubElement(pous_el, "pou", {"name": "PRG_MainControl", "pouType": "program"})
    body = ET.SubElement(pou, "body")
    st_el = ET.SubElement(body, "ST")
    xhtml = ET.SubElement(st_el, "xhtml", {"xmlns": "http://www.w3.org/1999/xhtml"})
    xhtml.text = design.plc_st_code

    instances = ET.SubElement(proj, "instances")
    configs = ET.SubElement(instances, "configurations")
    cfg = ET.SubElement(configs, "configuration", {"name": p.settings.plc_vendor})
    res = ET.SubElement(cfg, "resource", {"name": "MainRack"})
    gvars = ET.SubElement(res, "globalVars", {"name": "GVL_IO_Map"})
    for ch in design.plc_channels:
        var = ET.SubElement(gvars, "variable", {"name": f"{ch.io_type}_{ch.unit_tag}_{ch.point_index:02d}", "address": ch.plc_address})
        t_el = ET.SubElement(var, "type")
        ET.SubElement(t_el, "BOOL" if ch.io_type in ("DI", "DO") else "INT")
        doc = ET.SubElement(var, "documentation")
        dx = ET.SubElement(doc, "xhtml", {"xmlns": "http://www.w3.org/1999/xhtml"})
        dx.text = f"{ch.signal_name} ({ch.terminal_tag} / {ch.wire_number})"

    rough = ET.tostring(proj, encoding="utf-8")
    return minidom.parseString(rough).toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def export_fat_checklist_md(design: ComputedDesign) -> str:
    p = design.project
    s = design.power_summary
    lines = [
        f"# FAT / SAT 제어반 시운전 체크시트 — {p.name}",
        "",
        f"- **프로젝트 ID**: `{p.id}` | **고객사**: {p.client}",
        f"- **적용 규격**: `{p.settings.standard_profile}` | **주전원**: `{p.settings.power_system}`",
        f"- **선정 주 차단기**: `{s.main_breaker_part}` ({s.main_breaker_rating_a}AT) | **SMPS**: `{s.smps_selected_part}` ({s.smps_capacity_a}A)",
        f"- **외함 / 냉각**: `{s.enclosure_part}` ({s.enclosure_size_mm}) / {s.cooling_solution}",
        "",
        "## 1. 전원 및 안전 사전 점검 (Power-On & Safety Check)",
        "- [ ] 주전원 L1-L2-L3 상간 절연저항 측정 (500V DC 메거, 1MΩ 이상)",
        "- [ ] PE 보호접지 연속성 확인 (외함 도어, 중판, 모터 프레임 0.1Ω 이하)",
        f"- [ ] 주 차단기 `-Q0 ({s.main_breaker_part})` 투입 및 상회전 방향 확인",
        f"- [ ] SMPS `-G1 ({s.smps_selected_part})` 무부하/부하 출력 DC 24.0V ± 2% 확인",
        "- [ ] 비상정지(E-Stop) 동작 시 안전 릴레이 `-K_SAF1` 및 이중화 접촉기 즉시 차단 확인",
        "",
        "## 2. PLC I/O 포인트별 루프 테스트 (I/O Loop Check)",
        "| 체크 | 구분 | PLC 주소 | 단자번호 | 와이어 | 기기 태그 | 신호명 |",
        "| :---: | :---: | :--- | :--- | :--- | :--- | :--- |",
    ]
    for ch in design.plc_channels:
        lines.append(f"| [ ] | {ch.io_type} | `{ch.plc_address}` | `{ch.terminal_tag}` | `{ch.wire_number}` | {ch.unit_tag} | {ch.signal_name} |")

    lines.extend(["", "## 3. 자동 검도(ERC/DRC) 요약"])
    for r in design.rule_checks:
        lines.append(f"- **[{r.severity}] {r.rule_id} ({r.standard_ref})** — {r.title}: {r.detail}")
    return "\n".join(lines) + "\n"


def export_project_dxf(design: ComputedDesign) -> str:
    return export_dxf(design.project, design.power_summary, design.load_calculations)


def export_project_layout_dxf(design: ComputedDesign) -> str:
    return export_layout_dxf(design.project, design.panel_layout)


def export_wire_labels_csv(design: ComputedDesign) -> str:
    """Export wire ferrules & device nameplate markers for Brady/Phoenix/Brother printers."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["LabelType", "TagOrWireNo", "CrossSection", "Color", "From", "To", "Description"])
    for t in design.terminals:
        w.writerow(["WIRE_MARKER", t.wire_number, f"{t.wire_sq} SQ", t.wire_color, t.from_device, t.to_device, t.signal])
    for c in design.load_calculations:
        w.writerow(["DEVICE_PLATE", c.iec_device_tag, "-", "-", c.tag, c.breaker_part, c.name])
    return "\ufeff" + buf.getvalue()


def export_eplan_parts_csv(design: ComputedDesign) -> str:
    """Export EPLAN Electric P8 Parts Management compatible CSV."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["PartNumber", "Manufacturer", "ProductGroup", "Designation", "OrderNumber", "Quantity", "UnitPriceKRW"])
    for b in design.bom:
        w.writerow([b.part_number, b.manufacturer, b.category, b.spec, b.part_number, b.quantity, b.unit_price_krw])
    return "\ufeff" + buf.getvalue()


def export_engineering_dossier_html(design: ComputedDesign) -> str:
    """Generate a clean, printable HTML Engineering Calculation & BOM Report (Print -> PDF)."""
    import html as _h
    p = design.project
    s = design.power_summary
    bom_rows = "".join(
        f"<tr><td>{b.line_no}</td><td>{_h.escape(b.category)}</td><td><code>{_h.escape(b.part_number)}</code></td>"
        f"<td>{_h.escape(b.manufacturer)}</td><td>{_h.escape(b.spec)}</td><td style='text-align:right'>{b.quantity}</td>"
        f"<td style='text-align:right'>₩{b.total_price_krw:,}</td></tr>"
        for b in design.bom
    )
    calc_rows = "".join(
        f"<tr><td><code>{_h.escape(c.tag)}</code></td><td>{_h.escape(c.name)}</td><td>{c.rated_current_a}A</td>"
        f"<td>{c.wire_sq} SQ ({c.wire_awg})</td><td>{c.voltage_drop_pct}%</td><td><code>{_h.escape(c.breaker_part)}</code></td>"
        f"<td><code>{_h.escape(c.eplan_macro)}</code></td></tr>"
        for c in design.load_calculations
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{_h.escape(p.name)} — Engineering Dossier</title>
<style>body{{font-family:sans-serif;margin:32px;color:#0f172a;font-size:13px}}h1,h2{{margin:0 0 8px}}
table{{width:100%;border-collapse:collapse;margin:12px 0 24px}}th,td{{border:1px solid #cbd5e1;padding:6px 8px;text-align:left}}
th{{background:#f1f5f9}}code{{font-family:monospace;font-size:12px}}.meta{{background:#f8fafc;padding:12px;border:1px solid #cbd5e1;margin-bottom:18px}}</style>
</head><body>
<h1>Control Panel Engineering Dossier — {_h.escape(p.name)}</h1>
<div class="meta">
  <strong>Organization:</strong> {_h.escape(design.tenant_name)} | <strong>Project ID:</strong> <code>{_h.escape(p.id)}</code> |
  <strong>Standard:</strong> {_h.escape(p.settings.standard_profile)} | <strong>Power:</strong> {_h.escape(p.settings.power_system)}<br/>
  <strong>Main MCCB:</strong> {_h.escape(s.main_breaker_part)} ({s.main_breaker_rating_a}AT / SCCR {s.panel_sccr_ka}kA) |
  <strong>Main Cable:</strong> {s.main_wire_sq} SQ ({s.main_wire_awg}) |
  <strong>SMPS:</strong> {_h.escape(s.smps_selected_part)} ({s.smps_capacity_a}A) |
  <strong>Transformer:</strong> {_h.escape(s.transformer_part or "None")} |
  <strong>Enclosure:</strong> {_h.escape(s.enclosure_part)} ({_h.escape(s.enclosure_size_mm)}) |
  <strong>Heat Loss:</strong> {s.total_heat_loss_w}W
</div>
<h2>1. Branch Circuit Calculations &amp; EPLAN Macros</h2>
<table><thead><tr><th>Tag</th><th>Load</th><th>Rated A</th><th>Wire</th><th>ΔV</th><th>Breaker</th><th>EPLAN Macro</th></tr></thead><tbody>{calc_rows}</tbody></table>
<h2>2. Unified Vendor BOM (Total: ₩{design.bom_total_krw:,})</h2>
<table><thead><tr><th>#</th><th>Category</th><th>Part Number</th><th>Manufacturer</th><th>Spec</th><th>Qty</th><th>Total</th></tr></thead><tbody>{bom_rows}</tbody></table>
</body></html>"""


def export_full_package_zip(design: ComputedDesign) -> bytes:
    """Bundle all synchronized engineering deliverables into a single downloadable ZIP archive."""
    import zipfile
    pid = design.project.id
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"EPLAN/{pid}_EPLAN.aml", export_eplan_aml(design).encode("utf-8"))
        zf.writestr(f"EPLAN/{pid}_EPLAN_Parts.csv", export_eplan_parts_csv(design).encode("utf-8"))
        zf.writestr(f"PLC/{pid}_PLCopen.xml", export_plcopen_xml(design).encode("utf-8"))
        zf.writestr(f"PLC/{pid}_MainControl.st", design.plc_st_code.encode("utf-8"))
        zf.writestr(f"PLC/{pid}_IO_Map.csv", export_io_csv(design).encode("utf-8"))
        zf.writestr(f"CAD/{pid}_Schematic_MultiSheet.dxf", export_project_dxf(design).encode("utf-8"))
        zf.writestr(f"CAD/{pid}_MountingPlate_2D.dxf", export_project_layout_dxf(design).encode("utf-8"))
        zf.writestr(f"CAD/SVG/{pid}_MountingPlate_2D.svg", design.panel_layout.svg.encode("utf-8"))
        zf.writestr(f"CAD/SVG/{pid}_MountingPlate_Thermal.svg", design.panel_layout.svg_thermal.encode("utf-8"))
        for sh in design.schematic_sheets:
            zf.writestr(f"CAD/SVG/{pid}_{sh.code}.svg", sh.svg.encode("utf-8"))
        zf.writestr(f"BOM/{pid}_BOM.csv", export_bom_csv(design).encode("utf-8"))
        zf.writestr(f"BOM/{pid}_Terminals_Wires.csv", export_terminals_csv(design).encode("utf-8"))
        zf.writestr(f"BOM/{pid}_WireMarkers_Labels.csv", export_wire_labels_csv(design).encode("utf-8"))
        zf.writestr(f"DOCS/{pid}_Engineering_Report.html", export_engineering_dossier_html(design).encode("utf-8"))
        zf.writestr(f"DOCS/{pid}_FAT_Checklist.md", export_fat_checklist_md(design).encode("utf-8"))
    return buf.getvalue()

