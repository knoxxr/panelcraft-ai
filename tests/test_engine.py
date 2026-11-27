"""Comprehensive unit & integration tests for PanelCraft AI v0.2 engineering engine."""

from __future__ import annotations

import io
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path

from backend.engine.copilot import generate_interlock_code, parse_nl_spec
from backend.engine.io_plc import build_plc_and_io
from backend.engine.layout import export_layout_dxf
from backend.engine.llm_gateway import test_llm_connection
from backend.engine.schematic import export_dxf
from backend.exporters import (
    export_bom_csv,
    export_eplan_aml,
    export_fat_checklist_md,
    export_io_csv,
)
from backend.importers import (
    export_catalog_template_csv,
    export_load_template_csv,
    extract_pdf_text,
    parse_catalog_file,
    parse_loads_file,
)
from backend.main import compute_full_design
from backend.models import CopilotParseRequest, LlmConfig, LoadUnit, Project, ProjectSettings
from backend.storage import (
    create_revision,
    diff_revisions,
    get_llm_config,
    init_db,
    list_custom_catalog,
    list_projects,
    list_revisions,
    save_llm_config,
    save_project,
    upsert_custom_catalog_items,
)


def _build_minimal_xlsx(rows: list[list[str]]) -> bytes:
    """Build a genuine Office Open XML (.xlsx) workbook in memory for testing."""
    buf = io.BytesIO()
    row_xml_parts = []
    for r_idx, row in enumerate(rows, start=1):
        cells = []
        for c_idx, val in enumerate(row):
            col_let = chr(ord("A") + c_idx)
            cells.append(f'<c r="{col_let}{r_idx}" t="inlineStr"><is><t>{val}</t></is></c>')
        row_xml_parts.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(row_xml_parts)}</sheetData></worksheet>'
    )
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml.encode("utf-8"))
    return buf.getvalue()


def _build_minimal_pdf(text_ascii: str) -> bytes:
    """Build a valid FlateDecode-compressed minimal PDF byte stream for testing."""
    content = f"BT /F1 12 Tf 72 720 Td ({text_ascii}) Tj ET".encode("utf-8")
    compressed = zlib.compress(content)
    return (
        b"%PDF-1.4\n1 0 obj\n<< /Length "
        + str(len(compressed)).encode("ascii")
        + b" /Filter /FlateDecode >>\nstream\n"
        + compressed
        + b"\nendstream\nendobj\n%%EOF\n"
    )


