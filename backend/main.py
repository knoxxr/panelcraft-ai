"""FastAPI entry point for PanelCraft AI v0.6 Multi-Tenant SaaS Platform.

Features:
- Multi-Tenant Organizations + PBKDF2/JWT Authentication & 4-Role RBAC (admin/reviewer/designer/viewer)
- Unified SQLite (embedded) & PostgreSQL (Cloud SaaS) database adapter
- Interactive 2D Mounting Plate Drag-and-Drop persistence + live collision check + duct-routed wire BOM
- Deterministic electrical sizing, 7 electrical vendors, 6 PLC vendors, EPLAN AML, PLCopen XML, Full ZIP
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.auth import (
    ROLE_PERMISSIONS,
    create_access_token,
    enforce_permission,
    get_optional_user,
    hash_password,
    verify_password,
)
from backend.db import get_db_info
from backend.mcp_server import get_mcp_server_metadata, handle_mcp_jsonrpc
from backend.engine.calculator import compute_electrical_and_bom
from backend.engine.copilot import generate_interlock_code, parse_nl_spec
from backend.engine.io_plc import build_plc_and_io
from backend.engine.layout import build_panel_layout
from backend.engine.llm_gateway import test_llm_connection
from backend.engine.macros import STANDARD_MACROS, generate_eplan_ema_xml, instantiate_macro_units
from backend.engine.rules import run_design_verification
from backend.engine.schematic import build_terminals, synthesize_schematics
from backend.exporters import (
    export_bom_csv,
    export_engineering_dossier_html,
    export_eplan_aml,
    export_eplan_parts_csv,
    export_fat_checklist_md,
    export_full_package_zip,
    export_io_csv,
    export_plcopen_xml,
    export_project_dxf,
    export_project_layout_dxf,
    export_terminals_csv,
    export_wire_labels_csv,
)
from backend.importers import (
    export_catalog_template_csv,
    export_load_template_csv,
    extract_pdf_text,
    parse_catalog_file,
    parse_loads_file,
)
from backend.models import (
    AppVersionInfo,
    AuditLogEntry,
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthTokenResponse,
    BomItem,
    CircuitMacroTemplate,
    ComputedDesign,
    CopilotParseRequest,
    CopilotParseResponse,
    CustomCatalogItem,
    CustomEplanMacro,
    CustomEplanMacroRequest,
    ImportCatalogResponse,
    ImportLoadsResponse,
    InterlockRequest,
    InterlockResponse,
    LayoutPositionsUpdateRequest,
    LlmConfig,
    LoadUnit,
    Project,
    ProjectSettings,
    RevisionRecord,
    RuleCheckItem,
    TenantOrg,
    UpdateCheckResponse,
    UpdateConfig,
    UserPublic,
)
from backend.storage import (
    clear_custom_catalog,
    create_revision,
    create_user,
    delete_custom_catalog_item,
    delete_custom_macro,
    delete_project,
    diff_revisions,
    get_llm_config,
    get_project,
    get_revision,
    get_tenant,
    get_update_config,
    get_user_by_email,
    init_db,
    list_audit_logs,
    list_custom_catalog,
    list_custom_macros,
    list_projects,
    list_revisions,
    list_tenants,
    list_users,
    record_audit_log,
    save_llm_config,
    save_project,
    save_tenant,
    save_update_config,
    update_revision_status,
    upsert_custom_catalog_items,
    upsert_custom_macro,
)
from backend.updater import build_github_links, check_github_updates
from backend.version import get_app_version, get_runtime_info, read_changelog_entries

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(
    title="PanelCraft AI — Multi-Tenant Industrial Control Panel SaaS API",
    version=get_app_version(),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


def _to_user_public(row: dict) -> UserPublic:
    role = row["role"]
    return UserPublic(
        id=row["id"],
        email=row["email"],
        full_name=row["full_name"],
        role=role,
        tenant_id=row["tenant_id"],
        permissions=sorted(ROLE_PERMISSIONS.get(role, set())),
        created_at=row["created_at"],
    )


def compute_full_design(
    project: Project,
    custom_catalog: list[CustomCatalogItem] | None = None,
    custom_macros: list[CustomEplanMacro] | None = None,
) -> ComputedDesign:
    """Execute full SSOT pipeline: PLC/I/O -> Sizing/IEC60909/60890/BOM -> 2D Layout & Wire Routing -> Rules -> Schematics."""
    tenant = get_tenant(project.tenant_id)
    tenant_name = tenant.titleblock_company if tenant else "PanelCraft Organization"
    catalog = custom_catalog if custom_catalog is not None else list_custom_catalog(tenant_id=project.tenant_id)
    macros = custom_macros if custom_macros is not None else list_custom_macros(tenant_id=project.tenant_id)
    plc_modules, plc_channels, st_code = build_plc_and_io(project)
    power_summary, load_calcs, bom, bom_total = compute_electrical_and_bom(project, plc_modules, catalog, macros)
    terminals = build_terminals(load_calcs, plc_channels)
    panel_layout = build_panel_layout(project, power_summary, load_calcs, plc_modules)

    # Inject duct-routed Panel Internal Wiring directly into BOM (unit = M)
    next_line = len(bom) + 1
    for w in panel_layout.wire_length_summary:
        wire_std = f"UL 1015 {w.wire_awg} ({w.wire_sq} SQ)" if project.settings.standard_profile == "UL 508A" else f"HIV {w.wire_sq} SQ ({w.wire_awg})"
        bom.append(
            BomItem(
                line_no=next_line,
                category="판넬 내부 배선 (Panel Wire)",
                iec_tags=["-W_INT"],
                manufacturer="LS Cable / KIV",
                part_number=f"KIV-{w.wire_sq}SQ",
                spec=f"{wire_std} — {w.purpose} ({w.route_count} routes, duct-routed)",
                quantity=int(w.total_length_m),
                unit="M",
                unit_price_krw=w.unit_price_per_m_krw,
                total_price_krw=w.total_price_krw,
                lead_time_days=2,
                lifecycle_status="Auto-Routed",
            )
        )
        bom_total += w.total_price_krw
        next_line += 1

    rule_checks = run_design_verification(project, power_summary, load_calcs, plc_modules, plc_channels)
    for issue in panel_layout.layout_issues:
        rule_checks.insert(
            0,
            RuleCheckItem(
                rule_id=issue.code,
                severity=issue.severity,
                category="DRC",
                standard_ref="IEC 61439-1 / Mounting Plate 2D",
                target_tag=", ".join(issue.targets),
                title="2D Mounting Plate Collision / Clearance Alert",
                detail=issue.message,
                recommendation="Adjust component coordinates in '05 2D Panel Layout' or click Auto-Reset Layout.",
            ),
        )

    schematics = synthesize_schematics(project, power_summary, load_calcs, plc_modules, plc_channels, tenant_name=tenant_name)
    return ComputedDesign(
        project=project,
        tenant_name=tenant_name,
        power_summary=power_summary,
        load_calculations=load_calcs,
        bom=bom,
        bom_total_krw=bom_total,
        plc_modules=plc_modules,
        plc_channels=plc_channels,
        plc_st_code=st_code,
        terminals=terminals,
        rule_checks=rule_checks,
        schematic_sheets=schematics,
        panel_layout=panel_layout,
    )


# --- Auth & RBAC Endpoints ---

@app.post("/api/auth/login", response_model=AuthTokenResponse)
def api_auth_login(body: AuthLoginRequest) -> AuthTokenResponse:
    row = get_user_by_email(body.email)
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = create_access_token(row["id"], row["email"], row["full_name"], row["role"], row["tenant_id"])
    return AuthTokenResponse(access_token=token, user=_to_user_public(row))


@app.post("/api/auth/register", response_model=AuthTokenResponse)
def api_auth_register(body: AuthRegisterRequest) -> AuthTokenResponse:
    if get_user_by_email(body.email):
        raise HTTPException(status_code=409, detail="Email is already registered.")
    row = create_user(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
        tenant_id=body.tenant_id,
    )
    token = create_access_token(row["id"], row["email"], row["full_name"], row["role"], row["tenant_id"])
    return AuthTokenResponse(access_token=token, user=_to_user_public(row))


@app.get("/api/auth/me")
def api_auth_me(user: Optional[dict] = Depends(get_optional_user)) -> dict:
    db_info = get_db_info()
    if not user:
        return {"authenticated": False, "user": None, "db": db_info}
    row = get_user_by_email(user.get("email", ""))
    return {
        "authenticated": bool(row),
        "user": _to_user_public(row).model_dump() if row else None,
        "db": db_info,
    }


@app.get("/api/auth/users", response_model=list[UserPublic])
def api_list_users(tenant_id: Optional[str] = None) -> list[UserPublic]:
    return [_to_user_public(r) for r in list_users(tenant_id=tenant_id)]


# --- App Version, Auto-Update & GitHub Community Endpoints ---

@app.get("/api/health")
def health() -> dict[str, str]:
    db_info = get_db_info()
    return {
        "status": "ok",
        "service": "panelcraft-ai",
        "version": get_app_version(),
        "db_backend": db_info["backend"],
        "mcp_endpoint": "/mcp",
    }


# --- Model Context Protocol (MCP) Streamable HTTP Endpoint ---

@app.get("/mcp")
def api_mcp_info(request: Request) -> dict:
    base_url = str(request.base_url).rstrip("/")
    return get_mcp_server_metadata(base_url=base_url)


@app.post("/mcp")
async def api_mcp_rpc(request: Request, user: Optional[dict] = Depends(get_optional_user)) -> Response:
    try:
        payload = await request.json()
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content={"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {exc}"}},
        )

    if isinstance(payload, list):
        responses = [r for item in payload if (r := handle_mcp_jsonrpc(item, user=user)) is not None]
        if not responses:
            return Response(status_code=202)
        return JSONResponse(content=responses, headers={"MCP-Protocol-Version": "2025-03-26"})

    resp = handle_mcp_jsonrpc(payload, user=user)
    if resp is None:
        return Response(status_code=202)
    return JSONResponse(content=resp, headers={"MCP-Protocol-Version": "2025-03-26"})


@app.delete("/mcp")
def api_mcp_close_session() -> Response:
    return Response(status_code=204)


@app.get("/api/version", response_model=AppVersionInfo)
def api_version_info() -> AppVersionInfo:
    rt = get_runtime_info()
    ucfg = get_update_config()
    return AppVersionInfo(
        app_version=rt["app_version"],
        os=rt["os"],
        os_release=rt["os_release"],
        arch=rt["arch"],
        python_version=rt["python_version"],
        update_config=ucfg,
        github_links=build_github_links(ucfg.github_repo, rt["app_version"]),
        changelog=read_changelog_entries(),
    )


@app.get("/api/update/config", response_model=UpdateConfig)
def api_get_update_config() -> UpdateConfig:
    return get_update_config()


@app.post("/api/update/config", response_model=UpdateConfig)
def api_save_update_config(cfg: UpdateConfig, user: Optional[dict] = Depends(get_optional_user)) -> UpdateConfig:
    enforce_permission(user, "manage_settings")
    return save_update_config(cfg)


@app.post("/api/update/check", response_model=UpdateCheckResponse)
def api_check_updates(cfg: Optional[UpdateConfig] = None) -> UpdateCheckResponse:
    active_cfg = cfg or get_update_config()
    return check_github_updates(active_cfg)


# --- Multi-Tenant Manufacturer Organizations ---

@app.get("/api/tenants", response_model=list[TenantOrg])
def api_list_tenants() -> list[TenantOrg]:
    return list_tenants()


@app.post("/api/tenants", response_model=TenantOrg)
def api_create_tenant(tenant: TenantOrg, user: Optional[dict] = Depends(get_optional_user)) -> TenantOrg:
    actor = enforce_permission(user, "manage_org")
    saved = save_tenant(tenant)
    if not list_projects(tenant_id=saved.id):
        starter = Project(
            id=f"PRJ-{saved.id[-4:].upper()}01",
            tenant_id=saved.id,
            name=f"{saved.name} Starter Control Panel",
            client=saved.name,
            settings=ProjectSettings(
                standard_profile=saved.default_standard,
                power_system="3P_480V_60Hz" if saved.default_standard == "UL 508A" else "3P_380V_60Hz",
                preferred_vendor=saved.default_vendor,
                plc_vendor=saved.default_plc,
            ),
            loads=[
                LoadUnit(id="st1", tag="CONV_01", name="Main Transfer Conveyor VFD", load_type="motor_inv", power_kw=1.5, quantity=2, voltage=480 if saved.default_standard == "UL 508A" else 380, phases=3),
                LoadUnit(id="st2", tag="SRV_01", name="Handling Servo Axis", load_type="servo", power_kw=0.75, quantity=2, voltage=220, phases=1),
                LoadUnit(id="st3", tag="SOL_01", name="Pneumatic Actuator Valves", load_type="solenoid_group", quantity=8, voltage=24, phases=0),
                LoadUnit(id="st4", tag="SAFETY_01", name="Line E-Stop Safety Circuit", load_type="safety_circuit", quantity=2, voltage=24, phases=0, safety_level="PLd"),
            ],
        )
        save_project(starter)
    record_audit_log(saved.id, "ORG", "TENANT_CREATED", f"Created organization '{saved.name}'", actor=actor)
    return saved


# --- Standard & Company EPLAN .ema Circuit Macro Library & Audit Log ---

@app.get("/api/macros", response_model=list[CircuitMacroTemplate])
def api_list_macros() -> list[CircuitMacroTemplate]:
    return STANDARD_MACROS


@app.get("/api/macros/custom", response_model=list[CustomEplanMacro])
def api_list_custom_macros(tenant_id: Optional[str] = None) -> list[CustomEplanMacro]:
    return list_custom_macros(tenant_id=tenant_id)


@app.post("/api/macros/custom", response_model=CustomEplanMacro)
def api_upsert_custom_macro(
    body: CustomEplanMacroRequest,
    user: Optional[dict] = Depends(get_optional_user),
) -> CustomEplanMacro:
    import uuid

    actor = enforce_permission(user, "manage_catalog")
    mid = (body.id or "").strip() or f"EMA-{uuid.uuid4().hex[:6].upper()}"
    item = CustomEplanMacro(
        id=mid,
        tenant_id=body.tenant_id,
        macro_code=body.macro_code.strip(),
        eplan_file=body.eplan_file.strip(),
        variant=(body.variant.strip().upper()[:1] or "A"),
        representation_type=body.representation_type,
        target_load_type=body.target_load_type,
        name=body.name.strip(),
        description=body.description.strip(),
        placeholder_vars=body.placeholder_vars,
    )
    saved = upsert_custom_macro(item)
    record_audit_log(saved.tenant_id, "MACRO_LIB", "EPLAN_MACRO_SAVED", f"Saved .ema macro {saved.macro_code} -> {saved.eplan_file} (Var {saved.variant})", actor=actor)
    return saved


@app.delete("/api/macros/custom/{macro_id}")
def api_delete_custom_macro(
    macro_id: str,
    user: Optional[dict] = Depends(get_optional_user),
) -> dict[str, bool]:
    enforce_permission(user, "manage_catalog")
    ok = delete_custom_macro(macro_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Custom EPLAN macro not found.")
    return {"deleted": True}


@app.post("/api/projects/{project_id}/macros/{macro_id}", response_model=ComputedDesign)
def api_apply_macro(project_id: str, macro_id: str, user: Optional[dict] = Depends(get_optional_user)) -> ComputedDesign:
    actor = enforce_permission(user, "edit_project")
    prj = get_project(project_id)
    if not prj:
        raise HTTPException(status_code=404, detail="Project not found.")
    units = instantiate_macro_units(macro_id, prj)
    if not units:
        raise HTTPException(status_code=404, detail="Macro not found.")
    prj.loads.extend(units)
    save_project(prj)
    record_audit_log(prj.tenant_id, prj.id, "MACRO_APPLIED", f"Inserted macro {macro_id} (+{len(units)} units)", actor=actor)
    return compute_full_design(prj)


@app.get("/api/audit", response_model=list[AuditLogEntry])
def api_list_audit(tenant_id: Optional[str] = None, limit: int = 30) -> list[AuditLogEntry]:
    return [AuditLogEntry(**row) for row in list_audit_logs(tenant_id=tenant_id, limit=limit)]


# --- Project & Interactive 2D Layout Endpoints ---

@app.get("/api/projects", response_model=list[Project])
def api_list_projects(tenant_id: Optional[str] = None) -> list[Project]:
    return list_projects(tenant_id=tenant_id)


@app.get("/api/projects/{project_id}/design", response_model=ComputedDesign)
def api_get_computed_design(project_id: str) -> ComputedDesign:
    prj = get_project(project_id)
    if not prj:
        raise HTTPException(status_code=404, detail="Project not found.")
    return compute_full_design(prj)


@app.post("/api/projects", response_model=ComputedDesign)
def api_save_and_compute_project(project: Project, user: Optional[dict] = Depends(get_optional_user)) -> ComputedDesign:
    actor = enforce_permission(user, "edit_project")
    saved = save_project(project)
    record_audit_log(saved.tenant_id, saved.id, "PROJECT_SAVED", f"Updated '{saved.name}' ({len(saved.loads)} loads, {saved.settings.preferred_vendor}/{saved.settings.plc_vendor})", actor=actor)
    return compute_full_design(saved)


@app.post("/api/projects/{project_id}/layout/positions", response_model=ComputedDesign)
def api_update_layout_positions(
    project_id: str,
    body: LayoutPositionsUpdateRequest,
    user: Optional[dict] = Depends(get_optional_user),
) -> ComputedDesign:
    actor = enforce_permission(user, "edit_project")
    prj = get_project(project_id)
    if not prj:
        raise HTTPException(status_code=404, detail="Project not found.")
    merged = dict(prj.layout_overrides)
    for tag, coords in body.positions.items():
        if "x_mm" in coords and "y_mm" in coords:
            merged[tag] = {"x_mm": round(float(coords["x_mm"]), 1), "y_mm": round(float(coords["y_mm"]), 1)}
    prj.layout_overrides = merged
    save_project(prj)
    record_audit_log(prj.tenant_id, prj.id, "LAYOUT_MOVED", f"Updated 2D positions for {', '.join(body.positions.keys())}", actor=actor)
    return compute_full_design(prj)


@app.post("/api/projects/{project_id}/layout/reset", response_model=ComputedDesign)
def api_reset_layout_positions(project_id: str, user: Optional[dict] = Depends(get_optional_user)) -> ComputedDesign:
    actor = enforce_permission(user, "edit_project")
    prj = get_project(project_id)
    if not prj:
        raise HTTPException(status_code=404, detail="Project not found.")
    prj.layout_overrides = {}
    save_project(prj)
    record_audit_log(prj.tenant_id, prj.id, "LAYOUT_RESET", "Reset 2D mounting plate layout to IEC 61439 auto-placement", actor=actor)
    return compute_full_design(prj)


@app.delete("/api/projects/{project_id}")
def api_delete_project(project_id: str, user: Optional[dict] = Depends(get_optional_user)) -> dict[str, bool]:
    enforce_permission(user, "edit_project")
    ok = delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"deleted": True}


# --- Excel / CSV Importers & Custom Company Catalog (Tenant-Scoped) ---

@app.post("/api/projects/{project_id}/import/loads", response_model=ImportLoadsResponse)
async def api_import_loads(
    project_id: str,
    file: UploadFile = File(...),
    mode: str = Form("replace"),
    user: Optional[dict] = Depends(get_optional_user),
) -> ImportLoadsResponse:
    actor = enforce_permission(user, "edit_project")
    prj = get_project(project_id)
    if not prj:
        raise HTTPException(status_code=404, detail="Project not found.")
    raw = await file.read()
    units, skipped, warnings = parse_loads_file(file.filename or "loads.csv", raw)
    if not units:
        raise HTTPException(status_code=400, detail="No valid load rows found. " + "; ".join(warnings))
    if mode == "append":
        prj.loads.extend(units)
    else:
        prj.loads = units
    save_project(prj)
    record_audit_log(prj.tenant_id, prj.id, "LOADS_IMPORTED", f"Imported {len(units)} loads from '{file.filename}' ({mode})", actor=actor)
    design = compute_full_design(prj)
    return ImportLoadsResponse(imported_count=len(units), skipped_rows=skipped, warnings=warnings, design=design)


@app.get("/api/catalog/custom", response_model=list[CustomCatalogItem])
def api_list_custom_catalog(tenant_id: Optional[str] = None) -> list[CustomCatalogItem]:
    return list_custom_catalog(tenant_id=tenant_id)


@app.post("/api/import/catalog", response_model=ImportCatalogResponse)
async def api_import_catalog(
    file: UploadFile = File(...),
    tenant_id: str = Form("TENANT-KBAT"),
    user: Optional[dict] = Depends(get_optional_user),
) -> ImportCatalogResponse:
    actor = enforce_permission(user, "manage_catalog")
    raw = await file.read()
    items, warnings = parse_catalog_file(file.filename or "catalog.csv", raw)
    if not items:
        raise HTTPException(status_code=400, detail="No valid catalog rows found. " + "; ".join(warnings))
    all_items = upsert_custom_catalog_items(items, tenant_id=tenant_id)
    record_audit_log(tenant_id, "CATALOG", "CATALOG_IMPORTED", f"Uploaded {len(items)} company parts from '{file.filename}'", actor=actor)
    return ImportCatalogResponse(imported_count=len(items), total_custom_items=len(all_items), warnings=warnings, items=all_items)


@app.delete("/api/catalog/custom/{item_id}")
def api_delete_custom_catalog_item(
    item_id: str,
    tenant_id: Optional[str] = None,
    user: Optional[dict] = Depends(get_optional_user),
) -> dict[str, bool]:
    enforce_permission(user, "manage_catalog")
    if item_id == "__ALL__":
        clear_custom_catalog(tenant_id=tenant_id)
        return {"deleted": True}
    ok = delete_custom_catalog_item(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Catalog item not found.")
    return {"deleted": True}


@app.get("/api/templates/{kind}")
def api_download_template(kind: str) -> Response:
    if kind == "loads_csv":
        return Response(
            content=export_load_template_csv(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="PanelCraft_LoadSchedule_Template.csv"'},
        )
    if kind == "catalog_csv":
        return Response(
            content=export_catalog_template_csv(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="PanelCraft_CompanyCatalog_Template.csv"'},
        )
    raise HTTPException(status_code=400, detail="Unsupported template kind.")


# --- External / Local LLM Gateway & AI Copilot ---

@app.get("/api/llm/config", response_model=LlmConfig)
def api_get_llm_config() -> LlmConfig:
    return get_llm_config()


@app.post("/api/llm/config", response_model=LlmConfig)
def api_save_llm_config(cfg: LlmConfig, user: Optional[dict] = Depends(get_optional_user)) -> LlmConfig:
    enforce_permission(user, "manage_settings")
    return save_llm_config(cfg)


@app.post("/api/llm/test")
def api_test_llm(cfg: LlmConfig) -> dict:
    return test_llm_connection(cfg)


@app.post("/api/copilot/parse", response_model=CopilotParseResponse)
def api_copilot_parse(req: CopilotParseRequest) -> CopilotParseResponse:
    return parse_nl_spec(req, llm_cfg=get_llm_config())


@app.post("/api/copilot/parse-pdf", response_model=CopilotParseResponse)
async def api_copilot_parse_pdf(
    file: UploadFile = File(...),
    project_name: Optional[str] = Form(None),
    tenant_id: str = Form("TENANT-KBAT"),
) -> CopilotParseResponse:
    raw = await file.read()
    extracted = extract_pdf_text(raw)
    if not extracted or len(extracted.strip()) < 4:
        raise HTTPException(status_code=400, detail="Could not extract text from uploaded PDF/TXT document.")
    req = CopilotParseRequest(
        prompt=extracted,
        tenant_id=tenant_id,
        project_name=project_name or (Path(file.filename or "RFP_ControlPanel").stem + " Panel"),
    )
    res = parse_nl_spec(req, llm_cfg=get_llm_config())
    res.extracted_notes.insert(0, f"Extracted {len(extracted)} chars from '{file.filename}'")
    return res


@app.post("/api/projects/{project_id}/copilot/interlock", response_model=InterlockResponse)
def api_generate_interlock(project_id: str, body: InterlockRequest) -> InterlockResponse:
    prj = get_project(project_id)
    if not prj:
        raise HTTPException(status_code=404, detail="Project not found.")
    design = compute_full_design(prj)
    return generate_interlock_code(design, body.requirement_text, llm_cfg=get_llm_config())


# --- Revision, RBAC Status Promotion, Rollback & ECN Diff Endpoints ---

class CreateRevisionRequest(BaseModel):
    version_tag: str
    status: str = "Draft"
    author: str = "Controls Engineer"
    summary: str = ""


class RevisionStatusRequest(BaseModel):
    status: str


@app.get("/api/projects/{project_id}/revisions", response_model=list[RevisionRecord])
def api_list_revisions(project_id: str) -> list[RevisionRecord]:
    return list_revisions(project_id)


@app.post("/api/projects/{project_id}/revisions", response_model=RevisionRecord)
def api_create_revision(
    project_id: str,
    body: CreateRevisionRequest,
    user: Optional[dict] = Depends(get_optional_user),
) -> RevisionRecord:
    actor = enforce_permission(user, "create_revision")
    if body.status == "Released":
        enforce_permission(user, "release_revision")
    prj = get_project(project_id)
    if not prj:
        raise HTTPException(status_code=404, detail="Project not found.")
    design = compute_full_design(prj)
    err_cnt = sum(1 for r in design.rule_checks if r.severity == "ERROR")
    snapshot = {
        "settings": prj.settings.model_dump(),
        "loads": [l.model_dump() for l in prj.loads],
        "layout_overrides": prj.layout_overrides,
        "bom": [b.model_dump() for b in design.bom],
    }
    rev = create_revision(
        project_id=project_id,
        version_tag=body.version_tag,
        status=body.status,
        author=body.author or actor,
        summary=body.summary,
        bom_total_krw=design.bom_total_krw,
        total_io_points=len(design.plc_channels),
        error_count=err_cnt,
        snapshot_json=snapshot,
    )
    record_audit_log(prj.tenant_id, prj.id, "REVISION_CREATED", f"Created {rev.version_tag} ({rev.status})", actor=actor)
    return rev


@app.patch("/api/projects/{project_id}/revisions/{rev_id}/status", response_model=RevisionRecord)
def api_update_revision_status(
    project_id: str,
    rev_id: str,
    body: RevisionStatusRequest,
    user: Optional[dict] = Depends(get_optional_user),
) -> RevisionRecord:
    perm = "release_revision" if body.status == "Released" else "create_revision"
    actor = enforce_permission(user, perm)
    rev = get_revision(rev_id)
    if not rev or rev.project_id != project_id:
        raise HTTPException(status_code=404, detail="Revision not found.")
    if body.status not in ("Draft", "In Review", "Released"):
        raise HTTPException(status_code=400, detail="Invalid status.")
    updated = update_revision_status(rev_id, body.status)
    assert updated is not None
    prj = get_project(project_id)
    if prj:
        record_audit_log(prj.tenant_id, prj.id, "REVISION_STATUS", f"Changed {updated.version_tag} status -> {body.status}", actor=actor)
    return updated


@app.post("/api/projects/{project_id}/revisions/{rev_id}/restore", response_model=ComputedDesign)
def api_restore_revision(
    project_id: str,
    rev_id: str,
    user: Optional[dict] = Depends(get_optional_user),
) -> ComputedDesign:
    actor = enforce_permission(user, "rollback_revision")
    prj = get_project(project_id)
    rev = get_revision(rev_id)
    if not prj or not rev or rev.project_id != project_id:
        raise HTTPException(status_code=404, detail="Project or revision not found.")
    snap = rev.snapshot_json
    if "settings" in snap:
        prj.settings = ProjectSettings.model_validate(snap["settings"])
    if "loads" in snap:
        prj.loads = [LoadUnit.model_validate(l) for l in snap["loads"]]
    prj.layout_overrides = snap.get("layout_overrides", {})
    save_project(prj)
    record_audit_log(prj.tenant_id, prj.id, "REVISION_RESTORED", f"Rolled back project to {rev.version_tag}", actor=actor)
    return compute_full_design(prj)


@app.get("/api/projects/{project_id}/revisions/diff")
def api_diff_revisions(project_id: str, base_id: str, target_id: str) -> dict:
    revs = {r.id: r for r in list_revisions(project_id)}
    if base_id not in revs or target_id not in revs:
        raise HTTPException(status_code=404, detail="Revisions to compare not found.")
    return diff_revisions(revs[base_id], revs[target_id])


# --- Downloadable Engineering Artifact Exporters ---

@app.get("/api/projects/{project_id}/export/{fmt}")
def api_export(
    project_id: str,
    fmt: str,
    sheet: Optional[int] = None,
    thermal: Optional[bool] = False,
    macro_file: Optional[str] = None,
) -> Response:
    prj = get_project(project_id)
    if not prj:
        raise HTTPException(status_code=404, detail="Project not found.")
    custom_macros = list_custom_macros(tenant_id=prj.tenant_id)
    design = compute_full_design(prj, custom_macros=custom_macros)

    if fmt == "bom_csv":
        return Response(content=export_bom_csv(design), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{project_id}_BOM.csv"'})
    if fmt == "io_csv":
        return Response(content=export_io_csv(design), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{project_id}_IO_LIST.csv"'})
    if fmt == "terminals_csv":
        return Response(content=export_terminals_csv(design), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{project_id}_TERMINALS.csv"'})
    if fmt == "plc_st":
        return PlainTextResponse(content=design.plc_st_code, headers={"Content-Disposition": f'attachment; filename="{project_id}_MainControl.st"'})
    if fmt == "dxf":
        return PlainTextResponse(content=export_project_dxf(design), media_type="application/dxf", headers={"Content-Disposition": f'attachment; filename="{project_id}_Schematic.dxf"'})
    if fmt == "layout_dxf":
        return PlainTextResponse(content=export_project_layout_dxf(design), media_type="application/dxf", headers={"Content-Disposition": f'attachment; filename="{project_id}_MountingPlate_2D.dxf"'})
    if fmt == "layout_svg":
        svg = design.panel_layout.svg_thermal if thermal else design.panel_layout.svg
        return Response(content=svg, media_type="image/svg+xml", headers={"Content-Disposition": f'attachment; filename="{project_id}_MountingPlate_2D.svg"'})
    if fmt == "eplan_aml":
        return Response(content=export_eplan_aml(design), media_type="application/xml; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{project_id}_EPLAN.aml"'})
    if fmt == "eplan_ema":
        ema_fname, ema_xml = generate_eplan_ema_xml(
            design.project, design.load_calculations, custom_macros=custom_macros, target_macro_file=macro_file
        )
        return Response(content=ema_xml, media_type="application/xml; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{ema_fname}"'})
    if fmt == "plcopen_xml":
        return Response(content=export_plcopen_xml(design), media_type="application/xml; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{project_id}_PLCopen.xml"'})
    if fmt == "eplan_parts_csv":
        return Response(content=export_eplan_parts_csv(design), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{project_id}_EPLAN_Parts.csv"'})
    if fmt == "wire_labels_csv":
        return Response(content=export_wire_labels_csv(design), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{project_id}_WireMarkers_Labels.csv"'})
    if fmt == "dossier_html":
        return Response(content=export_engineering_dossier_html(design), media_type="text/html; charset=utf-8", headers={"Content-Disposition": f'inline; filename="{project_id}_Engineering_Report.html"'})
    if fmt == "package_zip":
        record_audit_log(prj.tenant_id, prj.id, "PACKAGE_EXPORTED", f"Downloaded full engineering package ZIP ({len(design.schematic_sheets)} sheets, {len(design.bom)} BOM items)")
        return Response(content=export_full_package_zip(design, custom_macros=custom_macros), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{project_id}_Engineering_Package.zip"'})
    if fmt == "fat_md":
        return PlainTextResponse(content=export_fat_checklist_md(design), media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{project_id}_FAT_Checklist.md"'})
    if fmt == "svg":
        idx = max(0, min((sheet or 1) - 1, len(design.schematic_sheets) - 1))
        sh = design.schematic_sheets[idx]
        return Response(content=sh.svg, media_type="image/svg+xml", headers={"Content-Disposition": f'attachment; filename="{project_id}_{sh.code}.svg"'})
    raise HTTPException(status_code=400, detail=f"Unsupported export format: {fmt}")


# --- Serve Frontend SPA, Icons & PWA Assets ---

if FRONTEND_DIR.exists():
    app.mount("/styles", StaticFiles(directory=str(FRONTEND_DIR / "styles")), name="styles")
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
    if (FRONTEND_DIR / "icons").exists():
        app.mount("/icons", StaticFiles(directory=str(FRONTEND_DIR / "icons")), name="icons")


@app.get("/manifest.json")
def serve_manifest() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "manifest.json"), media_type="application/manifest+json")


@app.get("/sw.js")
def serve_sw() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "sw.js"), media_type="application/javascript")


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "index.html"))
