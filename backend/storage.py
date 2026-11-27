"""SQLite Multi-Tenant SSOT persistence, custom company catalog, LLM/Update config, and ECN diff engine."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from backend.auth import hash_password
from backend.db import DEFAULT_SQLITE_PATH, DatabaseSession
from backend.models import (
    CustomCatalogItem,
    CustomEplanMacro,
    LlmConfig,
    LoadUnit,
    Project,
    ProjectSettings,
    RevisionRecord,
    TenantOrg,
    UpdateConfig,
)


DB_PATH = DEFAULT_SQLITE_PATH


def _connect(db_path: Path = DB_PATH) -> DatabaseSession:
    return DatabaseSession(db_path)


def init_db(db_path: Path = DB_PATH) -> None:
    conn = _connect(db_path)
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tenants (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                industry TEXT NOT NULL,
                titleblock_company TEXT NOT NULL,
                default_standard TEXT NOT NULL,
                default_vendor TEXT NOT NULL,
                default_plc TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT 'TENANT-KBAT',
                name TEXT NOT NULL,
                client TEXT NOT NULL,
                data_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS revisions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                version_tag TEXT NOT NULL,
                status TEXT NOT NULL,
                author TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL,
                bom_total_krw INTEGER NOT NULL,
                total_io_points INTEGER NOT NULL,
                error_count INTEGER NOT NULL,
                snapshot_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_catalog (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT 'TENANT-KBAT',
                category TEXT NOT NULL,
                manufacturer TEXT NOT NULL,
                part_number TEXT NOT NULL,
                rated_value REAL NOT NULL,
                spec TEXT NOT NULL,
                unit_price_krw INTEGER NOT NULL,
                lead_time_days INTEGER NOT NULL,
                lifecycle_status TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_macros (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT 'TENANT-KBAT',
                macro_code TEXT NOT NULL,
                eplan_file TEXT NOT NULL,
                variant TEXT NOT NULL DEFAULT 'A',
                representation_type TEXT NOT NULL DEFAULT 'Multi-line',
                target_load_type TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                placeholder_vars_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                detail TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        # Graceful schema migration for existing v0.1-v0.3 SQLite databases
        if conn.dialect == "sqlite":
            prj_cols = {r["name"] for r in conn.execute("PRAGMA table_info(projects)").fetchall()}
            if "tenant_id" not in prj_cols:
                conn.execute("ALTER TABLE projects ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'TENANT-KBAT'")
            cat_cols = {r["name"] for r in conn.execute("PRAGMA table_info(custom_catalog)").fetchall()}
            if "tenant_id" not in cat_cols:
                conn.execute("ALTER TABLE custom_catalog ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'TENANT-KBAT'")

    # Seed default manufacturer tenants if empty
    if conn.execute("SELECT COUNT(*) AS cnt FROM tenants").fetchone()["cnt"] == 0:
        for tenant in _default_seed_tenants():
            save_tenant(tenant, db_path=db_path)

    # Seed default RBAC demo accounts if empty
    if conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()["cnt"] == 0:
        for email, pw, name, role, tid in [
            ("admin@panelcraft.ai", "admin1234", "Alex Kim (Admin)", "admin", "TENANT-KBAT"),
            ("reviewer@panelcraft.ai", "review1234", "Sarah Park (Lead Reviewer)", "reviewer", "TENANT-KBAT"),
            ("designer@panelcraft.ai", "design1234", "J. Lee (Control Designer)", "designer", "TENANT-KBAT"),
            ("viewer@panelcraft.ai", "view1234", "M. Choi (Client Viewer)", "viewer", "TENANT-KBAT"),
        ]:
            create_user(email, hash_password(pw), name, role, tid, db_path=db_path)

    # Seed realistic industrial projects if empty (or seed global Apex project if missing)
    existing_ids = {r["id"] for r in conn.execute("SELECT id FROM projects").fetchall()}
    if not existing_ids:
        for prj in _default_seed_projects():
            save_project(prj, db_path=db_path)
    elif "PRJ-USLOG03" not in existing_ids:
        for prj in _default_seed_projects():
            if prj.id == "PRJ-USLOG03":
                save_project(prj, db_path=db_path)
            elif prj.id == "PRJ-SEMI02":
                # Link existing PRJ-SEMI02 to TENANT-HSEMI
                conn.execute("UPDATE projects SET tenant_id = 'TENANT-HSEMI' WHERE id = 'PRJ-SEMI02'")
                conn.commit()
    conn.close()


def _default_seed_tenants() -> list[TenantOrg]:
    return [
        TenantOrg(
            id="TENANT-KBAT",
            name="K-Battery Automation",
            industry="EV Battery & FA Equipment OEM",
            titleblock_company="K-BATTERY AUTOMATION CO., LTD.",
            default_standard="IEC 60204-1",
            default_vendor="LS Electric",
            default_plc="Mitsubishi Electric",
        ),
        TenantOrg(
            id="TENANT-HSEMI",
            name="H-Semicon Systems",
            industry="Semiconductor Wet Process OEM",
            titleblock_company="H-SEMICON SYSTEMS INC.",
            default_standard="IEC 60204-1",
            default_vendor="Schneider Electric",
            default_plc="Siemens",
        ),
        TenantOrg(
            id="TENANT-USLOG",
            name="Apex Robotics & Logistics",
            industry="Global Smart Logistics & Robotics (UL 508A)",
            titleblock_company="APEX ROBOTICS & LOGISTICS LLC",
            default_standard="UL 508A",
            default_vendor="ABB",
            default_plc="Rockwell Automation",
        ),
    ]


def _default_seed_projects() -> list[Project]:
    return [
        Project(
            id="PRJ-BAT01",
            tenant_id="TENANT-KBAT",
            name="EV Battery Module Transfer Main Panel",
            client="K-Battery Tech (Plant 2)",
            description="4x 1.5kW VFD conveyors, 2x 750W lift servos, 12x pneumatic clamps, 18x sensors, PLd redundant E-Stop",
            settings=ProjectSettings(
                standard_profile="IEC 60204-1",
                power_system="3P_380V_60Hz",
                preferred_vendor="LS Electric",
                plc_vendor="Mitsubishi Electric",
                io_spare_ratio=0.20,
                ambient_temp_c=35.0,
                max_internal_temp_c=45.0,
            ),
            loads=[
                LoadUnit(id="l1", tag="CONV_MAIN", name="Main Conveyor VFD Motor", load_type="motor_inv", power_kw=1.5, quantity=4, voltage=380, phases=3, cable_length_m=22.0, has_emi_filter=True),
                LoadUnit(id="l2", tag="LIFT_SRV", name="Vertical Lift AC Servo Axis", load_type="servo", power_kw=0.75, quantity=2, voltage=220, phases=1, cable_length_m=15.0),
                LoadUnit(id="l3", tag="DUST_BLW", name="Dust Collector Blower Motor", load_type="motor_dol", power_kw=2.2, quantity=1, voltage=380, phases=3, cable_length_m=18.0),
                LoadUnit(id="l4", tag="CLAMP_SOL", name="Stopper & Clamp Solenoids", load_type="solenoid_group", power_kw=0.0, quantity=12, voltage=24, phases=0, cable_length_m=12.0, has_surge_suppressor=True),
                LoadUnit(id="l5", tag="DET_SEN", name="Pallet Photo/Proximity Sensors", load_type="sensor_group", power_kw=0.0, quantity=18, voltage=24, phases=0, cable_length_m=14.0),
                LoadUnit(id="l6", tag="SAFETY_01", name="Line E-Stop & Safety Door Circuit", load_type="safety_circuit", power_kw=0.0, quantity=3, voltage=24, phases=0, safety_level="PLd"),
            ],
        ),
        Project(
            id="PRJ-SEMI02",
            tenant_id="TENANT-HSEMI",
            name="Wafer Clean & N2 Dry Chamber Panel",
            client="H-Semicon Fab 4",
            description="2x chemical pumps, 2x 4.5kW dry heaters, 3x wafer transfer servos, 16x valves, PLe EMO safety",
            settings=ProjectSettings(
                standard_profile="IEC 60204-1",
                power_system="3P_380V_60Hz",
                preferred_vendor="Schneider Electric",
                plc_vendor="Siemens",
                io_spare_ratio=0.25,
                ambient_temp_c=30.0,
                max_internal_temp_c=42.0,
            ),
            loads=[
                LoadUnit(id="s1", tag="PUMP_CIRC", name="Chemical Circulation VFD Pump", load_type="motor_inv", power_kw=2.2, quantity=2, voltage=380, phases=3, cable_length_m=16.0, has_emi_filter=True),
                LoadUnit(id="s2", tag="DRY_HTR", name="Chamber N2 Dry Heater Zone", load_type="heater", power_kw=4.5, quantity=2, voltage=380, phases=3, cable_length_m=12.0, power_factor=1.0, efficiency=1.0),
                LoadUnit(id="s3", tag="ROBOT_SRV", name="Wafer Handling Servo Axis", load_type="servo", power_kw=0.4, quantity=3, voltage=220, phases=1, cable_length_m=10.0),
                LoadUnit(id="s4", tag="VALVE_GRP", name="Diaphragm Valve Manifold", load_type="solenoid_group", quantity=16, voltage=24, phases=0, has_surge_suppressor=False),
                LoadUnit(id="s5", tag="PROC_SEN", name="Level / Flow / Door Sensors", load_type="sensor_group", quantity=20, voltage=24, phases=0),
                LoadUnit(id="s6", tag="SAFETY_01", name="Redundant EMO Safety Circuit", load_type="safety_circuit", quantity=2, voltage=24, phases=0, safety_level="PLe"),
            ],
        ),
        Project(
            id="PRJ-USLOG03",
            tenant_id="TENANT-USLOG",
            name="North America Palletizer Cell (UL 508A)",
            client="Midwest Fulfillment Hub #7",
            description="3P 480V UL 508A control cabinet with ABB drives, Rockwell ControlLogix 5580, 3x gantry servos, PLe safety",
            settings=ProjectSettings(
                standard_profile="UL 508A",
                power_system="3P_480V_60Hz",
                preferred_vendor="ABB",
                plc_vendor="Rockwell Automation",
                io_spare_ratio=0.20,
                ambient_temp_c=35.0,
                max_internal_temp_c=45.0,
            ),
            loads=[
                LoadUnit(id="a1", tag="INFEED_VFD", name="High-Speed Infeed Conveyor", load_type="motor_inv", power_kw=2.2, quantity=3, voltage=480, phases=3, cable_length_m=24.0, has_emi_filter=True),
                LoadUnit(id="a2", tag="GANTRY_SRV", name="3-Axis Palletizer Servo", load_type="servo", power_kw=1.5, quantity=3, voltage=220, phases=3, cable_length_m=18.0),
                LoadUnit(id="a3", tag="VAC_BLW", name="Vacuum Gripper Blower", load_type="motor_dol", power_kw=3.7, quantity=1, voltage=480, phases=3, cable_length_m=15.0),
                LoadUnit(id="a4", tag="GRIP_SOL", name="Gripper & Diverter Valves", load_type="solenoid_group", quantity=10, voltage=24, phases=0, has_surge_suppressor=True),
                LoadUnit(id="a5", tag="CELL_SEN", name="Photoeye & Area Scanner I/O", load_type="sensor_group", quantity=16, voltage=24, phases=0),
                LoadUnit(id="a6", tag="SAFETY_01", name="UL 508A Safety Curtain & E-Stop", load_type="safety_circuit", quantity=3, voltage=24, phases=0, safety_level="PLe"),
            ],
        ),
    ]


# --- Multi-Tenant Organizations ---

def list_tenants(db_path: Path = DB_PATH) -> list[TenantOrg]:
    conn = _connect(db_path)
    rows = conn.execute("SELECT * FROM tenants ORDER BY created_at ASC").fetchall()
    conn.close()
    return [TenantOrg(**dict(r)) for r in rows]


def get_tenant(tenant_id: str, db_path: Path = DB_PATH) -> Optional[TenantOrg]:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
    except sqlite3.OperationalError:
        row = None
    finally:
        conn.close()
    return TenantOrg(**dict(row)) if row else None


def save_tenant(tenant: TenantOrg, db_path: Path = DB_PATH) -> TenantOrg:
    if not tenant.titleblock_company:
        tenant.titleblock_company = tenant.name.upper()
    conn = _connect(db_path)
    with conn:
        conn.execute(
            """
            INSERT INTO tenants (
                id, name, industry, titleblock_company, default_standard,
                default_vendor, default_plc, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                industry = excluded.industry,
                titleblock_company = excluded.titleblock_company,
                default_standard = excluded.default_standard,
                default_vendor = excluded.default_vendor,
                default_plc = excluded.default_plc
            """,
            (
                tenant.id,
                tenant.name,
                tenant.industry,
                tenant.titleblock_company,
                tenant.default_standard,
                tenant.default_vendor,
                tenant.default_plc,
                tenant.created_at,
            ),
        )
    conn.close()
    return tenant


# --- Projects (Tenant-Scoped) ---

def list_projects(tenant_id: Optional[str] = None, db_path: Path = DB_PATH) -> list[Project]:
    conn = _connect(db_path)
    if tenant_id:
        rows = conn.execute(
            "SELECT data_json, tenant_id FROM projects WHERE tenant_id = ? ORDER BY updated_at DESC",
            (tenant_id,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT data_json, tenant_id FROM projects ORDER BY updated_at DESC").fetchall()
    conn.close()
    items: list[Project] = []
    for r in rows:
        p = Project.model_validate_json(r["data_json"])
        p.tenant_id = r["tenant_id"]
        items.append(p)
    return items


def get_project(project_id: str, db_path: Path = DB_PATH) -> Optional[Project]:
    conn = _connect(db_path)
    row = conn.execute("SELECT data_json, tenant_id FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    if not row:
        return None
    p = Project.model_validate_json(row["data_json"])
    p.tenant_id = row["tenant_id"]
    return p


def save_project(project: Project, db_path: Path = DB_PATH) -> Project:
    project.updated_at = datetime.now().isoformat(timespec="seconds")
    conn = _connect(db_path)
    with conn:
        conn.execute(
            """
            INSERT INTO projects (id, tenant_id, name, client, data_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                tenant_id = excluded.tenant_id,
                name = excluded.name,
                client = excluded.client,
                data_json = excluded.data_json,
                updated_at = excluded.updated_at
            """,
            (project.id, project.tenant_id, project.name, project.client, project.model_dump_json(), project.updated_at),
        )
    conn.close()
    return project


def delete_project(project_id: str, db_path: Path = DB_PATH) -> bool:
    conn = _connect(db_path)
    with conn:
        cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.execute("DELETE FROM revisions WHERE project_id = ?", (project_id,))
    conn.close()
    return cur.rowcount > 0


# --- Custom Company Component Catalog (Tenant-Scoped) ---

def list_custom_catalog(tenant_id: Optional[str] = None, db_path: Path = DB_PATH) -> list[CustomCatalogItem]:
    conn = _connect(db_path)
    if tenant_id:
        rows = conn.execute(
            "SELECT * FROM custom_catalog WHERE tenant_id = ? ORDER BY category, rated_value",
            (tenant_id,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM custom_catalog ORDER BY category, rated_value").fetchall()
    conn.close()
    return [CustomCatalogItem(**dict(r)) for r in rows]


def upsert_custom_catalog_items(
    items: list[CustomCatalogItem],
    tenant_id: str = "TENANT-KBAT",
    db_path: Path = DB_PATH,
) -> list[CustomCatalogItem]:
    conn = _connect(db_path)
    with conn:
        for it in items:
            it.tenant_id = tenant_id
            scoped_id = it.id if it.id.startswith(tenant_id) else f"{tenant_id}-{it.id}"
            conn.execute(
                """
                INSERT INTO custom_catalog (
                    id, tenant_id, category, manufacturer, part_number, rated_value,
                    spec, unit_price_krw, lead_time_days, lifecycle_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    category = excluded.category,
                    manufacturer = excluded.manufacturer,
                    part_number = excluded.part_number,
                    rated_value = excluded.rated_value,
                    spec = excluded.spec,
                    unit_price_krw = excluded.unit_price_krw,
                    lead_time_days = excluded.lead_time_days,
                    lifecycle_status = excluded.lifecycle_status
                """,
                (
                    scoped_id,
                    tenant_id,
                    it.category,
                    it.manufacturer,
                    it.part_number,
                    it.rated_value,
                    it.spec,
                    it.unit_price_krw,
                    it.lead_time_days,
                    it.lifecycle_status,
                ),
            )
    conn.close()
    return list_custom_catalog(tenant_id=tenant_id, db_path=db_path)


def delete_custom_catalog_item(item_id: str, db_path: Path = DB_PATH) -> bool:
    conn = _connect(db_path)
    with conn:
        cur = conn.execute("DELETE FROM custom_catalog WHERE id = ?", (item_id,))
    conn.close()
    return cur.rowcount > 0


def clear_custom_catalog(tenant_id: Optional[str] = None, db_path: Path = DB_PATH) -> None:
    conn = _connect(db_path)
    with conn:
        if tenant_id:
            conn.execute("DELETE FROM custom_catalog WHERE tenant_id = ?", (tenant_id,))
        else:
            conn.execute("DELETE FROM custom_catalog")
    conn.close()


# --- LLM & Update Config ---

def get_llm_config(db_path: Path = DB_PATH) -> LlmConfig:
    conn = _connect(db_path)
    row = conn.execute("SELECT value_json FROM app_settings WHERE key = 'llm_config'").fetchone()
    conn.close()
    if row:
        return LlmConfig.model_validate_json(row["value_json"])
    return LlmConfig(
        provider=os.getenv("PANELCRAFT_LLM_PROVIDER", "builtin"),  # type: ignore[arg-type]
        base_url=os.getenv("PANELCRAFT_LLM_BASE_URL", "https://api.openai.com/v1"),
        model=os.getenv("PANELCRAFT_LLM_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("PANELCRAFT_LLM_API_KEY", ""),
    )


def save_llm_config(cfg: LlmConfig, db_path: Path = DB_PATH) -> LlmConfig:
    conn = _connect(db_path)
    with conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value_json)
            VALUES ('llm_config', ?)
            ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json
            """,
            (cfg.model_dump_json(),),
        )
    conn.close()
    return cfg


def get_update_config(db_path: Path = DB_PATH) -> UpdateConfig:
    conn = _connect(db_path)
    row = conn.execute("SELECT value_json FROM app_settings WHERE key = 'update_config'").fetchone()
    conn.close()
    if row:
        return UpdateConfig.model_validate_json(row["value_json"])
    return UpdateConfig(
        github_repo=os.getenv("PANELCRAFT_GITHUB_REPO", "knoxxr/panelcraft-ai"),
    )


def save_update_config(cfg: UpdateConfig, db_path: Path = DB_PATH) -> UpdateConfig:
    conn = _connect(db_path)
    with conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value_json)
            VALUES ('update_config', ?)
            ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json
            """,
            (cfg.model_dump_json(),),
        )
    conn.close()
    return cfg


# --- Revisions, Status Promotion & ECN Diff ---

def get_revision(revision_id: str, db_path: Path = DB_PATH) -> Optional[RevisionRecord]:
    conn = _connect(db_path)
    r = conn.execute("SELECT * FROM revisions WHERE id = ?", (revision_id,)).fetchone()
    conn.close()
    if not r:
        return None
    return RevisionRecord(
        id=r["id"],
        project_id=r["project_id"],
        version_tag=r["version_tag"],
        status=r["status"],
        author=r["author"],
        summary=r["summary"],
        created_at=r["created_at"],
        bom_total_krw=r["bom_total_krw"],
        total_io_points=r["total_io_points"],
        error_count=r["error_count"],
        snapshot_json=json.loads(r["snapshot_json"]),
    )


def update_revision_status(revision_id: str, status: str, db_path: Path = DB_PATH) -> Optional[RevisionRecord]:
    conn = _connect(db_path)
    with conn:
        conn.execute("UPDATE revisions SET status = ? WHERE id = ?", (status, revision_id))
    conn.close()
    return get_revision(revision_id, db_path)


def create_revision(
    project_id: str,
    version_tag: str,
    status: str,
    author: str,
    summary: str,
    bom_total_krw: int,
    total_io_points: int,
    error_count: int,
    snapshot_json: dict[str, Any],
    db_path: Path = DB_PATH,
) -> RevisionRecord:
    rev = RevisionRecord(
        id=f"REV-{uuid.uuid4().hex[:8].upper()}",
        project_id=project_id,
        version_tag=version_tag,
        status=status,  # type: ignore[arg-type]
        author=author,
        summary=summary,
        created_at=datetime.now().isoformat(timespec="seconds"),
        bom_total_krw=bom_total_krw,
        total_io_points=total_io_points,
        error_count=error_count,
        snapshot_json=snapshot_json,
    )
    conn = _connect(db_path)
    with conn:
        conn.execute(
            """
            INSERT INTO revisions (
                id, project_id, version_tag, status, author, summary,
                created_at, bom_total_krw, total_io_points, error_count, snapshot_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rev.id,
                rev.project_id,
                rev.version_tag,
                rev.status,
                rev.author,
                rev.summary,
                rev.created_at,
                rev.bom_total_krw,
                rev.total_io_points,
                rev.error_count,
                json.dumps(rev.snapshot_json, ensure_ascii=False),
            ),
        )
    conn.close()
    return rev