class TestPanelCraftEngine(unittest.TestCase):
    def _sample_project(self) -> Project:
        return Project(
            id="PRJ-TEST01",
            name="테스트 컨베이어 제어반",
            settings=ProjectSettings(
                power_system="3P_380V_60Hz",
                preferred_vendor="LS Electric",
                plc_vendor="Mitsubishi Electric",
                io_spare_ratio=0.20,
            ),
            loads=[
                LoadUnit(id="u1", tag="CONV_01", name="메인 컨베이어", load_type="motor_inv", power_kw=1.5, quantity=4, voltage=380, phases=3, cable_length_m=20.0),
                LoadUnit(id="u2", tag="SRV_01", name="리프트 서보", load_type="servo", power_kw=0.75, quantity=2, voltage=220, phases=1, cable_length_m=15.0),
                LoadUnit(id="u3", tag="SOL_01", name="실린더 밸브", load_type="solenoid_group", quantity=12, voltage=24, phases=0, has_surge_suppressor=False),
                LoadUnit(id="u4", tag="SAFETY_01", name="비상정지 회로", load_type="safety_circuit", quantity=2, voltage=24, phases=0, safety_level="PLd"),
            ],
        )

    def test_electrical_calculations_and_vendor_switch(self) -> None:
        prj = self._sample_project()
        design_ls = compute_full_design(prj, custom_catalog=[])

        self.assertAlmostEqual(design_ls.power_summary.total_connected_kw, 7.5, places=2)
        self.assertGreater(design_ls.power_summary.main_breaker_rating_a, 15)
        self.assertGreater(design_ls.bom_total_krw, 1_000_000)
        self.assertTrue(any(b.manufacturer == "LS Electric" for b in design_ls.bom))

        prj.settings.preferred_vendor = "Schneider Electric"
        prj.settings.plc_vendor = "Siemens"
        design_sch = compute_full_design(prj, custom_catalog=[])
        self.assertTrue(any(b.manufacturer == "Schneider Electric" for b in design_sch.bom))
        self.assertTrue(any(ch.plc_address.startswith("%I") for ch in design_sch.plc_channels if ch.io_type == "DI"))

    def test_plc_io_spare_and_st_generation(self) -> None:
        prj = self._sample_project()
        modules, channels, st_code = build_plc_and_io(prj)
        self.assertGreaterEqual(len(modules), 4)
        self.assertGreater(len(channels), 20)
        self.assertIn("VAR_GLOBAL", st_code)
        self.assertIn("PROGRAM PRG_MainControl", st_code)

    def test_deterministic_rules_and_ai_review(self) -> None:
        prj = self._sample_project()
        design = compute_full_design(prj, custom_catalog=[])
        rule_ids = {r.rule_id for r in design.rule_checks}
        self.assertIn("AI-KB-101", rule_ids)
        self.assertEqual(sum(1 for r in design.rule_checks if r.severity == "ERROR"), 0)

        prj.loads = [l for l in prj.loads if l.load_type != "safety_circuit"]
        design_no_saf = compute_full_design(prj, custom_catalog=[])
        self.assertTrue(any(r.rule_id == "SAF-001" and r.severity == "ERROR" for r in design_no_saf.rule_checks))

    def test_schematic_svg_dxf_and_eplan_aml_export(self) -> None:
        prj = self._sample_project()
        design = compute_full_design(prj, custom_catalog=[])
        self.assertGreaterEqual(len(design.schematic_sheets), 4)
        for sh in design.schematic_sheets:
            self.assertIn("<svg", sh.svg)

        dxf = export_dxf(prj, design.power_summary, design.load_calculations)
        self.assertIn("ENTITIES", dxf)
        self.assertIn("EOF", dxf)

        # EPLAN AutomationML (CAEX 2.15) XML validity & content checks
        aml_xml = export_eplan_aml(design)
        root = ET.fromstring(aml_xml)
        self.assertEqual(root.tag, "CAEXFile")
        self.assertEqual(root.attrib.get("SchemaVersion"), "2.15")
        self.assertIn("MountingPlate2DLayout", aml_xml)
        self.assertIn("LogicalAddress", aml_xml)
        self.assertIn("OrderNumber", aml_xml)

        self.assertIn("Part Number", export_bom_csv(design))
        self.assertIn("PLC Address", export_io_csv(design))
        self.assertIn("FAT / SAT", export_fat_checklist_md(design))

    def test_mounting_plate_2d_layout_and_dxf(self) -> None:
        prj = self._sample_project()
        design = compute_full_design(prj, custom_catalog=[])
        lay = design.panel_layout
        self.assertGreater(lay.plate_w_mm, 500)
        self.assertGreater(lay.utilization_pct, 10.0)
        self.assertTrue(any(c.zone == "POWER" for c in lay.components))
        self.assertTrue(any(c.zone == "DRIVE" for c in lay.components))
        self.assertTrue(any(c.zone == "CONTROL" for c in lay.components))
        self.assertTrue(any(c.zone == "TERMINAL" for c in lay.components))
        self.assertIn("<svg", lay.svg)
        self.assertIn("Thermal Heatmap", lay.svg_thermal)

        lay_dxf = export_layout_dxf(prj, lay)
        self.assertIn("MOUNTING_PLATE", lay_dxf)
        self.assertIn("ZONE_CONTROL", lay_dxf)

    def test_excel_xlsx_and_csv_importers_with_custom_catalog_override(self) -> None:
        # 1. Load schedule .xlsx import
        xlsx_bytes = _build_minimal_xlsx([
            ["태그", "부하명", "유형", "용량(kW)", "수량", "전압", "케이블길이", "안전등급"],
            ["CONV_X1", "엑셀 컨베이어", "인버터", "2.2", "3", "380", "25", ""],
            ["SAF_X1", "엑셀 비상정지", "안전회로", "0", "2", "24", "10", "PLe"],
        ])
        units, skipped, _ = parse_loads_file("schedule.xlsx", xlsx_bytes)
        self.assertEqual(len(units), 2)
        self.assertEqual(skipped, 0)
        self.assertEqual(units[0].load_type, "motor_inv")
        self.assertEqual(units[1].safety_level, "PLe")

        # 2. CSV template round-trip
        tpl_units, tpl_skip, _ = parse_loads_file("loads.csv", export_load_template_csv().encode("utf-8"))
        self.assertEqual(len(tpl_units), 7)
        self.assertEqual(tpl_skip, 0)

        # 3. Company Custom Catalog import & BOM priority override
        cat_items, _ = parse_catalog_file("catalog.csv", export_catalog_template_csv().encode("utf-8"))
        self.assertEqual(len(cat_items), 5)

        prj = self._sample_project()
        design_custom = compute_full_design(prj, custom_catalog=cat_items)
        part_numbers = {b.part_number for b in design_custom.bom}
        self.assertIn("LSLV0015G100-STD", part_numbers)
        self.assertTrue(any("사내표준" in b.lifecycle_status for b in design_custom.bom))

    def test_pdf_rfp_extractor_and_interlock_generator(self) -> None:
        pdf_bytes = _build_minimal_pdf("3P 380V, Inverter Conveyor 2.2kW 3 units, Servo 750W 2 axes, Heater 4kW 1 unit, E-Stop 2 units PLe")
        extracted = extract_pdf_text(pdf_bytes)
        self.assertIn("Inverter Conveyor", extracted)

        parsed = parse_nl_spec(CopilotParseRequest(prompt=extracted, project_name="PDF RFP 테스트"))
        ltypes = {l.load_type for l in parsed.suggested_project.loads}
        self.assertTrue({"motor_inv", "servo", "heater", "safety_circuit"}.issubset(ltypes))

        # Natural-language IEC 61131-3 ST Interlock & Alarm Generator
        design = compute_full_design(parsed.suggested_project, custom_catalog=[])
        il = generate_interlock_code(
            design,
            "비상정지 시 전체 정지, 서보 원점 복귀 전 기동 금지, 히터 190도 초과 시 과승온 차단",
            llm_cfg=LlmConfig(provider="builtin"),
        )
        self.assertIn("FUNCTION_BLOCK FB_InterlockAndAlarm", il.st_code)
        self.assertIn("190", il.st_code)
        self.assertGreaterEqual(len(il.alarms), 3)

        # Built-in LLM connection test
        conn_res = test_llm_connection(LlmConfig(provider="builtin"))
        self.assertTrue(conn_res["ok"])

    def test_sqlite_storage_catalog_llm_and_ecn_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            init_db(db)
            self.assertGreaterEqual(len(list_projects(db_path=db)), 2)

            # LLM Config persistence
            cfg = LlmConfig(provider="ollama", base_url="http://192.168.0.10:11434", model="qwen2.5:14b")
            save_llm_config(cfg, db)
            loaded_cfg = get_llm_config(db)
            self.assertEqual(loaded_cfg.provider, "ollama")
            self.assertEqual(loaded_cfg.model, "qwen2.5:14b")

            # Custom catalog persistence
            cat_items, _ = parse_catalog_file("cat.csv", export_catalog_template_csv().encode("utf-8"))
            upsert_custom_catalog_items(cat_items, tenant_id="TENANT-KBAT", db_path=db)
            self.assertEqual(len(list_custom_catalog(tenant_id="TENANT-KBAT", db_path=db)), 5)

            # Revision & ECN Diff
            prj = self._sample_project()
            save_project(prj, db)
            d1 = compute_full_design(prj, custom_catalog=[])
            r1 = create_revision(
                prj.id, "Rev.A", "Draft", "테스터", "초도",
                d1.bom_total_krw, len(d1.plc_channels), 0,
                {"loads": [l.model_dump() for l in prj.loads], "bom": [b.model_dump() for b in d1.bom]},
                db_path=db,
            )
            prj.loads[0].quantity = 6
            d2 = compute_full_design(prj, custom_catalog=[])
            r2 = create_revision(
                prj.id, "Rev.B", "Released", "테스터", "컨베이어 증설",
                d2.bom_total_krw, len(d2.plc_channels), 0,
                {"loads": [l.model_dump() for l in prj.loads], "bom": [b.model_dump() for b in d2.bom]},
                db_path=db,
            )
            self.assertEqual(len(list_revisions(prj.id, db)), 2)
            diff = diff_revisions(r1, r2)
            self.assertGreater(diff["bom_cost_delta_krw"], 0)
            self.assertGreater(diff["io_points_delta"], 0)

    def test_version_updater_and_revision_rollback(self) -> None:
        from backend.models import UpdateConfig
        from backend.storage import get_revision, get_update_config, save_update_config, update_revision_status
        from backend.updater import build_github_links
        from backend.version import get_app_version, is_newer_version, read_changelog_entries

        self.assertEqual(get_app_version(), "0.6.0")
        self.assertTrue(is_newer_version("0.7.0", "0.6.0"))
        self.assertFalse(is_newer_version("0.6.0", "0.6.0"))
        self.assertGreaterEqual(len(read_changelog_entries()), 6)

        links = build_github_links("myorg/panelcraft-ai", "0.6.0")
        self.assertIn("issues/new", links["new_bug_url"])
        self.assertIn("discussions", links["discussions_url"])

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test_v3.db"
            init_db(db)
            save_update_config(UpdateConfig(github_repo="myorg/panelcraft-ai", channel="beta"), db)
            ucfg = get_update_config(db)
            self.assertEqual(ucfg.github_repo, "myorg/panelcraft-ai")
            self.assertEqual(ucfg.channel, "beta")

            prj = self._sample_project()
            save_project(prj, db)
            d1 = compute_full_design(prj, custom_catalog=[])
            r1 = create_revision(
                prj.id, "Rev.A", "Draft", "Engineer", "Initial",
                d1.bom_total_krw, len(d1.plc_channels), 0,
                {"settings": prj.settings.model_dump(), "loads": [l.model_dump() for l in prj.loads], "bom": [b.model_dump() for b in d1.bom]},
                db_path=db,
            )
            promoted = update_revision_status(r1.id, "Released", db)
            self.assertIsNotNone(promoted)
            self.assertEqual(promoted.status, "Released")
            fetched = get_revision(r1.id, db)
            self.assertIsNotNone(fetched)
            self.assertEqual(len(fetched.snapshot_json["loads"]), 4)

    def test_multitenant_global_vendors_and_plcopen_xml(self) -> None:
        from backend.exporters import export_plcopen_xml
        from backend.models import TenantOrg
        from backend.storage import list_tenants, save_tenant

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test_mt.db"
            init_db(db)
            tenants = list_tenants(db)
            self.assertGreaterEqual(len(tenants), 3)

            # Tenant isolation check
            us_projects = list_projects(tenant_id="TENANT-USLOG", db_path=db)
            self.assertEqual(len(us_projects), 1)
            self.assertEqual(us_projects[0].settings.standard_profile, "UL 508A")
            self.assertEqual(us_projects[0].settings.preferred_vendor, "ABB")
            self.assertEqual(us_projects[0].settings.plc_vendor, "Rockwell Automation")

            # Test all 6 PLC vendors + 7 electrical vendors
            prj = self._sample_project()
            for elec_v in ["ABB", "Fuji Electric", "Omron"]:
                prj.settings.preferred_vendor = elec_v  # type: ignore[assignment]
                d = compute_full_design(prj, custom_catalog=[])
                self.assertTrue(any(b.manufacturer == elec_v for b in d.bom), f"Missing BOM vendor {elec_v}")

            plc_expectations = {
                "Rockwell Automation": "Local:",
                "Omron": "NX_DI",
                "Beckhoff": "%IX",
            }
            for plc_v, prefix in plc_expectations.items():
                prj.settings.plc_vendor = plc_v  # type: ignore[assignment]
                d = compute_full_design(prj, custom_catalog=[])
                self.assertTrue(any(ch.plc_address.startswith(prefix) for ch in d.plc_channels if ch.io_type == "DI"))
                xml_str = export_plcopen_xml(d)
                root = ET.fromstring(xml_str)
                self.assertTrue(root.tag.endswith("project"))
                self.assertIn("PRG_MainControl", xml_str)

            # Create new custom manufacturer tenant
            new_t = save_tenant(TenantOrg(id="TENANT-DEMO99", name="Demo OEM", default_vendor="Fuji Electric", default_plc="Beckhoff"), db)
            self.assertEqual(new_t.id, "TENANT-DEMO99")
            self.assertEqual(len(list_tenants(db)), len(tenants) + 1)

    def test_v05_pagination_macros_transformer_and_full_zip(self) -> None:
        from backend.engine.macros import STANDARD_MACROS, instantiate_macro_units
        from backend.exporters import export_full_package_zip
        from backend.storage import list_audit_logs, record_audit_log

        prj = self._sample_project()
        # Apply 4 power macros -> triggers multi-page SH-02A / SH-02B + SH-04A / SH-04B pagination
        self.assertGreaterEqual(len(STANDARD_MACROS), 6)
        for mid in ("MACRO-CONV-VFD", "MACRO-HEATER-PID", "MACRO-PUMP-DOL", "MACRO-PNEU-IO"):
            units = instantiate_macro_units(mid, prj)
            self.assertTrue(len(units) >= 1)
            prj.loads.extend(units)

        design = compute_full_design(prj, custom_catalog=[])
        # Step-down transformer auto-sized because 220V servo exists on 380V mains
        self.assertIsNotNone(design.power_summary.transformer_part)
        self.assertGreater(design.power_summary.transformer_kva, 0)
        self.assertGreater(design.power_summary.panel_sccr_ka, 0)
        self.assertIn("AWG", design.power_summary.main_wire_awg)

        # Auto-pagination check
        codes = [sh.code for sh in design.schematic_sheets]
        self.assertIn("SH-02A", codes)
        self.assertIn("SH-02B", codes)
        self.assertIn("SH-04A", codes)
        self.assertIn("SH-04B", codes)

        # Full Engineering Delivery Package ZIP check
        zip_bytes = export_full_package_zip(design)
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            names = zf.namelist()
            self.assertTrue(any(n.endswith("_EPLAN.aml") for n in names))
            self.assertTrue(any(n.endswith("_PLCopen.xml") for n in names))
            self.assertTrue(any(n.endswith("_Engineering_Report.html") for n in names))
            self.assertTrue(any(n.endswith("_WireMarkers_Labels.csv") for n in names))
            self.assertTrue(any(n.endswith("_Schematic_MultiSheet.dxf") for n in names))

        # Audit log persistence
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "audit.db"
            init_db(db)
            record_audit_log("TENANT-KBAT", prj.id, "PACKAGE_EXPORTED", "Test zip export", db_path=db)
            logs = list_audit_logs(tenant_id="TENANT-KBAT", db_path=db)
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0]["action"], "PACKAGE_EXPORTED")

    def test_v06_auth_rbac_and_2d_drag_collision_wire_bom(self) -> None:
        from fastapi import HTTPException
        from backend.auth import create_access_token, decode_access_token, enforce_permission, hash_password, verify_password
        from backend.db import DatabaseSession
        from backend.storage import create_user, get_user_by_email, list_users

        # 1. Password hashing & JWT round-trip
        pw_hash = hash_password("s3cr3tPass!")
        self.assertTrue(verify_password("s3cr3tPass!", pw_hash))
        self.assertFalse(verify_password("wrong", pw_hash))

        token = create_access_token("USR-1", "eng@oem.com", "Alex", "designer", "TENANT-KBAT")
        claims = decode_access_token(token)
        self.assertEqual(claims["role"], "designer")

        # 2. RBAC enforcement matrix
        self.assertIn("designer", enforce_permission(claims, "edit_project"))
        with self.assertRaises(HTTPException) as ctx_rel:
            enforce_permission(claims, "release_revision")
        self.assertEqual(ctx_rel.exception.status_code, 403)

        viewer_claims = {"name": "View", "role": "viewer"}
        with self.assertRaises(HTTPException) as ctx_edit:
            enforce_permission(viewer_claims, "edit_project")
        self.assertEqual(ctx_edit.exception.status_code, 403)

        reviewer_claims = {"name": "Rev", "role": "reviewer"}
        self.assertIn("reviewer", enforce_permission(reviewer_claims, "release_revision"))

        # 3. DB adapter + seeded demo users
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "auth.db"
            init_db(db)
            self.assertGreaterEqual(len(list_users(db_path=db)), 4)
            self.assertIsNotNone(get_user_by_email("admin@panelcraft.ai", db_path=db))
            created = create_user("new@oem.com", hash_password("pass1234"), "New Eng", "reviewer", "TENANT-KBAT", db_path=db)
            self.assertEqual(created["role"], "reviewer")
            with DatabaseSession(db) as sess:
                rows = sess.fetchall("SELECT email FROM users WHERE role = ?", ("reviewer",))
                self.assertGreaterEqual(len(rows), 2)

        # 4. 2D Drag Override -> Collision Detection (LAY-001) & Duct-Routed Wire BOM
        prj = self._sample_project()
        base_design = compute_full_design(prj, custom_catalog=[])
        self.assertGreater(base_design.panel_layout.total_panel_wire_m, 10.0)
        self.assertTrue(any(b.unit == "M" and b.part_number.startswith("KIV-") for b in base_design.bom))
        self.assertEqual(len([i for i in base_design.panel_layout.layout_issues if i.code == "LAY-001"]), 0)

        # Force physical collision by dragging -F0 directly onto -Q0 coordinates
        q0 = next(c for c in base_design.panel_layout.components if c.tag == "-Q0")
        prj.layout_overrides = {"-F0": {"x_mm": q0.x_mm, "y_mm": q0.y_mm}}
        col_design = compute_full_design(prj, custom_catalog=[])
        self.assertTrue(any(i.code == "LAY-001" for i in col_design.panel_layout.layout_issues))
        self.assertTrue(any(r.rule_id == "LAY-001" and r.severity == "ERROR" for r in col_design.rule_checks))


if __name__ == "__main__":
    unittest.main()
