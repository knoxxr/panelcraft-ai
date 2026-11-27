"""Deterministic electrical capacity, component selection (with custom company catalog priority), thermal & BOM engine."""

from __future__ import annotations

import math

from backend.catalog import (
    BreakerSpec,
    ContactorSpec,
    DriveSpec,
    PLC_CATALOG,
    SAFETY_RELAY_BY_VENDOR,
    SmpsSpec,
    select_breaker,
    select_contactor,
    select_control_transformer,
    select_drive,
    select_smps,
    select_wire_sq,
    sq_to_awg,
)
from backend.models import (
    BomItem,
    CustomCatalogItem,
    CustomEplanMacro,
    LoadCalculationResult,
    PlcModule,
    PowerSummary,
    Project,
    SelectivityBranchItem,
    ThermalAnalysis,
)


POWER_SYSTEM_SPECS: dict[str, tuple[int, int]] = {
    "3P_380V_60Hz": (380, 3),
    "3P_440V_60Hz": (440, 3),
    "3P_480V_60Hz": (480, 3),
    "3P_220V_60Hz": (220, 3),
    "1P_220V_60Hz": (220, 1),
}

EPLAN_MACRO_MAP: dict[str, str] = {
    "motor_inv": "EPLAN_M_VFD_3P.ema",
    "motor_dol": "EPLAN_M_DOL_3P.ema",
    "servo": "EPLAN_M_SERVO_AX.ema",
    "heater": "EPLAN_M_HEATER_PID.ema",
    "solenoid_group": "EPLAN_M_SOL_24VDC.ema",
    "sensor_group": "EPLAN_M_SEN_24VDC.ema",
    "safety_circuit": "EPLAN_M_SAFETY_DUAL.ema",
}


def _match_custom(
    custom_catalog: list[CustomCatalogItem],
    category: str,
    required_value: float,
) -> CustomCatalogItem | None:
    candidates = [
        c for c in custom_catalog
        if c.category == category and c.rated_value >= required_value
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda x: x.rated_value)
    return candidates[0]


def _compute_iec60909_short_circuit(
    sys_v: int,
    sys_p: int,
    tx_kva: float,
    tx_z_pct: float,
    feeder_len_m: float,
    feeder_sq: float,
) -> tuple[float, float, float, float, float]:
    """Compute IEC 60909-0 prospective short-circuit current at main panel busbar.

    Returns (ik3_main_ka, ip_peak_ka, ik1_min_ka, r_main_ohm, x_main_ohm).
    """
    c_max = 1.05  # IEC 60909 Table 1 voltage factor for LV 380-480V
    s_va = max(tx_kva, 50.0) * 1000.0
    z_tr = (tx_z_pct / 100.0) * (sys_v ** 2) / s_va
    r_tr = z_tr * 0.25
    x_tr = math.sqrt(max(z_tr ** 2 - r_tr ** 2, 1e-9))

    # Copper feeder impedance at 20C (worst-case maximum fault current)
    rho_cu_20 = 0.0185  # Ohm * mm^2 / m
    r_fdr = rho_cu_20 * max(feeder_len_m, 1.0) / max(feeder_sq, 2.5)
    x_fdr = 0.00008 * max(feeder_len_m, 1.0)

    r_tot = r_tr + r_fdr
    x_tot = x_tr + x_fdr
    z_tot = math.sqrt(r_tot ** 2 + x_tot ** 2)

    if sys_p == 3:
        ik3_a = (c_max * sys_v) / (math.sqrt(3.0) * max(z_tot, 1e-6))
    else:
        ik3_a = (c_max * sys_v) / (2.0 * max(z_tot, 1e-6))

    rx_ratio = r_tot / max(x_tot, 1e-6)
    kappa = 1.02 + 0.98 * math.exp(-3.0 * rx_ratio)
    ik3_ka = round(ik3_a / 1000.0, 2)
    ip_ka = round(kappa * math.sqrt(2.0) * ik3_ka, 2)
    ik1_min_ka = round(ik3_ka * 0.62, 2)
    return ik3_ka, ip_ka, ik1_min_ka, r_tot, x_tot


