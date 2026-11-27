"""SSOT (Single Source of Truth) Pydantic models for PanelCraft AI Multi-Tenant SaaS."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


StandardProfile = Literal["IEC 60204-1", "KS C IEC 60364", "UL 508A"]
PowerSystem = Literal["3P_380V_60Hz", "3P_440V_60Hz", "3P_220V_60Hz", "3P_480V_60Hz", "1P_220V_60Hz"]
VendorProfile = Literal[
    "LS Electric",
    "Schneider Electric",
    "Siemens",
    "Mitsubishi Electric",
    "ABB",
    "Fuji Electric",
    "Omron",
]
PlcVendor = Literal[
    "Mitsubishi Electric",
    "LS Electric",
    "Siemens",
    "Rockwell Automation",
    "Omron",
    "Beckhoff",
]
LoadType = Literal[
    "motor_dol",
    "motor_inv",
    "servo",
    "heater",
    "solenoid_group",
    "sensor_group",
    "safety_circuit",
]
SafetyLevel = Literal["PLc", "PLd", "PLe"]
RevisionStatus = Literal["Draft", "In Review", "Released"]
LlmProvider = Literal["builtin", "ollama", "openai_compat"]


class TenantOrg(BaseModel):
    """Multi-tenant manufacturer organization workspace."""

    id: str
    name: str
    industry: str = "Industrial Automation"
    titleblock_company: str = ""
    default_standard: StandardProfile = "IEC 60204-1"
    default_vendor: VendorProfile = "LS Electric"
    default_plc: PlcVendor = "Mitsubishi Electric"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class LoadUnit(BaseModel):
    """Functional unit / load entry in the SSOT engineering model."""

    id: str
    tag: str = Field(..., description="Functional unit tag e.g. CONV_01")
    name: str = Field(..., description="Descriptive Korean/English name")
    load_type: LoadType
    power_kw: float = Field(default=0.0, ge=0.0, description="Rated power in kW")
    quantity: int = Field(default=1, ge=1, description="Number of identical channels or sub-loads")
    voltage: int = Field(default=380, description="Operating voltage (480, 440, 380, 220, 24)")
    phases: int = Field(default=3, description="3 for 3-phase, 1 for 1-phase, 0 for DC")
    cable_length_m: float = Field(default=15.0, ge=1.0, description="Cable run length in meters")
    power_factor: float = Field(default=0.85, gt=0.1, le=1.0)
    efficiency: float = Field(default=0.88, gt=0.1, le=1.0)
    demand_factor: float = Field(default=0.85, gt=0.1, le=1.0)
    safety_level: Optional[SafetyLevel] = None
    has_surge_suppressor: bool = True
    has_emi_filter: bool = True
    notes: str = ""


class ProjectSettings(BaseModel):
    standard_profile: StandardProfile = "IEC 60204-1"
    power_system: PowerSystem = "3P_380V_60Hz"
    control_voltage_dc: int = 24
    preferred_vendor: VendorProfile = "LS Electric"
    plc_vendor: PlcVendor = "Mitsubishi Electric"
    io_spare_ratio: float = Field(default=0.20, ge=0.0, le=0.50)
    ambient_temp_c: float = Field(default=35.0, ge=10.0, le=55.0)
    max_internal_temp_c: float = Field(default=45.0, ge=25.0, le=60.0)
    supply_transformer_kva: float = Field(default=500.0, ge=50.0, le=5000.0)
    supply_impedance_pct: float = Field(default=4.5, ge=2.0, le=12.0)
    feeder_length_m: float = Field(default=25.0, ge=1.0, le=500.0)
    enclosure_install_type: Literal["freestanding_all_open", "wall_mounted", "bayed_side_by_side"] = "freestanding_all_open"


class Project(BaseModel):
    id: str
    tenant_id: str = "TENANT-KBAT"
    name: str
    client: str = "Standard Automation Line"
    description: str = ""
    settings: ProjectSettings = Field(default_factory=ProjectSettings)
    loads: list[LoadUnit] = Field(default_factory=list)
    layout_overrides: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Custom user-dragged 2D mounting plate coordinates {tag: {x_mm, y_mm}}",
    )
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class CustomCatalogItem(BaseModel):
    """Company-specific preferred component entry imported via Excel/CSV (tenant-scoped)."""

    id: str
    tenant_id: str = "TENANT-KBAT"
    category: Literal["MCCB", "MC", "INVERTER", "SERVO", "SMPS"]
    manufacturer: str
    part_number: str
    rated_value: float = Field(..., description="Rated Amps (MCCB/MC/SMPS) or Rated kW (INVERTER/SERVO)")
    spec: str
    unit_price_krw: int = Field(default=0, ge=0)
    lead_time_days: int = Field(default=3, ge=0)
    lifecycle_status: str = "Preferred (사내표준)"


class LoadCalculationResult(BaseModel):
    unit_id: str
    tag: str
    name: str
    load_type: LoadType
    iec_device_tag: str
    eplan_macro: str = "EPLAN_M_GENERIC.ema"
    eplan_macro_variant: str = "A"
    rated_current_a: float
    design_current_a: float
    starting_current_a: float
    wire_sq: float
    wire_awg: str = "16 AWG"
    voltage_drop_pct: float
    breaker_rating_a: int
    breaker_icu_ka: int = 25
    breaker_part: str
    contactor_part: Optional[str] = None
    drive_part: Optional[str] = None
    dc24v_current_a: float = 0.0
    heat_loss_w: float = 0.0
    formula_trace: str = ""


class SelectivityBranchItem(BaseModel):
    """IEC 60909 branch fault level & IEC 60364-5-53 upstream/downstream breaker selectivity."""

    tag: str
    name: str
    upstream_part: str
    upstream_rating_a: int
    downstream_part: str
    downstream_rating_a: int
    downstream_icu_ka: int
    ik3_branch_ka: float
    selectivity_ratio: float
    coordination_status: Literal["TOTAL", "PARTIAL", "NON_SELECTIVE"]
    breaking_ok: bool
    note: str = ""


class ThermalAnalysis(BaseModel):
    """IEC 60890 enclosure surface dissipation & precision cooling equipment sizing."""

    enclosure_w_mm: int
    enclosure_h_mm: int
    enclosure_d_mm: int
    install_type: str
    effective_surface_m2: float
    natural_dissipation_w: float
    net_cooling_required_w: float
    predicted_uncooled_temp_c: float
    predicted_cooled_temp_c: float
    required_airflow_m3h: float
    cooling_mode: Literal["NATURAL", "FILTER_FAN", "PANEL_AC"]
    recommended_cooling_part: str
    recommended_cooling_capacity_w: int
    thermal_margin_c: float


class PowerSummary(BaseModel):
    system_voltage_v: int
    phases: int
    total_connected_kw: float
    total_demand_kw: float
    total_rated_current_a: float
    total_demand_current_a: float
    main_breaker_rating_a: int
    main_breaker_icu_ka: int = 25
    main_breaker_part: str
    main_wire_sq: float
    main_wire_awg: str = "10 AWG"
    panel_sccr_ka: int = 18
    ik3_main_ka: float = 0.0
    ip_peak_ka: float = 0.0
    ik1_min_ka: float = 0.0
    main_breaking_margin_pct: float = 0.0
    selectivity_summary: str = ""
    selectivity_checks: list[SelectivityBranchItem] = Field(default_factory=list)
    thermal_analysis: Optional[ThermalAnalysis] = None
    transformer_part: Optional[str] = None
    transformer_kva: float = 0.0
    total_dc24v_current_a: float
    smps_required_a: float
    smps_selected_part: str
    smps_capacity_a: float
    total_heat_loss_w: float
    cooling_required_m3h: float
    cooling_solution: str
    enclosure_size_mm: str
    enclosure_part: str


class BomItem(BaseModel):
    line_no: int
    category: str
    iec_tags: list[str]
    manufacturer: str
    part_number: str
    spec: str
    quantity: int
    unit: str = "EA"
    unit_price_krw: int
    total_price_krw: int
    lead_time_days: int
    lifecycle_status: str = "Active"


class PlcModule(BaseModel):
    slot: int
    module_type: str
    part_number: str
    manufacturer: str
    description: str
    channels: int
    used_channels: int
    start_address: str
    end_address: str


class PlcChannel(BaseModel):
    channel_id: str
    io_type: Literal["DI", "DO", "AI", "AO"]
    plc_address: str
    slot: int
    point_index: int
    terminal_tag: str
    wire_number: str
    unit_tag: str
    signal_name: str
    voltage: str = "DC 24V"


class TerminalRow(BaseModel):
    strip: str
    terminal_no: int
    wire_number: str
    wire_sq: float
    wire_color: str
    from_device: str
    to_device: str
    signal: str


class RuleCheckItem(BaseModel):
    rule_id: str
    severity: Literal["ERROR", "WARNING", "INFO"]
    category: Literal["ERC", "DRC", "SAFETY", "THERMAL", "AI_REVIEW"]
    standard_ref: str
    target_tag: str
    title: str
    detail: str
    recommendation: str


class SchematicSheet(BaseModel):
    sheet_no: int
    code: str
    title: str
    svg: str


class LayoutComponent(BaseModel):
    tag: str
    label: str
    part_number: str
    zone: Literal["POWER", "DRIVE", "CONTROL", "TERMINAL"]
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float
    d_mm: float
    heat_w: float = 0.0
    clearance_mm: float = 0.0


class LayoutIssue(BaseModel):
    severity: Literal["ERROR", "WARNING"]
    code: str
    targets: list[str]
    message: str


class WireLengthEstimate(BaseModel):
    wire_sq: float
    wire_awg: str
    purpose: str
    route_count: int
    total_length_m: float
    unit_price_per_m_krw: int
    total_price_krw: int


class PanelLayout(BaseModel):
    enclosure_w_mm: int
    enclosure_h_mm: int
    enclosure_d_mm: int
    plate_w_mm: int
    plate_h_mm: int
    utilization_pct: float
    power_zone_separation_mm: int = 60
    components: list[LayoutComponent]
    layout_issues: list[LayoutIssue] = Field(default_factory=list)
    wire_length_summary: list[WireLengthEstimate] = Field(default_factory=list)
    total_panel_wire_m: float = 0.0
    svg: str
    svg_thermal: str


class ComputedDesign(BaseModel):
    project: Project
    tenant_name: str = "PanelCraft Organization"
    power_summary: PowerSummary
    load_calculations: list[LoadCalculationResult]
    bom: list[BomItem]
    bom_total_krw: int
    plc_modules: list[PlcModule]
    plc_channels: list[PlcChannel]
    plc_st_code: str
    terminals: list[TerminalRow]
    rule_checks: list[RuleCheckItem]
    schematic_sheets: list[SchematicSheet]
    panel_layout: PanelLayout


class RevisionRecord(BaseModel):
    id: str
    project_id: str
    version_tag: str
    status: RevisionStatus = "Draft"
    author: str = "Controls Engineer"
    summary: str = ""
    created_at: str
    bom_total_krw: int
    total_io_points: int
    error_count: int
    snapshot_json: dict[str, Any]


class LlmConfig(BaseModel):
    provider: LlmProvider = "builtin"
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    timeout_sec: int = Field(default=25, ge=5, le=120)


class CopilotParseRequest(BaseModel):
    prompt: str
    tenant_id: str = "TENANT-KBAT"
    preferred_vendor: Optional[VendorProfile] = None
    plc_vendor: Optional[PlcVendor] = None
    project_name: Optional[str] = None


class CopilotParseResponse(BaseModel):
    suggested_project: Project
    extracted_notes: list[str]
    confidence: float
    engine_used: str = "Offline Deterministic Parser"


class InterlockRequest(BaseModel):
    requirement_text: str


class InterlockRule(BaseModel):
    alarm_code: str
    condition: str
    action: str
    reset_policy: str
    related_io: list[str] = Field(default_factory=list)


class InterlockResponse(BaseModel):
    st_code: str
    alarms: list[InterlockRule]
    engine_used: str
    notes: list[str]


class ImportLoadsResponse(BaseModel):
    imported_count: int
    skipped_rows: int
    warnings: list[str]
    design: ComputedDesign


class ImportCatalogResponse(BaseModel):
    imported_count: int
    total_custom_items: int
    warnings: list[str]
    items: list[CustomCatalogItem]


class UpdateConfig(BaseModel):
    github_repo: str = "knoxxr/panelcraft-ai"
    channel: Literal["stable", "beta"] = "stable"
    auto_check_on_startup: bool = True


class UpdateCheckResponse(BaseModel):
    status: Literal["up_to_date", "update_available", "check_failed"]
    current_version: str
    latest_version: str
    update_available: bool
    release_url: str
    release_notes: str = ""
    published_at: str = ""
    assets: list[dict[str, Any]] = Field(default_factory=list)
    checked_at: str
    message: str


class AppVersionInfo(BaseModel):
    app_version: str
    os: str
    os_release: str
    arch: str
    python_version: str
    update_config: UpdateConfig
    github_links: dict[str, str]
    changelog: list[dict[str, Any]]


class CircuitMacroTemplate(BaseModel):
    macro_id: str
    eplan_file: str
    name_en: str
    name_ko: str
    category: str
    description_en: str
    description_ko: str
    loads: list[dict[str, Any]]


class AuditLogEntry(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    action: str
    actor: str
    detail: str
    created_at: str


UserRole = Literal["admin", "reviewer", "designer", "viewer"]


class UserPublic(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    tenant_id: str
    permissions: list[str] = Field(default_factory=list)
    created_at: str


class AuthRegisterRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=6)
    full_name: str
    role: UserRole = "designer"
    tenant_id: str = "TENANT-KBAT"


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class LayoutPositionsUpdateRequest(BaseModel):
    positions: dict[str, dict[str, float]]


class CustomEplanMacro(BaseModel):
    """Company-specific EPLAN Electric P8 .ema window macro template & placeholder mapping."""

    id: str
    tenant_id: str = "TENANT-KBAT"
    macro_code: str = Field(..., description="Internal macro ID e.g. KBAT-VFD-01")
    eplan_file: str = Field(..., description="EPLAN .ema path e.g. $(MD_MACROS)\\KBAT\\VFD_3P.ema")
    variant: str = Field(default="A", description="EPLAN Macro Variant A..P")
    representation_type: Literal["Multi-line", "Single-line", "Panel layout", "Overview"] = "Multi-line"
    target_load_type: LoadType
    name: str
    description: str = ""
    placeholder_vars: dict[str, str] = Field(default_factory=dict)
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class CustomEplanMacroRequest(BaseModel):
    id: Optional[str] = None
    tenant_id: str = "TENANT-KBAT"
    macro_code: str
    eplan_file: str
    variant: str = "A"
    representation_type: Literal["Multi-line", "Single-line", "Panel layout", "Overview"] = "Multi-line"
    target_load_type: LoadType
    name: str
    description: str = ""
    placeholder_vars: dict[str, str] = Field(default_factory=dict)



