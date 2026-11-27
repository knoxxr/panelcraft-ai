"""PanelCraft AI — Model Context Protocol (MCP) Server (JSON-RPC 2.0, Stdio + Streamable HTTP).

Implements MCP 2025-03-26 / 2024-11-05 with zero external SDK dependencies:
- 12 Industrial Control Panel SSOT Engineering Tools (sizing, IEC 60909/60890, BOM, PLC I/O, 2D layout, EPLAN export)
- Live MCP Resources & Resource Templates (panelcraft://...)
- Engineering Prompt Templates (RFP design, compliance audit, vendor quote comparison)

Usage (Stdio transport for Claude Desktop, Cursor, Windsurf, VS Code, Antigravity):
    python3 -m backend.mcp_server

Usage (Streamable HTTP transport):
    Mounted on FastAPI at POST /mcp (and discovery at GET /mcp)
"""

from __future__ import annotations

import json
import sys
import uuid
from typing import Any, Optional

from backend.auth import enforce_permission
from backend.engine.copilot import generate_interlock_code, parse_nl_spec
from backend.engine.macros import STANDARD_MACROS, generate_eplan_ema_xml, instantiate_macro_units
from backend.exporters import (
    export_bom_csv,
    export_eplan_aml,
    export_eplan_parts_csv,
    export_fat_checklist_md,
    export_io_csv,
    export_plcopen_xml,
    export_project_dxf,
    export_terminals_csv,
    export_wire_labels_csv,
)
from backend.models import LoadUnit, Project
from backend.storage import (
    get_llm_config,
    get_project,
    init_db,
    list_custom_macros,
    list_projects,
    list_tenants,
    record_audit_log,
    save_project,
)
from backend.version import get_app_version

MCP_PROTOCOL_VERSION = "2025-03-26"
SUPPORTED_VERSIONS = {"2025-03-26", "2024-11-05"}


def _compute_design(project: Project):
    # Lazy import avoids circular import when FastAPI mounts /mcp
    from backend.main import compute_full_design

    return compute_full_design(project)


# ---------------------------------------------------------------------------
# MCP Tool Definitions (JSON Schema)
# ---------------------------------------------------------------------------