def _compute_iec60890_thermal(
    enc_w_mm: int,
    enc_h_mm: int,
    enc_d_mm: int,
    install_type: str,
    ambient_c: float,
    max_internal_c: float,
    total_heat_w: float,
) -> tuple[ThermalAnalysis, str, tuple[str, str, str, str, int, int, int, str]]:
    """Precision IEC 60890 effective enclosure surface & cooling unit selection.

    Returns (ThermalAnalysis, cooling_solution_summary, bom_tuple).
    """
    w = enc_w_mm / 1000.0
    h = enc_h_mm / 1000.0
    d = enc_d_mm / 1000.0

    # IEC 60890 Table 1 mounting surface area factors (m^2)
    if install_type == "wall_mounted":
        ae = 1.4 * w * (h + d) + 1.8 * d * h
    elif install_type == "bayed_side_by_side":
        ae = 1.4 * h * (w + d) + 1.4 * w * d
    else:
        ae = 1.8 * h * (w + d) + 1.4 * w * d

    k_steel = 5.5  # W / (m^2 * K) painted sheet steel enclosure
    delta_t = max(max_internal_c - ambient_c, 5.0)
    natural_w = k_steel * ae * delta_t
    net_cool_w = max(0.0, total_heat_w - natural_w)
    uncooled_temp = ambient_c + (total_heat_w / max(k_steel * ae, 0.1))
    req_airflow = round((3.1 * max(net_cool_w, total_heat_w * 0.35)) / delta_t, 1) if total_heat_w > natural_w else 0.0

    if net_cool_w <= 0.0 and uncooled_temp <= max_internal_c - 2.0:
        mode = "NATURAL"
        part = "SK 3237.200"
        cap_w = int(round(natural_w))
        cooled_temp = round(uncooled_temp, 1)
        sol = f"IEC 60890 자연 대류 방열 충분 (유효면적 {ae:.2f}m², 자연방열 {natural_w:.0f}W ≥ {total_heat_w:.0f}W)"
        bom_item = ("방열 액세서리", "Rittal", part, "필터 루버 벤트 세트 (자연대류)", 2, 32000, 3, "-E_VENT")
    elif ambient_c <= max_internal_c - 7.0 and net_cool_w <= 550.0:
        mode = "FILTER_FAN"
        if req_airflow <= 150.0:
            part, fan_flow, price, cap_w = "SK 3240.100", 180, 185000, 480
        else:
            part, fan_flow, price, cap_w = "SK 3243.100", 550, 320000, 950
        cooled_temp = round(min(max_internal_c - 2.5, ambient_c + (3.1 * net_cool_w) / max(fan_flow, 100.0) + 2.5), 1)
        sol = f"IEC 60890 강제 필터 팬 ({part}, {fan_flow} m³/h | 필요풍량 {req_airflow} m³/h, 순냉각 {net_cool_w:.0f}W)"
        bom_item = ("냉각 팬", "Rittal", part, f"TopTherm 필터팬 {fan_flow} m³/h + 배기필터", 1, price, 4, "-M_FAN1")
    else:
        mode = "PANEL_AC"
        req_ac_w = max(500.0, net_cool_w * 1.25 if ambient_c < max_internal_c else total_heat_w * 1.25)
        if req_ac_w <= 550:
            part, cap_w, price = "SK 3185.830", 500, 1180000
        elif req_ac_w <= 1050:
            part, cap_w, price = "SK 3304.500", 1000, 1650000
        elif req_ac_w <= 1650:
            part, cap_w, price = "SK 3186.930", 1600, 2250000
        else:
            part, cap_w, price = "SK 3188.940", 2500, 2980000
        cooled_temp = round(min(max_internal_c - 5.0, 35.0), 1)
        sol = f"IEC 60890 밀폐형 판넬 에어컨 ({part}, 냉각능력 {cap_w}W | 미냉각 시 {uncooled_temp:.1f}°C)"
        bom_item = ("판넬 쿨러", "Rittal", part, f"Blue e+ 제어반 냉각기 {cap_w}W (IP55 밀폐)", 1, price, 10, "-A_COOL1")

    analysis = ThermalAnalysis(
        enclosure_w_mm=enc_w_mm,
        enclosure_h_mm=enc_h_mm,
        enclosure_d_mm=enc_d_mm,
        install_type=install_type,
        effective_surface_m2=round(ae, 2),
        natural_dissipation_w=round(natural_w, 1),
        net_cooling_required_w=round(net_cool_w, 1),
        predicted_uncooled_temp_c=round(uncooled_temp, 1),
        predicted_cooled_temp_c=cooled_temp,
        required_airflow_m3h=req_airflow,
        cooling_mode=mode,
        recommended_cooling_part=part,
        recommended_cooling_capacity_w=cap_w,
        thermal_margin_c=round(max_internal_c - cooled_temp, 1),
    )
    return analysis, sol, bom_item