def list_revisions(project_id: str, db_path: Path = DB_PATH) -> list[RevisionRecord]:
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT * FROM revisions WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,),
    ).fetchall()
    conn.close()
    return [
        RevisionRecord(
            id=r["id"],
            project_id=r["project_id"],
            version_tag=r["version_tag"],
            status=r["status"],
            author=r["author"],
            summary=r["summary"],
            created_at=r["created_at"],
            bom_total_krw=r["bom_total_krw"],
            total_io_points=r["total_io_points"],
            error_count=r["error_count"],
            snapshot_json=json.loads(r["snapshot_json"]),
        )
        for r in rows
    ]


def diff_revisions(base_rev: RevisionRecord, target_rev: RevisionRecord) -> dict[str, Any]:
    base_loads = {l["tag"]: l for l in base_rev.snapshot_json.get("loads", [])}
    targ_loads = {l["tag"]: l for l in target_rev.snapshot_json.get("loads", [])}

    load_changes: list[dict[str, Any]] = []
    for tag, item in targ_loads.items():
        if tag not in base_loads:
            load_changes.append({"type": "ADDED", "tag": tag, "detail": f"{item['name']} ({item['power_kw']}kW × {item['quantity']})"})
        else:
            b = base_loads[tag]
            diffs = []
            if b.get("power_kw") != item.get("power_kw"):
                diffs.append(f"Power {b.get('power_kw')}kW → {item.get('power_kw')}kW")
            if b.get("quantity") != item.get("quantity"):
                diffs.append(f"Qty {b.get('quantity')} → {item.get('quantity')}")
            if b.get("load_type") != item.get("load_type"):
                diffs.append(f"Type {b.get('load_type')} → {item.get('load_type')}")
            if diffs:
                load_changes.append({"type": "MODIFIED", "tag": tag, "detail": ", ".join(diffs)})
    for tag, item in base_loads.items():
        if tag not in targ_loads:
            load_changes.append({"type": "REMOVED", "tag": tag, "detail": f"{item['name']} removed"})

    base_bom = {b["part_number"]: b for b in base_rev.snapshot_json.get("bom", [])}
    targ_bom = {b["part_number"]: b for b in target_rev.snapshot_json.get("bom", [])}
    bom_changes: list[dict[str, Any]] = []
    for pn, b in targ_bom.items():
        if pn not in base_bom:
            bom_changes.append({"type": "ADDED", "part_number": pn, "spec": b["spec"], "qty_delta": f"+{b['quantity']}"})
        elif base_bom[pn]["quantity"] != b["quantity"]:
            delta = b["quantity"] - base_bom[pn]["quantity"]
            sign = "+" if delta > 0 else ""
            bom_changes.append({"type": "MODIFIED", "part_number": pn, "spec": b["spec"], "qty_delta": f"{sign}{delta}"})
    for pn, b in base_bom.items():
        if pn not in targ_bom:
            bom_changes.append({"type": "REMOVED", "part_number": pn, "spec": b["spec"], "qty_delta": f"-{b['quantity']}"})

    return {
        "base_version": base_rev.version_tag,
        "target_version": target_rev.version_tag,
        "bom_cost_delta_krw": target_rev.bom_total_krw - base_rev.bom_total_krw,
        "io_points_delta": target_rev.total_io_points - base_rev.total_io_points,
        "load_changes": load_changes,
        "bom_changes": bom_changes,
    }