MCP_TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_tenants",
        "description": "List all B2B manufacturer organization workspaces (tenants) with their default standard, electrical vendor, and PLC vendor.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "list_projects",
        "description": "List control panel engineering projects stored in PanelCraft AI SSOT (optionally filtered by tenant_id).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string", "description": "Optional organization tenant ID (e.g. TENANT-KBAT)."},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "get_panel_design_summary",
        "description": "Run deterministic electrical sizing, IEC 60909 short-circuit & selectivity, IEC 60890 thermal cooling, PLC I/O, 2D mounting plate layout, and ERC/DRC verification for a project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID (e.g. PRJ-BAT01)."},
            },
            "required": ["project_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "create_project_from_rfp",
        "description": "Parse a natural-language or RFP control panel specification (English or Korean), create and persist a new SSOT project, and return its full calculated engineering summary.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "spec_text": {"type": "string", "description": "Natural-language specification or RFP requirements text."},
                "project_name": {"type": "string", "description": "Optional custom project name."},
                "client": {"type": "string", "description": "Optional client/plant name."},
                "tenant_id": {"type": "string", "description": "Organization tenant ID (default TENANT-KBAT)."},
            },
            "required": ["spec_text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "add_load_unit",
        "description": "Add an electrical load or functional unit (motor_inv, motor_dol, servo, heater, solenoid_group, sensor_group, safety_circuit) to an existing project and recalculate the SSOT.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "tag": {"type": "string", "description": "Unique functional unit tag e.g. CONV_05"},
                "name": {"type": "string", "description": "Descriptive name of the load"},
                "load_type": {
                    "type": "string",
                    "enum": ["motor_inv", "motor_dol", "servo", "heater", "solenoid_group", "sensor_group", "safety_circuit"],
                },
                "power_kw": {"type": "number", "default": 1.5},
                "quantity": {"type": "integer", "default": 1, "minimum": 1},
                "voltage": {"type": "integer", "default": 380},
                "phases": {"type": "integer", "default": 3},
                "cable_length_m": {"type": "number", "default": 15.0},
                "safety_level": {"type": "string", "enum": ["PLc", "PLd", "PLe"]},
            },
            "required": ["project_id", "tag", "name", "load_type"],
            "additionalProperties": False,
        },
    },
    {
        "name": "apply_circuit_macro",
        "description": "Insert a standardized EPLAN circuit macro module (MACRO-CONV-VFD, MACRO-SERVO-2AX, MACRO-HEATER-PID, MACRO-PUMP-DOL, MACRO-PNEU-IO, MACRO-SAFETY-PLE) into a project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "macro_id": {
                    "type": "string",
                    "enum": [m.macro_id for m in STANDARD_MACROS],
                },
            },
            "required": ["project_id", "macro_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "switch_panel_vendor_or_standard",
        "description": "Switch preferred electrical vendor, PLC vendor, compliance standard, or IEC 60909/60890 supply/thermal parameters on a project and return the recalculated BOM, SCCR, and cooling summary.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "preferred_vendor": {
                    "type": "string",
                    "enum": ["LS Electric", "Schneider Electric", "Siemens", "Mitsubishi Electric", "ABB", "Fuji Electric", "Omron"],
                },
                "plc_vendor": {
                    "type": "string",
                    "enum": ["Mitsubishi Electric", "LS Electric", "Siemens", "Rockwell Automation", "Omron", "Beckhoff"],
                },
                "standard_profile": {"type": "string", "enum": ["IEC 60204-1", "KS C IEC 60364", "UL 508A"]},
                "power_system": {"type": "string", "enum": ["3P_380V_60Hz", "3P_440V_60Hz", "3P_480V_60Hz", "3P_220V_60Hz", "1P_220V_60Hz"]},
                "ambient_temp_c": {"type": "number"},
                "supply_transformer_kva": {"type": "number"},
                "supply_impedance_pct": {"type": "number"},
                "feeder_length_m": {"type": "number"},
                "enclosure_install_type": {"type": "string", "enum": ["freestanding_all_open", "wall_mounted", "bayed_side_by_side"]},
            },
            "required": ["project_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "run_engineering_verification",
        "description": "Execute deterministic ERC/DRC/Safety/IEC 60909/IEC 60890/2D Collision checks and AI Knowledge-Base reviews for a project.",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_bom_and_io_schedule",
        "description": "Retrieve the synchronized Multi-Vendor BOM (including duct-routed internal panel wire meters) and PLC rack + I/O channel allocation schedule.",
        "inputSchema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "generate_plc_interlock_st",
        "description": "Generate IEC 61131-3 Structured Text (ST) interlock & alarm routines from natural-language requirements mapped to the project's actual PLC I/O addresses.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "requirement_text": {"type": "string", "description": "Control interlock / alarm requirement in English or Korean."},
            },
            "required": ["project_id", "requirement_text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "move_mounting_plate_component",
        "description": "Reposition a component on the 2D Mounting Plate (mm coordinates) or reset to IEC 61439 auto-layout, returning real-time collision alerts (LAY-001/002/003) and updated duct-routed wire lengths.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "tag": {"type": "string", "description": "Component device tag e.g. -Q0, -F0, CONV_MAIN"},
                "x_mm": {"type": "number"},
                "y_mm": {"type": "number"},
                "reset": {"type": "boolean", "default": False, "description": "Set true to reset all overrides back to IEC 61439 auto-layout."},
            },
            "required": ["project_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "export_engineering_artifact",
        "description": "Generate and return a synchronized engineering deliverable text/XML/CSV for a project (eplan_aml, eplan_ema, plcopen_xml, plc_st, bom_csv, io_csv, terminals_csv, wire_labels_csv, fat_md, dxf).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "format": {
                    "type": "string",
                    "enum": [
                        "eplan_aml",
                        "eplan_ema",
                        "eplan_parts_csv",
                        "plcopen_xml",
                        "plc_st",
                        "bom_csv",
                        "io_csv",
                        "terminals_csv",
                        "wire_labels_csv",
                        "fat_md",
                        "dxf",
                    ],
                },
                "macro_file": {"type": "string", "description": "Optional target .ema filename when format='eplan_ema'."},
            },
            "required": ["project_id", "format"],
            "additionalProperties": False,
        },
    },
]

# ---------------------------------------------------------------------------
# MCP Resources & Prompt Definitions
# ---------------------------------------------------------------------------

