"""Standard Reusable EPLAN Circuit Macro & Functional Unit Library."""

from __future__ import annotations

import uuid

from backend.models import CircuitMacroTemplate, LoadUnit, Project


STANDARD_MACROS: list[CircuitMacroTemplate] = [
    CircuitMacroTemplate(
        macro_id="MACRO-CONV-VFD",
        eplan_file="EPLAN_M_VFD_3P.ema",
        name_en="Conveyor VFD Module (2×1.5kW + EMI)",
        name_ko="컨베이어 인버터 표준 모듈 (2×1.5kW + EMI)",
        category="Power Drive",
        description_en="2x 3-phase VFD conveyor motors with EMI input filter, MCCB, and Run/Fault/Speed PLC I/O.",
        description_ko="3상 인버터 컨베이어 2대 + 입력 EMI 필터 + 분기 MCCB + 운전/이상/속도지령 I/O 세트",
        loads=[
            {"tag": "CONV_STD", "name": "Standard VFD Conveyor", "load_type": "motor_inv", "power_kw": 1.5, "quantity": 2, "cable_length_m": 20.0, "has_emi_filter": True}
        ],
    ),
    CircuitMacroTemplate(
        macro_id="MACRO-SERVO-2AX",
        eplan_file="EPLAN_M_SERVO_AX.ema",
        name_en="Dual-Axis AC Servo Transfer Cell (2×750W)",
        name_ko="2축 AC 서보 이송 모듈 (2×750W)",
        category="Motion",
        description_en="2x 750W AC servo drives with 24V holding brake budget, Ready/Alarm/Home I/O, and 220V step-down supply.",
        description_ko="750W AC 서보 2축 + 24V 브레이크 전류 반영 + Ready/Alarm/Home I/O + 220V 강압전원 자동 연계",
        loads=[
            {"tag": "SRV_CELL", "name": "Transfer Servo Axis", "load_type": "servo", "power_kw": 0.75, "quantity": 2, "voltage": 220, "phases": 1, "cable_length_m": 15.0}
        ],
    ),
    CircuitMacroTemplate(
        macro_id="MACRO-HEATER-PID",
        eplan_file="EPLAN_M_HEATER_PID.ema",
        name_en="Process PID Heater Zone (3kW + OTP)",
        name_ko="공정 PID 히터 제어 존 (3kW + 과승온)",
        category="Thermal Process",
        description_en="3kW resistive heater zone with SSR/MC, PID temperature controller, 4-20mA AI, and OTP interlock DI.",
        description_ko="3kW 3상 히터 + SSR/MC + PID 온도조절기 + 4-20mA 온도 AI + 과승온(OTP) 인터록 DI",
        loads=[
            {"tag": "HTR_ZONE", "name": "Process PID Heater Zone", "load_type": "heater", "power_kw": 3.0, "quantity": 1, "power_factor": 1.0, "efficiency": 1.0, "cable_length_m": 12.0}
        ],
    ),
    CircuitMacroTemplate(
        macro_id="MACRO-PUMP-DOL",
        eplan_file="EPLAN_M_DOL_3P.ema",
        name_en="3P DOL Pump / Blower Starter (2.2kW)",
        name_ko="3상 직입 펌프/블로워 기동 모듈 (2.2kW)",
        category="Power Drive",
        description_en="Direct-on-line motor starter with MCCB, magnetic contactor, thermal overload relay, and Aux/Trip I/O.",
        description_ko="MCCB + 전자접촉기(MC) + 열동계전기(THR) + 운전응답/과부하트립 I/O 표준 직입 회로",
        loads=[
            {"tag": "PUMP_DOL", "name": "Utility Pump DOL Motor", "load_type": "motor_dol", "power_kw": 2.2, "quantity": 1, "cable_length_m": 18.0}
        ],
    ),
    CircuitMacroTemplate(
        macro_id="MACRO-PNEU-IO",
        eplan_file="EPLAN_M_SOL_24VDC.ema",
        name_en="Pneumatic Manifold + Sensor Kit (8V / 16S)",
        name_ko="공압 밸브(8점) + 감지센서(16점) 표준 키트",
        category="Pneumatics & I/O",
        description_en="8x 24VDC solenoid valves with flyback diode surge suppressors + 16x proximity/photo sensors + CP protection.",
        description_ko="DC24V 솔레노이드 8개(플라이백 서지억제 포함) + 근접/광전센서 16점 + 제어용 CP 보호회로",
        loads=[
            {"tag": "PNEU_SOL", "name": "Pneumatic Valve Manifold", "load_type": "solenoid_group", "power_kw": 0.0, "quantity": 8, "voltage": 24, "phases": 0, "has_surge_suppressor": True},
            {"tag": "FIELD_SEN", "name": "Cylinder Reed & Prox Sensors", "load_type": "sensor_group", "power_kw": 0.0, "quantity": 16, "voltage": 24, "phases": 0},
        ],
    ),
    CircuitMacroTemplate(
        macro_id="MACRO-SAFETY-PLE",
        eplan_file="EPLAN_M_SAFETY_DUAL.ema",
        name_en="ISO 13849-1 PLe Redundant Safety Module",
        name_ko="ISO 13849-1 PLe 이중화 안전 회로 모듈",
        category="Functional Safety",
        description_en="Dual-channel 2NC E-Stop loop (2 stations), Cat.4 Safety Relay, Dual Safety Contactors with EDM feedback.",
        description_ko="2NC 이중화 비상정지(2개소) + Cat.4 안전릴레이 + 이중화 안전접촉기 + EDM 피드백 루프",
        loads=[
            {"tag": "SAFETY_PLE", "name": "Redundant E-Stop & Door Safety", "load_type": "safety_circuit", "power_kw": 0.0, "quantity": 2, "voltage": 24, "phases": 0, "safety_level": "PLe"}
        ],
    ),
]