def compute_electrical_and_bom(
    project: Project,
    plc_modules: list[PlcModule],
    custom_catalog: list[CustomCatalogItem] | None = None,
    custom_macros: list[CustomEplanMacro] | None = None,
) -> tuple[PowerSummary, list[LoadCalculationResult], list[BomItem], int]:
    """Run deterministic electrical formulas, IEC 60909/60890 analysis, select components, and compile SSOT BOM."""

    custom_list = custom_catalog or []
    macro_by_type: dict[str, CustomEplanMacro] = {m.target_load_type: m for m in (custom_macros or [])}

    def resolve_macro(ltype: str) -> tuple[str, str]:
        cm = macro_by_type.get(ltype)
        if cm:
            return cm.eplan_file, cm.variant
        return EPLAN_MACRO_MAP.get(ltype, "EPLAN_M_GENERIC.ema"), "A"

    sys_v, sys_p = POWER_SYSTEM_SPECS.get(project.settings.power_system, (380, 3))
    vendor = project.settings.preferred_vendor
    ambient = project.settings.ambient_temp_c
    delta_t = max(project.settings.max_internal_temp_c - ambient, 5.0)

    results: list[LoadCalculationResult] = []
    bom_acc: dict[tuple[str, str, str], dict] = {}

    def pick_breaker(req_a: float) -> tuple[BreakerSpec, str]:
        cust = _match_custom(custom_list, "MCCB", req_a)
        if cust:
            return (
                BreakerSpec(
                    cust.manufacturer,
                    cust.part_number,
                    int(round(cust.rated_value)),
                    3,
                    25,
                    cust.spec,
                    cust.unit_price_krw,
                    cust.lead_time_days,
                    heat_w=2.5 + cust.rated_value * 0.055,
                ),
                cust.lifecycle_status,
            )
        return select_breaker(vendor, req_a), "Active"

    def pick_contactor(req_a: float) -> tuple[ContactorSpec, str]:
        cust = _match_custom(custom_list, "MC", req_a)
        if cust:
            return (
                ContactorSpec(
                    cust.manufacturer,
                    cust.part_number,
                    int(round(cust.rated_value)),
                    "DC 24V",
                    cust.spec,
                    cust.unit_price_krw,
                    cust.lead_time_days,
                    heat_w=3.2,
                ),
                cust.lifecycle_status,
            )
        return select_contactor(vendor, req_a), "Active"

    def pick_drive(kind: str, req_kw: float) -> tuple[DriveSpec, str]:
        cat = "INVERTER" if kind == "inverter" else "SERVO"
        cust = _match_custom(custom_list, cat, req_kw)
        if cust:
            return (
                DriveSpec(
                    cust.manufacturer,
                    cust.part_number,
                    kind,
                    cust.rated_value,
                    380 if kind == "inverter" else 220,
                    cust.spec,
                    cust.unit_price_krw,
                    cust.lead_time_days,
                ),
                cust.lifecycle_status,
            )
        return select_drive(vendor, kind, req_kw), "Active"

    def pick_smps(req_a: float) -> tuple[SmpsSpec, str]:
        cust = _match_custom(custom_list, "SMPS", req_a)
        if cust:
            return (
                SmpsSpec(
                    cust.manufacturer,
                    cust.part_number,
                    cust.rated_value,
                    int(round(cust.rated_value * 24)),
                    cust.spec,
                    cust.unit_price_krw,
                    cust.lead_time_days,
                ),
                cust.lifecycle_status,
            )
        return select_smps(req_a), "Active"

    def add_bom(
        category: str,
        manufacturer: str,
        part_number: str,
        spec: str,
        qty: int,
        unit_price: int,
        lead_days: int,
        iec_tag: str,
        lifecycle_status: str = "Active",
    ) -> None:
        key = (category, manufacturer, part_number)
        if key not in bom_acc:
            bom_acc[key] = {
                "category": category,
                "manufacturer": manufacturer,
                "part_number": part_number,
                "spec": spec,
                "quantity": 0,
                "unit_price_krw": unit_price,
                "lead_time_days": lead_days,
                "iec_tags": [],
                "lifecycle_status": lifecycle_status,
            }
        bom_acc[key]["quantity"] += qty
        if iec_tag and iec_tag not in bom_acc[key]["iec_tags"]:
            bom_acc[key]["iec_tags"].append(iec_tag)

    total_connected_kw = 0.0
    total_demand_kw = 0.0
    total_rated_ac_a = 0.0
    total_demand_ac_a = 0.0
    max_starting_delta_a = 0.0
    total_dc24v_a = 0.0
    total_heat_w = 0.0

    q_idx = 1
    k_idx = 1
    m_idx = 1
    u_idx = 1
    e_idx = 1
    y_idx = 1
    b_idx = 1
    saf_idx = 1

    for load in project.loads:
        qty = max(load.quantity, 1)

        if load.load_type in ("motor_dol", "motor_inv", "servo", "heater"):
            unit_kw = load.power_kw
            total_kw = unit_kw * qty
            v = load.voltage if load.voltage > 0 else sys_v
            ph = load.phases if load.phases in (1, 3) else sys_p

            pf, eff = (1.0, 1.0) if load.load_type == "heater" else (load.power_factor, load.efficiency)

            if ph == 3:
                unit_in = (unit_kw * 1000.0) / (math.sqrt(3) * v * pf * eff)
                formula = f"I = ({unit_kw}kW × 1000) / (√3 × {v}V × {pf:.2f} × {eff:.2f}) = {unit_in:.2f}A"
            else:
                unit_in = (unit_kw * 1000.0) / (v * pf * eff)
                formula = f"I = ({unit_kw}kW × 1000) / ({v}V × {pf:.2f} × {eff:.2f}) = {unit_in:.2f}A"

            design_a = unit_in * 1.25
            if load.load_type == "motor_dol":
                start_a = unit_in * 6.0
                breaker_req = unit_in * 2.0
            elif load.load_type in ("motor_inv", "servo"):
                start_a = unit_in * 1.5
                breaker_req = unit_in * 1.45
            else:
                start_a = unit_in * 1.05
                breaker_req = unit_in * 1.25

            wire_sq, vd_pct = select_wire_sq(
                design_current_a=design_a,
                voltage_v=v,
                phases=ph,
                length_m=load.cable_length_m,
                ambient_temp_c=ambient,
            )

            brk, brk_status = pick_breaker(breaker_req)
            q_tag = f"-Q{q_idx}" if qty == 1 else f"-Q{q_idx}..Q{q_idx + qty - 1}"
            q_idx += qty
            add_bom("차단기 (MCCB)", brk.vendor, brk.part_number, brk.spec, qty, brk.price_krw, brk.lead_days, q_tag, brk_status)

            mc_part: str | None = None
            drv_part: str | None = None
            heat_w = brk.heat_w * qty
            dc24_a = 0.0

            if load.load_type == "motor_dol":
                mc, mc_status = pick_contactor(unit_in * 1.15)
                mc_part = mc.part_number
                k_tag = f"-K{k_idx}" if qty == 1 else f"-K{k_idx}..K{k_idx + qty - 1}"
                k_idx += qty
                dev_tag = f"-M{m_idx}" if qty == 1 else f"-M{m_idx}..M{m_idx + qty - 1}"
                m_idx += qty
                add_bom("전자접촉기 (MC)", mc.vendor, mc.part_number, mc.spec, qty, mc.price_krw, mc.lead_days, k_tag, mc_status)
                add_bom("열동계전기 (THR)", mc.vendor, f"MT-{mc.rated_a} ({unit_in:.1f}A)", f"과부하 계전기 설정 {unit_in:.1f}A", qty, 24000, 3, f"-F{m_idx}")
                dc24_a = 0.12 * qty
                heat_w += (mc.heat_w + 3.0) * qty

            elif load.load_type == "motor_inv":
                drv, drv_status = pick_drive("inverter", unit_kw)
                drv_part = drv.part_number
                u_tag = f"-U{u_idx}" if qty == 1 else f"-U{u_idx}..U{u_idx + qty - 1}"
                u_idx += qty
                dev_tag = f"-M{m_idx}" if qty == 1 else f"-M{m_idx}..M{m_idx + qty - 1}"
                m_idx += qty
                add_bom("인버터 (VFD)", drv.vendor, drv.part_number, drv.spec, qty, drv.price_krw, drv.lead_days, u_tag, drv_status)
                if load.has_emi_filter:
                    add_bom("노이즈 필터 (EMI)", "Schaffner", f"FN3258-{int(max(7, math.ceil(unit_in)))}A", "3상 인버터 입력 EMI 필터", qty, 85000, 5, f"-Z{u_idx}")
                dc24_a = 0.08 * qty
                heat_w += (unit_kw * 1000.0 * 0.035) * qty

            elif load.load_type == "servo":
                drv, drv_status = pick_drive("servo", unit_kw)
                drv_part = drv.part_number
                u_tag = f"-U{u_idx}" if qty == 1 else f"-U{u_idx}..U{u_idx + qty - 1}"
                u_idx += qty
                dev_tag = f"-M{m_idx}" if qty == 1 else f"-M{m_idx}..M{m_idx + qty - 1}"
                m_idx += qty
                add_bom("서보 드라이브", drv.vendor, drv.part_number, drv.spec, qty, drv.price_krw, drv.lead_days, u_tag, drv_status)
                dc24_a = 0.25 * qty
                heat_w += (unit_kw * 1000.0 * 0.042 + 12.0) * qty

            else:
                mc, mc_status = pick_contactor(unit_in * 1.15)
                mc_part = mc.part_number
                k_tag = f"-K{k_idx}" if qty == 1 else f"-K{k_idx}..K{k_idx + qty - 1}"
                k_idx += qty
                dev_tag = f"-E{e_idx}" if qty == 1 else f"-E{e_idx}..E{e_idx + qty - 1}"
                e_idx += qty
                add_bom("SSR / 접촉기", mc.vendor, mc.part_number, f"히터 제어용 {mc.spec}", qty, mc.price_krw, mc.lead_days, k_tag, mc_status)
                add_bom("온도조절기", "Autonics", "TK4S-14RN", "PID 디지털 온도조절기 48x48", qty, 58000, 2, f"-B{b_idx}")
                b_idx += qty
                dc24_a = 0.10 * qty
                heat_w += mc.heat_w * qty

            total_connected_kw += total_kw
            total_demand_kw += total_kw * load.demand_factor
            bus_scale = (v / sys_v) if ph == sys_p else (v / (sys_v * math.sqrt(3)))
            total_rated_ac_a += (unit_in * qty) * bus_scale
            total_demand_ac_a += (unit_in * qty * load.demand_factor) * bus_scale
            max_starting_delta_a = max(max_starting_delta_a, (start_a - unit_in) * bus_scale)
            total_dc24v_a += dc24_a
            total_heat_w += heat_w

            mac_file, mac_var = resolve_macro(load.load_type)
            results.append(
                LoadCalculationResult(
                    unit_id=load.id,
                    tag=load.tag,
                    name=load.name,
                    load_type=load.load_type,
                    iec_device_tag=dev_tag,
                    eplan_macro=mac_file,
                    eplan_macro_variant=mac_var,
                    rated_current_a=round(unit_in, 2),
                    design_current_a=round(design_a, 2),
                    starting_current_a=round(start_a, 2),
                    wire_sq=wire_sq,
                    wire_awg=sq_to_awg(wire_sq),
                    voltage_drop_pct=vd_pct,
                    breaker_rating_a=brk.rated_a,
                    breaker_icu_ka=brk.icu_ka,
                    breaker_part=brk.part_number,
                    contactor_part=mc_part,
                    drive_part=drv_part,
                    dc24v_current_a=round(dc24_a, 2),
                    heat_loss_w=round(heat_w, 1),
                    formula_trace=formula,
                )
            )

        elif load.load_type == "solenoid_group":
            grp_a = 0.18 * qty
            design_a = grp_a * 1.25
            wire_sq, vd_pct = select_wire_sq(design_a, 24, 0, load.cable_length_m, ambient, max_vdrop_pct=5.0)
            dev_tag = f"-Y{y_idx}..Y{y_idx + qty - 1}"
            y_idx += qty
            cp_a = max(2, int(math.ceil(design_a / 2.0) * 2))
            cp_part = f"CP-2P-{cp_a}A (DC24V)"
            add_bom("서킷 프로텍터 (CP)", vendor, cp_part, f"DC24V 제어회로 보호용 {cp_a}A", 1, 26000, 3, f"-F{q_idx}")
            q_idx += 1
            add_bom("릴레이 보드", "Omron", "G2R-1-SN DC24V", "중간 릴레이 + 소켓 세트 (솔레노이드 구동)", qty, 9500, 2, dev_tag)
            if load.has_surge_suppressor:
                add_bom("서지 억제기", "Phoenix Contact", "PLC-RSC-24DC/21", "플라이백 다이오드 내장 서지 보호", qty, 4500, 2, dev_tag)

            heat_w = qty * 1.2
            total_dc24v_a += grp_a
            total_heat_w += heat_w

            mac_file, mac_var = resolve_macro(load.load_type)
            results.append(
                LoadCalculationResult(
                    unit_id=load.id,
                    tag=load.tag,
                    name=load.name,
                    load_type=load.load_type,
                    iec_device_tag=dev_tag,
                    eplan_macro=mac_file,
                    eplan_macro_variant=mac_var,
                    rated_current_a=round(grp_a, 2),
                    design_current_a=round(design_a, 2),
                    starting_current_a=round(grp_a * 1.1, 2),
                    wire_sq=wire_sq,
                    wire_awg=sq_to_awg(wire_sq),
                    voltage_drop_pct=vd_pct,
                    breaker_rating_a=cp_a,
                    breaker_part=cp_part,
                    dc24v_current_a=round(grp_a, 2),
                    heat_loss_w=round(heat_w, 1),
                    formula_trace=f"I_dc24 = {qty}ea × 0.18A = {grp_a:.2f}A (동시율 100% 기준)",
                )
            )

        elif load.load_type == "sensor_group":
            grp_a = 0.04 * qty
            design_a = grp_a * 1.25
            wire_sq, vd_pct = select_wire_sq(max(design_a, 0.5), 24, 0, load.cable_length_m, ambient, max_vdrop_pct=5.0)
            dev_tag = f"-B{b_idx}..B{b_idx + qty - 1}"
            b_idx += qty
            cp_part = "CP-2P-4A (DC24V)"
            add_bom("서킷 프로텍터 (CP)", vendor, cp_part, "DC24V 센서 전원 보호용 4A", 1, 24000, 3, f"-F{q_idx}")
            q_idx += 1
            add_bom("센서 분배 단자대", "Phoenix Contact", "PT 2.5-3L", "3단 센서용 푸시인 단자대", qty, 3200, 2, dev_tag)

            total_dc24v_a += grp_a
            total_heat_w += qty * 0.25

            mac_file, mac_var = resolve_macro(load.load_type)
            results.append(
                LoadCalculationResult(
                    unit_id=load.id,
                    tag=load.tag,
                    name=load.name,
                    load_type=load.load_type,
                    iec_device_tag=dev_tag,
                    eplan_macro=mac_file,
                    eplan_macro_variant=mac_var,
                    rated_current_a=round(grp_a, 2),
                    design_current_a=round(design_a, 2),
                    starting_current_a=round(grp_a, 2),
                    wire_sq=wire_sq,
                    wire_awg=sq_to_awg(wire_sq),
                    voltage_drop_pct=vd_pct,
                    breaker_rating_a=4,
                    breaker_part=cp_part,
                    dc24v_current_a=round(grp_a, 2),
                    heat_loss_w=round(qty * 0.25, 1),
                    formula_trace=f"I_dc24 = {qty}ea × 0.04A = {grp_a:.2f}A",
                )
            )

        elif load.load_type == "safety_circuit":
            lvl = load.safety_level or "PLd"
            saf_pn, saf_spec, saf_price, saf_lead = SAFETY_RELAY_BY_VENDOR.get(
                vendor, SAFETY_RELAY_BY_VENDOR["LS Electric"]
            )
            dev_tag = f"-K_SAF{saf_idx}"
            saf_idx += 1
            add_bom("안전 릴레이", vendor, saf_pn, f"{saf_spec} ({lvl})", 1, saf_price, saf_lead, dev_tag)
            add_bom("비상정지 스위치", "IDEC", "XW1E-BV402M-R", f"Ø22 2NC 강제개리 비상정지 ({qty}개소)", qty, 28000, 3, f"-S_EMG1..{qty}")
            if lvl in ("PLd", "PLe"):
                mc_saf, mc_saf_status = pick_contactor(max(18.0, total_demand_ac_a * 0.6))
                add_bom("안전 이중화 접촉기", mc_saf.vendor, mc_saf.part_number, f"이중화 차단용 {mc_saf.spec} (EDM 피드백)", 2, mc_saf.price_krw, mc_saf.lead_days, "-K_S1, -K_S2", mc_saf_status)
                heat_w = 8.0 + mc_saf.heat_w * 2
                dc24_a = 0.45
            else:
                heat_w = 6.0
                dc24_a = 0.25

            total_dc24v_a += dc24_a
            total_heat_w += heat_w

            mac_file, mac_var = resolve_macro(load.load_type)
            results.append(
                LoadCalculationResult(
                    unit_id=load.id,
                    tag=load.tag,
                    name=load.name,
                    load_type=load.load_type,
                    iec_device_tag=dev_tag,
                    eplan_macro=mac_file,
                    eplan_macro_variant=mac_var,
                    rated_current_a=round(dc24_a, 2),
                    design_current_a=round(dc24_a * 1.25, 2),
                    starting_current_a=round(dc24_a, 2),
                    wire_sq=0.75,
                    wire_awg=sq_to_awg(0.75),
                    voltage_drop_pct=0.4,
                    breaker_rating_a=4,
                    breaker_part="CP-2P-4A (SAFETY)",
                    contactor_part="Dual Safety MC" if lvl in ("PLd", "PLe") else "Single Safety MC",
                    dc24v_current_a=round(dc24_a, 2),
                    heat_loss_w=round(heat_w, 1),
                    formula_trace=f"ISO 13849-1 {lvl} 기준 이중화 2NC + 안전릴레이 + EDM 피드백",
                )
            )

    plc_cat = PLC_CATALOG.get(project.settings.plc_vendor, PLC_CATALOG["Mitsubishi Electric"])
    for mod in plc_modules:
        cat_item = plc_cat.get(mod.module_type)
        if cat_item:
            add_bom(
                f"PLC ({mod.module_type})",
                cat_item.vendor,
                cat_item.part_number,
                cat_item.spec,
                1,
                cat_item.price_krw,
                cat_item.lead_days,
                f"-A1.{mod.slot}",
            )
            total_dc24v_a += cat_item.dc24v_a
            total_heat_w += cat_item.heat_w

    smps_req_a = max(total_dc24v_a * 1.25, 2.0)
    smps, smps_status = pick_smps(smps_req_a)
    add_bom("SMPS (DC24V)", smps.vendor, smps.part_number, smps.spec, 1, smps.price_krw, smps.lead_days, "-G1", smps_status)
    total_heat_w += (total_dc24v_a * 24.0) * 0.14

    # Step-Down Transformer (-T1) auto-sizing when 220V servo/AC loads exist on >= 380V mains
    tr_part: str | None = None
    tr_kva = 0.0
    if sys_v >= 380:
        lv220_kw = sum(
            l.power_kw * l.quantity
            for l in project.loads
            if l.load_type in ("servo", "motor_dol", "motor_inv", "heater") and l.voltage == 220
        )
        if lv220_kw > 0:
            req_kva = max(1.0, (lv220_kw / 0.85) * 1.25)
            tr = select_control_transformer(req_kva)
            tr_part = tr.part_number
            tr_kva = tr.kva
            add_bom("강압 변압기 (Transformer)", tr.vendor, tr.part_number, tr.spec, 1, tr.price_krw, tr.lead_days, "-T1")
            total_heat_w += tr.heat_w

    smps_ac_a = (smps.output_w / 0.88) / max(sys_v, 220)
    total_demand_ac_a += smps_ac_a
    total_rated_ac_a += smps_ac_a
    main_req_a = max(total_demand_ac_a * 1.25, total_demand_ac_a + max_starting_delta_a * 0.35, 15.0)
    main_brk, main_brk_status = pick_breaker(main_req_a)
    main_wire_sq, _ = select_wire_sq(max(total_demand_ac_a * 1.25, 10.0), sys_v, sys_p, 10.0, ambient, max_vdrop_pct=2.0)

    add_bom("주 차단기 (Main MCCB)", main_brk.vendor, main_brk.part_number, f"주전원 {main_brk.spec}", 1, main_brk.price_krw, main_brk.lead_days, "-Q0", main_brk_status)
    add_bom("서지 보호기 (SPD)", "Phoenix Contact", "VAL-MS 320/3+1", "Type 2 3상 서지 보호기 (40kA)", 1, 165000, 4, "-F0")
    total_heat_w += main_brk.heat_w

    tb_qty = max(20, len(project.loads) * 6)
    add_bom("단자대 (Terminal Block)", "Phoenix Contact", "UT 4 / PT 2.5 MIX", "동력/제어 배선 단자대 + 엔드브라켓", tb_qty, 1800, 2, "-X1, -X2")

    # Select enclosure first so IEC 60890 thermal analysis uses exact enclosure geometry
    complexity_score = sum(l.quantity for l in project.loads if l.load_type in ("motor_dol", "motor_inv", "servo", "heater")) * 2 + len(plc_modules)
    if complexity_score <= 8 and total_connected_kw <= 15:
        enc_w, enc_h, enc_d = 800, 1200, 400
        enc_size, enc_part, enc_price = "800 × 1200 × 400 mm (벽부/자립형)", "Rittal AX 1280.000", 620000
    elif complexity_score <= 18 and total_connected_kw <= 45:
        enc_w, enc_h, enc_d = 1000, 1800, 500
        enc_size, enc_part, enc_price = "1000 × 1800 × 500 mm (자립형 1면)", "Rittal VX 8085.000", 1280000
    else:
        enc_w, enc_h, enc_d = 1600, 2000, 600
        enc_size, enc_part, enc_price = "1600 × 2000 × 600 mm (자립형 2면)", "Rittal VX 8606.000", 2350000

    add_bom("제어반 외함", "Rittal", enc_part, f"IP55 분체도장 외함 {enc_size}", 1, enc_price, 7, "=A1+P1")

    # IEC 60890 Precision Thermal & Cooling Analysis
    thermal_analysis, cooling_sol, cool_bom = _compute_iec60890_thermal(
        enc_w_mm=enc_w,
        enc_h_mm=enc_h,
        enc_d_mm=enc_d,
        install_type=project.settings.enclosure_install_type,
        ambient_c=ambient,
        max_internal_c=project.settings.max_internal_temp_c,
        total_heat_w=total_heat_w,
    )
    add_bom(*cool_bom)
    cooling_m3h = thermal_analysis.required_airflow_m3h if thermal_analysis.required_airflow_m3h > 0 else round((3.1 * total_heat_w) / delta_t, 1)

    # IEC 60909 Short-Circuit Current & Breaker Selectivity Coordination
    ik3_main, ip_peak, ik1_min, r_main, x_main = _compute_iec60909_short_circuit(
        sys_v=sys_v,
        sys_p=sys_p,
        tx_kva=project.settings.supply_transformer_kva,
        tx_z_pct=project.settings.supply_impedance_pct,
        feeder_len_m=project.settings.feeder_length_m,
        feeder_sq=max(main_wire_sq, 10.0),
    )
    main_margin_pct = round(((main_brk.icu_ka - ik3_main) / max(main_brk.icu_ka, 1)) * 100.0, 1)

    load_by_id = {l.id: l for l in project.loads}
    selectivity_checks: list[SelectivityBranchItem] = []
    for res in results:
        if res.load_type not in ("motor_dol", "motor_inv", "servo", "heater"):
            continue
        ld = load_by_id.get(res.unit_id)
        cable_m = ld.cable_length_m if ld else 15.0
        # Branch fault level at load terminals (or breaker outgoing terminals using internal 2m + branch impedance)
        r_br = r_main + 0.0185 * 2.0 / max(res.wire_sq, 1.5)
        x_br = x_main + 0.00008 * 2.0
        z_br = math.sqrt(r_br ** 2 + x_br ** 2)
        ik3_br = round(((1.05 * sys_v) / (math.sqrt(3.0) * max(z_br, 1e-6))) / 1000.0, 2) if sys_p == 3 else round(((1.05 * sys_v) / (2.0 * max(z_br, 1e-6))) / 1000.0, 2)

        ratio = round(main_brk.rated_a / max(res.breaker_rating_a, 1), 2)
        if ratio >= 2.5:
            coord_status = "TOTAL"
            note = f"Total selectivity ({ratio}x ≥ 2.5x; cable {cable_m:.0f}m)"
        elif ratio >= 1.6:
            coord_status = "PARTIAL"
            note = f"Partial selectivity ({ratio}x; magnetic trip coordination recommended)"
        else:
            coord_status = "NON_SELECTIVE"
            note = f"Low ratio ({ratio}x < 1.6x) — risk of simultaneous upstream trip"

        selectivity_checks.append(
            SelectivityBranchItem(
                tag=res.tag,
                name=res.name,
                upstream_part=main_brk.part_number,
                upstream_rating_a=main_brk.rated_a,
                downstream_part=res.breaker_part,
                downstream_rating_a=res.breaker_rating_a,
                downstream_icu_ka=res.breaker_icu_ka,
                ik3_branch_ka=ik3_br,
                selectivity_ratio=ratio,
                coordination_status=coord_status,
                breaking_ok=res.breaker_icu_ka >= ik3_br,
                note=note,
            )
        )

    tot_cnt = sum(1 for s in selectivity_checks if s.coordination_status == "TOTAL")
    part_cnt = sum(1 for s in selectivity_checks if s.coordination_status == "PARTIAL")
    non_cnt = sum(1 for s in selectivity_checks if s.coordination_status == "NON_SELECTIVE")
    sel_summary = f"TOTAL {tot_cnt} / PARTIAL {part_cnt} / NON-SEL {non_cnt}"

    category_order = [
        "주 차단기 (Main MCCB)",
        "강압 변압기 (Transformer)",
        "서지 보호기 (SPD)",
        "차단기 (MCCB)",
        "인버터 (VFD)",
        "서보 드라이브",
        "노이즈 필터 (EMI)",
        "전자접촉기 (MC)",
        "열동계전기 (THR)",
        "SSR / 접촉기",
        "안전 릴레이",
        "안전 이중화 접촉기",
        "비상정지 스위치",
        "SMPS (DC24V)",
        "서킷 프로텍터 (CP)",
    ]

    def sort_key(item: dict) -> tuple[int, str]:
        cat = item["category"]
        idx = category_order.index(cat) if cat in category_order else 99
        return (idx, cat)

    bom_items: list[BomItem] = []
    bom_total = 0
    for idx, raw in enumerate(sorted(bom_acc.values(), key=sort_key), start=1):
        line_total = raw["quantity"] * raw["unit_price_krw"]
        bom_total += line_total
        bom_items.append(
            BomItem(
                line_no=idx,
                category=raw["category"],
                iec_tags=raw["iec_tags"],
                manufacturer=raw["manufacturer"],
                part_number=raw["part_number"],
                spec=raw["spec"],
                quantity=raw["quantity"],
                unit_price_krw=raw["unit_price_krw"],
                total_price_krw=line_total,
                lead_time_days=raw["lead_time_days"],
                lifecycle_status=raw["lifecycle_status"],
            )
        )

    branch_icus = [r.breaker_icu_ka for r in results if r.load_type in ("motor_dol", "motor_inv", "servo", "heater")]
    panel_sccr = min([main_brk.icu_ka, *branch_icus]) if branch_icus else main_brk.icu_ka

    summary = PowerSummary(
        system_voltage_v=sys_v,
        phases=sys_p,
        total_connected_kw=round(total_connected_kw, 2),
        total_demand_kw=round(total_demand_kw, 2),
        total_rated_current_a=round(total_rated_ac_a, 2),
        total_demand_current_a=round(total_demand_ac_a, 2),
        main_breaker_rating_a=main_brk.rated_a,
        main_breaker_icu_ka=main_brk.icu_ka,
        main_breaker_part=main_brk.part_number,
        main_wire_sq=main_wire_sq,
        main_wire_awg=sq_to_awg(main_wire_sq),
        panel_sccr_ka=panel_sccr,
        ik3_main_ka=ik3_main,
        ip_peak_ka=ip_peak,
        ik1_min_ka=ik1_min,
        main_breaking_margin_pct=main_margin_pct,
        selectivity_summary=sel_summary,
        selectivity_checks=selectivity_checks,
        thermal_analysis=thermal_analysis,
        transformer_part=tr_part,
        transformer_kva=tr_kva,
        total_dc24v_current_a=round(total_dc24v_a, 2),
        smps_required_a=round(smps_req_a, 2),
        smps_selected_part=smps.part_number,
        smps_capacity_a=smps.output_a,
        total_heat_loss_w=round(total_heat_w, 1),
        cooling_required_m3h=cooling_m3h,
        cooling_solution=cooling_sol,
        enclosure_size_mm=enc_size,
        enclosure_part=enc_part,
    )

    return summary, results, bom_items, bom_total