MCP_STATIC_RESOURCES: list[dict[str, Any]] = [
    {
        "uri": "panelcraft://tenants",
        "name": "Organization Workspaces (Tenants)",
        "description": "B2B equipment manufacturer workspaces and default electrical/PLC standards.",
        "mimeType": "application/json",
    },
    {
        "uri": "panelcraft://projects",
        "name": "Control Panel Projects",
        "description": "All control panel SSOT projects with power system, vendor, and load counts.",
        "mimeType": "application/json",
    },
    {
        "uri": "panelcraft://macros",
        "name": "EPLAN Circuit Macro Library",
        "description": "Standard and company custom EPLAN Electric P8 .ema macro templates.",
        "mimeType": "application/json",
    },
]

MCP_RESOURCE_TEMPLATES: list[dict[str, Any]] = [
    {
        "uriTemplate": "panelcraft://projects/{project_id}/design",
        "name": "Computed Control Panel SSOT Design",
        "description": "Full electrical calculation, IEC 60909/60890 analysis, BOM, PLC I/O, and rule verification JSON.",
        "mimeType": "application/json",
    },
    {
        "uriTemplate": "panelcraft://projects/{project_id}/eplan.aml",
        "name": "EPLAN AutomationML (CAEX 2.15)",
        "description": "Synchronized EPLAN Electric P8 / Pro Panel AML exchange file.",
        "mimeType": "application/xml",
    },
    {
        "uriTemplate": "panelcraft://projects/{project_id}/plcopen.xml",
        "name": "PLCopen TC6 XML",
        "description": "Vendor-neutral IEC 61131-3 PLCopen TC6 XML project file.",
        "mimeType": "application/xml",
    },
    {
        "uriTemplate": "panelcraft://projects/{project_id}/main.st",
        "name": "PLC IEC 61131-3 Structured Text",
        "description": "Auto-generated PLC Main Control ST program mapped to actual I/O addresses.",
        "mimeType": "text/plain",
    },
]

MCP_PROMPTS: list[dict[str, Any]] = [
    {
        "name": "design_panel_from_rfp",
        "description": "End-to-end workflow to parse a customer RFP, verify IEC 60909/60890 & ISO 13849-1 compliance, and export EPLAN AML + BOM.",
        "arguments": [
            {"name": "rfp_text", "description": "Customer RFP or equipment specification text.", "required": True},
            {"name": "target_standard", "description": "IEC 60204-1, KS C IEC 60364, or UL 508A.", "required": False},
        ],
    },
    {
        "name": "audit_panel_compliance",
        "description": "Comprehensive engineering compliance audit covering ERC/DRC, IEC 60909 short-circuit selectivity, IEC 60890 cooling, and 2D collisions.",
        "arguments": [
            {"name": "project_id", "description": "Target Project ID (e.g. PRJ-BAT01).", "required": True},
        ],
    },
    {
        "name": "compare_vendor_quotes",
        "description": "Compare BOM cost, SCCR, and lead-time across multiple electrical equipment vendors (LS Electric, Schneider, Siemens, ABB).",
        "arguments": [
            {"name": "project_id", "description": "Target Project ID (e.g. PRJ-BAT01).", "required": True},
        ],
    },
]


# ---------------------------------------------------------------------------
# Tool Execution Engine
# ---------------------------------------------------------------------------

