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
    LoadCalculationResult,
    PlcModule,
    PowerSummary,
    Project,
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


def compute_electrical_and_bom(
    project: Project,
    plc_modules: list[PlcModule],
    custom_catalog: list[CustomCatalogItem] | None = None,
) -> tuple[PowerSummary, list[LoadCalculationResult], list[BomItem], int]:
    """Run deterministic electrical formulas, select components, and compile SSOT BOM."""

    custom_list = custom_catalog or []
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

            results.append(
                LoadCalculationResult(
                    unit_id=load.id,
                    tag=load.tag,
                    name=load.name,
                    load_type=load.load_type,
                    iec_device_tag=dev_tag,
                    eplan_macro=EPLAN_MACRO_MAP.get(load.load_type, "EPLAN_M_GENERIC.ema"),
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

            results.append(
                LoadCalculationResult(
                    unit_id=load.id,
                    tag=load.tag,
                    name=load.name,
                    load_type=load.load_type,
                    iec_device_tag=dev_tag,
                    rated_current_a=round(grp_a, 2),
                    design_current_a=round(design_a, 2),
                    starting_current_a=round(grp_a * 1.1, 2),
                    wire_sq=wire_sq,
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

            results.append(
                LoadCalculationResult(
                    unit_id=load.id,
                    tag=load.tag,
                    name=load.name,
                    load_type=load.load_type,
                    iec_device_tag=dev_tag,
                    rated_current_a=round(grp_a, 2),
                    design_current_a=round(design_a, 2),
                    starting_current_a=round(grp_a, 2),
                    wire_sq=wire_sq,
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

            results.append(
                LoadCalculationResult(
                    unit_id=load.id,
                    tag=load.tag,
                    name=load.name,
                    load_type=load.load_type,
                    iec_device_tag=dev_tag,
                    rated_current_a=round(dc24_a, 2),
                    design_current_a=round(dc24_a * 1.25, 2),
                    starting_current_a=round(dc24_a, 2),
                    wire_sq=0.75,
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

    cooling_m3h = round((3.1 * total_heat_w) / delta_t, 1)
    if total_heat_w <= 120:
        cooling_sol = "자연 대류 방열 (루버 벤트)"
        add_bom("방열 액세서리", "Rittal", "SK 3237.200", "필터 루버 벤트 세트", 2, 32000, 3, "-E_VENT")
    elif total_heat_w <= 650:
        cooling_sol = f"강제 필터 팬 (필요풍량 {cooling_m3h} m³/h → 180 m³/h 팬 적용)"
        add_bom("냉각 팬", "Rittal", "SK 3240.100", "TopTherm 필터팬 180 m³/h + 배기필터", 1, 185000, 4, "-M_FAN1")
    else:
        cooling_sol = f"판넬 쿨러 (제어반 에어컨 1000W급, 발열 {total_heat_w:.0f}W)"
        add_bom("판넬 쿨러", "Rittal", "SK 3304.500", "Blue e+ 제어반 냉각기 1.0kW", 1, 1650000, 10, "-A_COOL1")

    complexity_score = sum(l.quantity for l in project.loads if l.load_type in ("motor_dol", "motor_inv", "servo", "heater")) * 2 + len(plc_modules)
    if complexity_score <= 8 and total_connected_kw <= 15:
        enc_size, enc_part, enc_price = "800 × 1200 × 400 mm (벽부/자립형)", "Rittal AX 1280.000", 620000
    elif complexity_score <= 18 and total_connected_kw <= 45:
        enc_size, enc_part, enc_price = "1000 × 1800 × 500 mm (자립형 1면)", "Rittal VX 8085.000", 1280000
    else:
        enc_size, enc_part, enc_price = "1600 × 2000 × 600 mm (자립형 2면)", "Rittal VX 8606.000", 2350000

    add_bom("제어반 외함", "Rittal", enc_part, f"IP55 분체도장 외함 {enc_size}", 1, enc_price, 7, "=A1+P1")

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