def instantiate_macro_units(macro_id: str, project: Project) -> list[LoadUnit]:
    """Instantiate unique LoadUnits from a standard macro adapted to the project's primary power system."""
    macro = next((m for m in STANDARD_MACROS if m.macro_id == macro_id), None)
    if not macro:
        return []

    sys_v = 480 if "480" in project.settings.power_system else (440 if "440" in project.settings.power_system else (220 if "220" in project.settings.power_system else 380))
    sys_p = 1 if project.settings.power_system.startswith("1P") else 3
    existing_tags = {l.tag.upper() for l in project.loads}

    created: list[LoadUnit] = []
    for raw in macro.loads:
        base_tag = raw["tag"]
        tag = base_tag
        seq = 2
        while tag.upper() in existing_tags:
            tag = f"{base_tag}_{seq:02d}"
            seq += 1
        existing_tags.add(tag.upper())

        data = dict(raw)
        data["id"] = f"mac_{uuid.uuid4().hex[:6]}"
        data["tag"] = tag
        if data["load_type"] in ("motor_dol", "motor_inv", "heater"):
            data.setdefault("voltage", sys_v)
            data.setdefault("phases", sys_p)
        created.append(LoadUnit(**data))
    return created


def generate_eplan_ema_xml(
    project: Project,
    calcs: list,
    custom_macros: list | None = None,
    target_macro_file: str | None = None,
) -> tuple[str, str]:
    """Generate an EPLAN Electric P8 Window Macro XML (.ema) with Placeholder Object ValueSets.

    Returns (filename, xml_content).
    """
    import xml.etree.ElementTree as ET
    from xml.dom import minidom

    custom_by_file = {m.eplan_file: m for m in (custom_macros or [])}
    selected_calcs = [c for c in calcs if not target_macro_file or c.eplan_macro == target_macro_file]
    if not selected_calcs:
        selected_calcs = calcs[:1]

    macro_name = target_macro_file or (selected_calcs[0].eplan_macro if selected_calcs else "EPLAN_M_PANEL.ema")
    cm = custom_by_file.get(macro_name)
    variant = cm.variant if cm else (selected_calcs[0].eplan_macro_variant if selected_calcs else "A")
    rep_type = cm.representation_type if cm else "Multi-line"

    root = ET.Element(
        "EplanPxfRoot",
        {
            "Name": project.name,
            "Type": "WindowMacro",
            "Version": "2024.0",
            "Generator": "PanelCraft AI SSOT",
        },
    )
    meta = ET.SubElement(root, "MacroMetadata")
    ET.SubElement(meta, "MacroFile").text = macro_name
    ET.SubElement(meta, "Variant").text = variant
    ET.SubElement(meta, "RepresentationType").text = rep_type
    ET.SubElement(meta, "Standard").text = project.settings.standard_profile
    ET.SubElement(meta, "PowerSystem").text = project.settings.power_system

    # EPLAN Placeholder Object (O117) with resolved ValueSets for each matching circuit
    placeholder_obj = ET.SubElement(
        root,
        "O117",
        {
            "MacroName": macro_name,
            "Variant": variant,
            "RepresentationType": rep_type,
        },
    )
    vars_el = ET.SubElement(placeholder_obj, "PlaceholderVariables")
    default_vars = (
        cm.placeholder_vars
        if (cm and cm.placeholder_vars)
        else {
            "<DeviceTag>": "{iec_device_tag}",
            "<MCCB_Part>": "{breaker_part}",
            "<MCCB_Rating_A>": "{breaker_rating_a}",
            "<Drive_or_MC>": "{drive_or_mc}",
            "<Wire_SQ>": "{wire_sq}",
            "<Wire_AWG>": "{wire_awg}",
        }
    )
    for k, v in default_vars.items():
        ET.SubElement(vars_el, "Variable", {"Name": k, "Binding": v})

    value_sets = ET.SubElement(placeholder_obj, "ValueSets")
    for idx, c in enumerate(selected_calcs, start=1):
        vs = ET.SubElement(value_sets, "ValueSet", {"Name": f"{c.tag}_SET{idx}", "UnitTag": c.tag})
        ctx = {
            "tag": c.tag,
            "name": c.name,
            "iec_device_tag": c.iec_device_tag,
            "breaker_part": c.breaker_part,
            "breaker_rating_a": str(c.breaker_rating_a),
            "breaker_icu_ka": str(c.breaker_icu_ka),
            "drive_or_mc": c.drive_part or c.contactor_part or "-",
            "wire_sq": str(c.wire_sq),
            "wire_awg": c.wire_awg,
            "rated_current_a": str(c.rated_current_a),
        }
        for var_name, tmpl in default_vars.items():
            resolved = tmpl
            for ck, cv in ctx.items():
                resolved = resolved.replace("{" + ck + "}", cv)
            ET.SubElement(vs, "Value", {"Variable": var_name}).text = resolved

    pretty = minidom.parseString(ET.tostring(root, encoding="utf-8")).toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")
    safe_fname = macro_name.replace("\\", "/").split("/")[-1]
    if not safe_fname.lower().endswith(".ema"):
        safe_fname += ".ema"
    return safe_fname, pretty