def _summarize_design(design) -> dict[str, Any]:
    ps = design.power_summary
    err_cnt = sum(1 for r in design.rule_checks if r.severity == "ERROR")
    warn_cnt = sum(1 for r in design.rule_checks if r.severity == "WARNING")
    return {
        "project_id": design.project.id,
        "project_name": design.project.name,
        "tenant_id": design.project.tenant_id,
        "standard": design.project.settings.standard_profile,
        "power_system": design.project.settings.power_system,
        "preferred_vendor": design.project.settings.preferred_vendor,
        "plc_vendor": design.project.settings.plc_vendor,
        "power_summary": {
            "total_connected_kw": ps.total_connected_kw,
            "total_demand_kw": ps.total_demand_kw,
            "total_demand_current_a": ps.total_demand_current_a,
            "main_breaker": f"{ps.main_breaker_part} ({ps.main_breaker_rating_a}AT / Icu {ps.main_breaker_icu_ka}kA)",
            "main_wire": f"{ps.main_wire_sq} mm2 ({ps.main_wire_awg})",
            "panel_sccr_ka": ps.panel_sccr_ka,
            "transformer": f"{ps.transformer_part} ({ps.transformer_kva}kVA)" if ps.transformer_part else None,
            "smps": f"{ps.smps_selected_part} ({ps.total_dc24v_current_a}A / {ps.smps_capacity_a}A)",
        },
        "iec60909_short_circuit": {
            "ik3_main_ka": ps.ik3_main_ka,
            "ip_peak_ka": ps.ip_peak_ka,
            "ik1_min_ka": ps.ik1_min_ka,
            "main_breaking_margin_pct": ps.main_breaking_margin_pct,
            "selectivity_summary": ps.selectivity_summary,
            "branches": [s.model_dump() for s in ps.selectivity_checks],
        },
        "iec60890_thermal": ps.thermal_analysis.model_dump() if ps.thermal_analysis else None,
        "plc_io": {
            "modules_count": len(design.plc_modules),
            "active_channels": len(design.plc_channels),
        },
        "mounting_plate_2d": {
            "enclosure": ps.enclosure_part,
            "size_mm": ps.enclosure_size_mm,
            "utilization_pct": design.panel_layout.utilization_pct,
            "total_panel_wire_m": design.panel_layout.total_panel_wire_m,
            "layout_issues": [i.model_dump() for i in design.panel_layout.layout_issues],
        },
        "bom": {
            "line_items": len(design.bom),
            "total_krw": design.bom_total_krw,
        },
        "verification": {
            "errors": err_cnt,
            "warnings": warn_cnt,
            "total_checks": len(design.rule_checks),
        },
        "schematic_sheets": [f"{sh.code}: {sh.title}" for sh in design.schematic_sheets],
    }