def record_audit_log(
    tenant_id: str,
    project_id: str,
    action: str,
    detail: str,
    actor: str = "Controls Engineer",
    db_path: Path = DB_PATH,
) -> None:
    conn = _connect(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO audit_logs (id, tenant_id, project_id, action, actor, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"AUD-{uuid.uuid4().hex[:8].upper()}",
                    tenant_id,
                    project_id,
                    action,
                    actor,
                    detail,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def list_audit_logs(tenant_id: Optional[str] = None, limit: int = 30, db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    conn = _connect(db_path)
    try:
        if tenant_id:
            rows = conn.execute(
                "SELECT * FROM audit_logs WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?",
                (tenant_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    return [dict(r) for r in rows]


# --- SaaS Users & RBAC Accounts ---

def get_user_by_email(email: str, db_path: Path = DB_PATH) -> Optional[dict[str, Any]]:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),)).fetchone()
    except sqlite3.OperationalError:
        row = None
    finally:
        conn.close()
    return dict(row) if row else None


def create_user(
    email: str,
    password_hash: str,
    full_name: str,
    role: str,
    tenant_id: str,
    db_path: Path = DB_PATH,
) -> dict[str, Any]:
    uid = f"USR-{uuid.uuid4().hex[:8].upper()}"
    created_at = datetime.now().isoformat(timespec="seconds")
    conn = _connect(db_path)
    with conn:
        conn.execute(
            "INSERT INTO users (id, email, password_hash, full_name, role, tenant_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uid, email.strip().lower(), password_hash, full_name.strip(), role, tenant_id, created_at),
        )
    conn.close()
    return {
        "id": uid,
        "email": email.strip().lower(),
        "full_name": full_name.strip(),
        "role": role,
        "tenant_id": tenant_id,
        "created_at": created_at,
    }


def list_users(tenant_id: Optional[str] = None, db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    conn = _connect(db_path)
    try:
        if tenant_id:
            rows = conn.execute(
                "SELECT id, email, full_name, role, tenant_id, created_at FROM users WHERE tenant_id = ? ORDER BY created_at ASC",
                (tenant_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, email, full_name, role, tenant_id, created_at FROM users ORDER BY created_at ASC"
            ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    return [dict(r) for r in rows]


# --- Company EPLAN .ema Macro Library ---

def list_custom_macros(tenant_id: Optional[str] = None, db_path: Path = DB_PATH) -> list[CustomEplanMacro]:
    conn = _connect(db_path)
    try:
        if tenant_id:
            rows = conn.execute(
                "SELECT * FROM custom_macros WHERE tenant_id = ? ORDER BY updated_at DESC",
                (tenant_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM custom_macros ORDER BY updated_at DESC").fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    result: list[CustomEplanMacro] = []
    for r in rows:
        try:
            pvars = json.loads(r["placeholder_vars_json"] or "{}")
        except Exception:
            pvars = {}
        result.append(
            CustomEplanMacro(
                id=r["id"],
                tenant_id=r["tenant_id"],
                macro_code=r["macro_code"],
                eplan_file=r["eplan_file"],
                variant=r["variant"],
                representation_type=r["representation_type"],
                target_load_type=r["target_load_type"],
                name=r["name"],
                description=r["description"],
                placeholder_vars=pvars,
                updated_at=r["updated_at"],
            )
        )
    return result


def upsert_custom_macro(item: CustomEplanMacro, db_path: Path = DB_PATH) -> CustomEplanMacro:
    item.updated_at = datetime.now().isoformat(timespec="seconds")
    conn = _connect(db_path)
    with conn:
        conn.execute(
            """
            INSERT INTO custom_macros (
                id, tenant_id, macro_code, eplan_file, variant, representation_type,
                target_load_type, name, description, placeholder_vars_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                tenant_id = excluded.tenant_id,
                macro_code = excluded.macro_code,
                eplan_file = excluded.eplan_file,
                variant = excluded.variant,
                representation_type = excluded.representation_type,
                target_load_type = excluded.target_load_type,
                name = excluded.name,
                description = excluded.description,
                placeholder_vars_json = excluded.placeholder_vars_json,
                updated_at = excluded.updated_at
            """,
            (
                item.id,
                item.tenant_id,
                item.macro_code,
                item.eplan_file,
                item.variant,
                item.representation_type,
                item.target_load_type,
                item.name,
                item.description,
                json.dumps(item.placeholder_vars, ensure_ascii=False),
                item.updated_at,
            ),
        )
    conn.close()
    return item


def delete_custom_macro(macro_id: str, db_path: Path = DB_PATH) -> bool:
    conn = _connect(db_path)
    with conn:
        cur = conn.execute("DELETE FROM custom_macros WHERE id = ?", (macro_id,))
    conn.close()
    return cur.rowcount > 0