def execute_mcp_tool(
    name: str,
    arguments: dict[str, Any],
    user: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Execute a registered PanelCraft AI MCP tool and return structured JSON result."""
    init_db()
    args = arguments or {}

    if name == "list_tenants":
        return {"tenants": [t.model_dump() for t in list_tenants()]}

    if name == "list_projects":
        prjs = list_projects(tenant_id=args.get("tenant_id"))
        return {
            "projects": [
                {
                    "id": p.id,
                    "tenant_id": p.tenant_id,
                    "name": p.name,
                    "client": p.client,
                    "power_system": p.settings.power_system,
                    "standard": p.settings.standard_profile,
                    "vendor": p.settings.preferred_vendor,
                    "plc_vendor": p.settings.plc_vendor,
                    "load_count": len(p.loads),
                }
                for p in prjs
            ]
        }

    if name == "get_panel_design_summary":
        prj = get_project(str(args.get("project_id", "")))
        if not prj:
            raise ValueError(f"Project not found: {args.get('project_id')}")
        return _summarize_design(_compute_design(prj))

    if name == "create_project_from_rfp":
        actor = enforce_permission(user, "edit_project")
        spec_text = str(args.get("spec_text", "")).strip()
        if not spec_text:
            raise ValueError("spec_text is required.")
        cfg = get_llm_config()
        parsed = parse_nl_spec(spec_text, llm_config=cfg)
        prj = parsed.suggested_project
        if args.get("project_name"):
            prj.name = str(args["project_name"]).strip()
        if args.get("client"):
            prj.client = str(args["client"]).strip()
        if args.get("tenant_id"):
            prj.tenant_id = str(args["tenant_id"]).strip()
        saved = save_project(prj)
        record_audit_log(saved.tenant_id, saved.id, "MCP_RFP_CREATED", f"Created project via MCP from RFP ({len(saved.loads)} loads)", actor=actor)
        return {
            "engine_used": parsed.engine_used,
            "extracted_notes": parsed.extracted_notes,
            "design_summary": _summarize_design(_compute_design(saved)),
        }

    if name == "add_load_unit":
        actor = enforce_permission(user, "edit_project")
        prj = get_project(str(args.get("project_id", "")))
        if not prj:
            raise ValueError(f"Project not found: {args.get('project_id')}")
        ltype = args["load_type"]
        is_dc = ltype in ("solenoid_group", "sensor_group", "safety_circuit")
        unit = LoadUnit(
            id=f"mcp_{uuid.uuid4().hex[:6]}",
            tag=str(args["tag"]).strip(),
            name=str(args["name"]).strip(),
            load_type=ltype,
            power_kw=0.0 if is_dc else float(args.get("power_kw", 1.5)),
            quantity=int(args.get("quantity", 1)),
            voltage=24 if is_dc else int(args.get("voltage", 220 if ltype == "servo" else 380)),
            phases=0 if is_dc else int(args.get("phases", 1 if ltype == "servo" else 3)),
            cable_length_m=float(args.get("cable_length_m", 15.0)),
            safety_level=args.get("safety_level") or ("PLd" if ltype == "safety_circuit" else None),
        )
        prj.loads.append(unit)
        save_project(prj)
        record_audit_log(prj.tenant_id, prj.id, "MCP_LOAD_ADDED", f"Added load {unit.tag} ({unit.load_type}) via MCP", actor=actor)
        return {"added_unit": unit.model_dump(), "design_summary": _summarize_design(_compute_design(prj))}

    if name == "apply_circuit_macro":
        actor = enforce_permission(user, "edit_project")
        prj = get_project(str(args.get("project_id", "")))
        if not prj:
            raise ValueError(f"Project not found: {args.get('project_id')}")
        macro_id = str(args.get("macro_id", ""))
        units = instantiate_macro_units(macro_id, prj)
        if not units:
            raise ValueError(f"Macro not found: {macro_id}")
        prj.loads.extend(units)
        save_project(prj)
        record_audit_log(prj.tenant_id, prj.id, "MCP_MACRO_APPLIED", f"Applied macro {macro_id} (+{len(units)} units) via MCP", actor=actor)
        return {
            "macro_id": macro_id,
            "inserted_tags": [u.tag for u in units],
            "design_summary": _summarize_design(_compute_design(prj)),
        }

    if name == "switch_panel_vendor_or_standard":
        actor = enforce_permission(user, "edit_project")
        prj = get_project(str(args.get("project_id", "")))
        if not prj:
            raise ValueError(f"Project not found: {args.get('project_id')}")
        s = prj.settings
        for field in (
            "preferred_vendor",
            "plc_vendor",
            "standard_profile",
            "power_system",
            "ambient_temp_c",
            "supply_transformer_kva",
            "supply_impedance_pct",
            "feeder_length_m",
            "enclosure_install_type",
        ):
            if field in args and args[field] is not None:
                setattr(s, field, args[field])
        save_project(prj)
        record_audit_log(prj.tenant_id, prj.id, "MCP_SETTINGS_UPDATED", f"Updated settings ({s.preferred_vendor}/{s.plc_vendor}/{s.standard_profile}) via MCP", actor=actor)
        return _summarize_design(_compute_design(prj))

    if name == "run_engineering_verification":
        prj = get_project(str(args.get("project_id", "")))
        if not prj:
            raise ValueError(f"Project not found: {args.get('project_id')}")
        design = _compute_design(prj)
        return {
            "project_id": prj.id,
            "errors": sum(1 for r in design.rule_checks if r.severity == "ERROR"),
            "warnings": sum(1 for r in design.rule_checks if r.severity == "WARNING"),
            "checks": [r.model_dump() for r in design.rule_checks],
        }

    if name == "get_bom_and_io_schedule":
        prj = get_project(str(args.get("project_id", "")))
        if not prj:
            raise ValueError(f"Project not found: {args.get('project_id')}")
        design = _compute_design(prj)
        return {
            "project_id": prj.id,
            "bom_total_krw": design.bom_total_krw,
            "bom": [b.model_dump() for b in design.bom],
            "plc_modules": [m.model_dump() for m in design.plc_modules],
            "plc_channels": [ch.model_dump() for ch in design.plc_channels],
        }

    if name == "generate_plc_interlock_st":
        prj = get_project(str(args.get("project_id", "")))
        if not prj:
            raise ValueError(f"Project not found: {args.get('project_id')}")
        req_text = str(args.get("requirement_text", "")).strip()
        if not req_text:
            raise ValueError("requirement_text is required.")
        design = _compute_design(prj)
        res = generate_interlock_code(prj, design.plc_channels, req_text, llm_config=get_llm_config())
        return res.model_dump()

    if name == "move_mounting_plate_component":
        actor = enforce_permission(user, "edit_project")
        prj = get_project(str(args.get("project_id", "")))
        if not prj:
            raise ValueError(f"Project not found: {args.get('project_id')}")
        if args.get("reset"):
            prj.layout_overrides = {}
            action = "MCP_LAYOUT_RESET"
            detail = "Reset 2D mounting plate layout via MCP"
        else:
            tag = str(args.get("tag", "")).strip()
            if not tag or "x_mm" not in args or "y_mm" not in args:
                raise ValueError("Provide tag, x_mm, and y_mm (or reset=true).")
            overrides = dict(prj.layout_overrides)
            overrides[tag] = {"x_mm": round(float(args["x_mm"]), 1), "y_mm": round(float(args["y_mm"]), 1)}
            prj.layout_overrides = overrides
            action = "MCP_LAYOUT_MOVED"
            detail = f"Moved {tag} to ({args['x_mm']}, {args['y_mm']}) mm via MCP"
        save_project(prj)
        record_audit_log(prj.tenant_id, prj.id, action, detail, actor=actor)
        design = _compute_design(prj)
        return {
            "project_id": prj.id,
            "utilization_pct": design.panel_layout.utilization_pct,
            "total_panel_wire_m": design.panel_layout.total_panel_wire_m,
            "layout_issues": [i.model_dump() for i in design.panel_layout.layout_issues],
            "wire_length_summary": [w.model_dump() for w in design.panel_layout.wire_length_summary],
        }

    if name == "export_engineering_artifact":
        prj = get_project(str(args.get("project_id", "")))
        if not prj:
            raise ValueError(f"Project not found: {args.get('project_id')}")
        fmt = str(args.get("format", "")).strip()
        custom_macros = list_custom_macros(tenant_id=prj.tenant_id)
        design = _compute_design(prj)
        exporters = {
            "eplan_aml": lambda: (f"{prj.id}_EPLAN.aml", export_eplan_aml(design)),
            "eplan_ema": lambda: generate_eplan_ema_xml(prj, design.load_calculations, custom_macros=custom_macros, target_macro_file=args.get("macro_file")),
            "eplan_parts_csv": lambda: (f"{prj.id}_EPLAN_Parts.csv", export_eplan_parts_csv(design)),
            "plcopen_xml": lambda: (f"{prj.id}_PLCopen.xml", export_plcopen_xml(design)),
            "plc_st": lambda: (f"{prj.id}_MainControl.st", design.plc_st_code),
            "bom_csv": lambda: (f"{prj.id}_BOM.csv", export_bom_csv(design)),
            "io_csv": lambda: (f"{prj.id}_IO_Map.csv", export_io_csv(design)),
            "terminals_csv": lambda: (f"{prj.id}_Terminals.csv", export_terminals_csv(design)),
            "wire_labels_csv": lambda: (f"{prj.id}_WireLabels.csv", export_wire_labels_csv(design)),
            "fat_md": lambda: (f"{prj.id}_FAT_Checklist.md", export_fat_checklist_md(design)),
            "dxf": lambda: (f"{prj.id}_Schematic.dxf", export_project_dxf(design)),
        }
        if fmt not in exporters:
            raise ValueError(f"Unsupported format: {fmt}")
        fname, content = exporters[fmt]()
        return {"filename": fname, "format": fmt, "size_bytes": len(content.encode("utf-8")), "content": content}

    raise ValueError(f"Unknown MCP tool: {name}")


def read_mcp_resource(uri: str) -> dict[str, Any]:
    """Resolve a panelcraft:// MCP resource URI."""
    init_db()
    if uri == "panelcraft://tenants":
        return {"uri": uri, "mimeType": "application/json", "text": json.dumps([t.model_dump() for t in list_tenants()], ensure_ascii=False, indent=2)}
    if uri == "panelcraft://projects":
        return {"uri": uri, "mimeType": "application/json", "text": json.dumps(execute_mcp_tool("list_projects", {}), ensure_ascii=False, indent=2)}
    if uri == "panelcraft://macros":
        payload = {
            "standard_macros": [m.model_dump() for m in STANDARD_MACROS],
            "company_custom_macros": [m.model_dump() for m in list_custom_macros()],
        }
        return {"uri": uri, "mimeType": "application/json", "text": json.dumps(payload, ensure_ascii=False, indent=2)}

    if uri.startswith("panelcraft://projects/"):
        parts = uri[len("panelcraft://projects/") :].split("/", 1)
        if len(parts) == 2:
            pid, sub = parts
            prj = get_project(pid)
            if not prj:
                raise ValueError(f"Project not found: {pid}")
            design = _compute_design(prj)
            if sub == "design":
                return {"uri": uri, "mimeType": "application/json", "text": json.dumps(_summarize_design(design), ensure_ascii=False, indent=2)}
            if sub == "eplan.aml":
                return {"uri": uri, "mimeType": "application/xml", "text": export_eplan_aml(design)}
            if sub == "plcopen.xml":
                return {"uri": uri, "mimeType": "application/xml", "text": export_plcopen_xml(design)}
            if sub == "main.st":
                return {"uri": uri, "mimeType": "text/plain", "text": design.plc_st_code}

    raise ValueError(f"Unknown MCP resource URI: {uri}")


def get_mcp_prompt(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Render a reusable PanelCraft AI MCP engineering prompt."""
    args = arguments or {}
    if name == "design_panel_from_rfp":
        rfp = args.get("rfp_text", "")
        std = args.get("target_standard", "IEC 60204-1")
        return {
            "description": "End-to-end RFP-to-EPLAN control panel design workflow",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Use PanelCraft AI MCP tools to design an industrial control panel compliant with {std}:\n"
                            f"1. Call `create_project_from_rfp` with the RFP below.\n"
                            f"2. Call `run_engineering_verification` and fix any ERRORs (safety, voltage drop, IEC 60909 Icu, or 2D collisions).\n"
                            f"3. Summarize Power, IEC 60909 short-circuit selectivity, IEC 60890 cooling, PLC I/O, and BOM total.\n"
                            f"4. Call `export_engineering_artifact` for `eplan_aml` and `fat_md`.\n\nRFP:\n{rfp}"
                        ),
                    },
                }
            ],
        }
    if name == "audit_panel_compliance":
        pid = args.get("project_id", "PRJ-BAT01")
        return {
            "description": f"Compliance audit for {pid}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Perform a complete electrical & safety engineering audit on project `{pid}`:\n"
                            f"1. Call `get_panel_design_summary` and `run_engineering_verification`.\n"
                            f"2. Evaluate IEC 60909 breaker breaking margins & selectivity ratios.\n"
                            f"3. Verify IEC 60890 thermal margin & cooling equipment selection.\n"
                            f"4. Report prioritized corrective actions with IEC/UL standard citations."
                        ),
                    },
                }
            ],
        }
    if name == "compare_vendor_quotes":
        pid = args.get("project_id", "PRJ-BAT01")
        return {
            "description": f"Multi-vendor BOM cost & lead-time comparison for {pid}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Compare control panel BOM cost, SCCR, and lead-time for project `{pid}` across LS Electric, Schneider Electric, Siemens, and ABB "
                            f"using `switch_panel_vendor_or_standard` and present a Markdown comparison table."
                        ),
                    },
                }
            ],
        }
    raise ValueError(f"Unknown MCP prompt: {name}")


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 MCP Dispatcher (Shared by Stdio & Streamable HTTP)
# ---------------------------------------------------------------------------

def _rpc_ok(req_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _rpc_err(req_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


def handle_mcp_jsonrpc(
    payload: dict[str, Any],
    user: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """Process a single MCP JSON-RPC 2.0 request or notification."""
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        return _rpc_err(None, -32600, "Invalid Request: expected JSON-RPC 2.0 object.")

    req_id = payload.get("id")
    method = str(payload.get("method", ""))
    params = payload.get("params") or {}

    # Notifications have no 'id' and expect no JSON-RPC response body
    if method.startswith("notifications/"):
        return None

    try:
        if method == "initialize":
            req_ver = params.get("protocolVersion", MCP_PROTOCOL_VERSION)
            proto = req_ver if req_ver in SUPPORTED_VERSIONS else MCP_PROTOCOL_VERSION
            return _rpc_ok(
                req_id,
                {
                    "protocolVersion": proto,
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False},
                        "prompts": {"listChanged": False},
                    },
                    "serverInfo": {
                        "name": "panelcraft-ai-mcp",
                        "title": "PanelCraft AI Control Panel SSOT MCP Server",
                        "version": get_app_version(),
                    },
                    "instructions": (
                        "PanelCraft AI MCP Server provides deterministic industrial control panel engineering tools: "
                        "electrical capacity sizing, IEC 60909 short-circuit & selectivity, IEC 60890 thermal cooling, "
                        "7-vendor BOM, 6-vendor PLC I/O & ST interlocks, 2D mounting plate layout, and EPLAN AML/.ema export."
                    ),
                },
            )

        if method == "ping":
            return _rpc_ok(req_id, {})

        if method == "tools/list":
            return _rpc_ok(req_id, {"tools": MCP_TOOLS})

        if method == "tools/call":
            tool_name = str(params.get("name", ""))
            tool_args = params.get("arguments") or {}
            try:
                out = execute_mcp_tool(tool_name, tool_args, user=user)
                return _rpc_ok(
                    req_id,
                    {
                        "content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False, indent=2)}],
                        "structuredContent": out,
                        "isError": False,
                    },
                )
            except Exception as exc:
                return _rpc_ok(
                    req_id,
                    {
                        "content": [{"type": "text", "text": f"Error executing tool '{tool_name}': {exc}"}],
                        "isError": True,
                    },
                )

        if method == "resources/list":
            return _rpc_ok(req_id, {"resources": MCP_STATIC_RESOURCES})

        if method == "resources/templates/list":
            return _rpc_ok(req_id, {"resourceTemplates": MCP_RESOURCE_TEMPLATES})

        if method == "resources/read":
            uri = str(params.get("uri", ""))
            res = read_mcp_resource(uri)
            return _rpc_ok(req_id, {"contents": [res]})

        if method == "prompts/list":
            return _rpc_ok(req_id, {"prompts": MCP_PROMPTS})

        if method == "prompts/get":
            p_name = str(params.get("name", ""))
            p_args = params.get("arguments") or {}
            return _rpc_ok(req_id, get_mcp_prompt(p_name, p_args))

        return _rpc_err(req_id, -32601, f"Method not found: {method}")
    except Exception as exc:
        return _rpc_err(req_id, -32603, f"Internal MCP server error: {exc}")


def get_mcp_server_metadata(base_url: str = "http://localhost:8000") -> dict[str, Any]:
    """Return MCP server discovery metadata & ready-to-paste client configs."""
    return {
        "name": "panelcraft-ai-mcp",
        "version": get_app_version(),
        "protocol_version": MCP_PROTOCOL_VERSION,
        "transports": {
            "streamable_http": f"{base_url.rstrip('/')}/mcp",
            "stdio_command": ["python3", "-m", "backend.mcp_server"],
        },
        "tools_count": len(MCP_TOOLS),
        "resources_count": len(MCP_STATIC_RESOURCES) + len(MCP_RESOURCE_TEMPLATES),
        "prompts_count": len(MCP_PROMPTS),
        "tools": MCP_TOOLS,
        "resources": MCP_STATIC_RESOURCES,
        "resource_templates": MCP_RESOURCE_TEMPLATES,
        "prompts": MCP_PROMPTS,
        "client_configs": {
            "claude_desktop_stdio": {
                "mcpServers": {
                    "panelcraft-ai": {
                        "command": "python3",
                        "args": ["-m", "backend.mcp_server"],
                        "cwd": "/path/to/panelcraft-ai",
                    }
                }
            },
            "streamable_http": {
                "mcpServers": {
                    "panelcraft-ai": {
                        "url": f"{base_url.rstrip('/')}/mcp",
                        "headers": {"Authorization": "Bearer <OPTIONAL_JWT_TOKEN>"},
                    }
                }
            },
        },
    }


# ---------------------------------------------------------------------------
# Stdio Transport Runner (`python3 -m backend.mcp_server`)
# ---------------------------------------------------------------------------

def run_stdio_server() -> None:
    """Run MCP server over stdin/stdout (newline-delimited JSON-RPC 2.0 per MCP spec)."""
    init_db()
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        # Gracefully skip Content-Length header lines if a legacy LSP-style client sends them
        if line.lower().startswith("content-length:"):
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            resp = _rpc_err(None, -32700, f"Parse error: {exc}")
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            continue

        if isinstance(msg, list):
            batch_out = [r for item in msg if (r := handle_mcp_jsonrpc(item)) is not None]
            if batch_out:
                sys.stdout.write(json.dumps(batch_out, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        else:
            resp = handle_mcp_jsonrpc(msg)
            if resp is not None:
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    run_stdio_server()
