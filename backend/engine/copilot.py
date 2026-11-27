"""Hybrid AI Copilot: External/Local LLM + Deterministic RFP/NL Parser & IEC 61131-3 Interlock Code Generator."""

from __future__ import annotations

import re
import uuid

from backend.engine.llm_gateway import call_llm_json
from backend.models import (
    ComputedDesign,
    CopilotParseRequest,
    CopilotParseResponse,
    InterlockResponse,
    InterlockRule,
    LlmConfig,
    LoadUnit,
    Project,
    ProjectSettings,
)


def parse_nl_spec(req: CopilotParseRequest, llm_cfg: LlmConfig | None = None) -> CopilotParseResponse:
    """Parse RFP/NL specification using configured External/Local LLM with deterministic fallback."""
    if llm_cfg and llm_cfg.provider != "builtin":
        llm_res = _try_llm_parse_spec(req, llm_cfg)
        if llm_res is not None:
            return llm_res
    return _deterministic_parse_nl_spec(req)


def _try_llm_parse_spec(req: CopilotParseRequest, cfg: LlmConfig) -> CopilotParseResponse | None:
    system_prompt = (
        "You are a senior industrial control panel electrical engineer. "
        "Extract equipment loads from the user's RFP or specification into strict JSON: "
        '{"power_system": "3P_380V_60Hz|3P_440V_60Hz|3P_220V_60Hz|1P_220V_60Hz", '
        '"preferred_vendor": "LS Electric|Schneider Electric|Siemens|Mitsubishi Electric", '
        '"plc_vendor": "Mitsubishi Electric|LS Electric|Siemens", '
        '"notes": ["string"], '
        '"loads": [{"tag": "CONV_01", "name": "string", '
        '"load_type": "motor_dol|motor_inv|servo|heater|solenoid_group|sensor_group|safety_circuit", '
        '"power_kw": 1.5, "quantity": 1, "voltage": 380, "phases": 3, "safety_level": "PLd"}]}'
    )
    data, engine_label = call_llm_json(cfg, system_prompt, req.prompt[:6000])
    if not data or not isinstance(data.get("loads"), list) or not data["loads"]:
        return None

    loads: list[LoadUnit] = []
    for idx, item in enumerate(data["loads"], start=1):
        try:
            ltype = item.get("load_type", "motor_inv")
            if ltype not in ("motor_dol", "motor_inv", "servo", "heater", "solenoid_group", "sensor_group", "safety_circuit"):
                continue
            loads.append(
                LoadUnit(
                    id=f"llm_{uuid.uuid4().hex[:6]}",
                    tag=str(item.get("tag") or f"UNIT_{idx:02d}")[:18],
                    name=str(item.get("name") or f"부하 #{idx}")[:48],
                    load_type=ltype,
                    power_kw=max(0.0, float(item.get("power_kw") or 0.0)),
                    quantity=max(1, int(item.get("quantity") or 1)),
                    voltage=int(item.get("voltage") or (24 if ltype in ("solenoid_group", "sensor_group", "safety_circuit") else 380)),
                    phases=int(item.get("phases") if item.get("phases") is not None else (0 if ltype in ("solenoid_group", "sensor_group", "safety_circuit") else 3)),
                    safety_level=item.get("safety_level") if ltype == "safety_circuit" else None,
                )
            )
        except Exception:
            continue

    if not loads:
        return None

    power_sys = data.get("power_system", "3P_380V_60Hz")
    if power_sys not in ("3P_380V_60Hz", "3P_440V_60Hz", "3P_220V_60Hz", "1P_220V_60Hz"):
        power_sys = "3P_380V_60Hz"
    pref_vendor = req.preferred_vendor or data.get("preferred_vendor", "LS Electric")
    if pref_vendor not in ("LS Electric", "Schneider Electric", "Siemens", "Mitsubishi Electric"):
        pref_vendor = "LS Electric"
    plc_vendor = req.plc_vendor or data.get("plc_vendor", "Mitsubishi Electric")
    if plc_vendor not in ("Mitsubishi Electric", "LS Electric", "Siemens"):
        plc_vendor = "Mitsubishi Electric"

    project = Project(
        id=f"PRJ-{uuid.uuid4().hex[:6].upper()}",
        name=req.project_name or "LLM RFP 분석 제어반 프로젝트",
        client=f"AI Copilot ({engine_label})",
        description=f"원본 사양: {req.prompt[:180]}",
        settings=ProjectSettings(
            power_system=power_sys,
            preferred_vendor=pref_vendor,
            plc_vendor=plc_vendor,
        ),
        loads=loads,
    )
    notes = [str(n) for n in data.get("notes", [])] or [f"{engine_label}으로 {len(loads)}개 기능 유닛 추출 완료"]
    return CopilotParseResponse(
        suggested_project=project,
        extracted_notes=notes,
        confidence=0.93,
        engine_used=engine_label,
    )


def _deterministic_parse_nl_spec(req: CopilotParseRequest) -> CopilotParseResponse:
    """Deterministic Korean/English RFP & NL specification parser."""
    text = req.prompt.strip()
    lower = text.lower()
    notes: list[str] = []
    loads: list[LoadUnit] = []

    power_sys = "3P_380V_60Hz"
    sys_v = 380
    sys_p = 3
    if "480v" in lower or "480 v" in lower or "ul 508" in lower or "ul508" in lower:
        power_sys, sys_v, sys_p = "3P_480V_60Hz", 480, 3
        notes.append("Power System detected: 3P 480V 60Hz (UL 508A)")
    elif "440v" in lower or "440 v" in lower:
        power_sys, sys_v, sys_p = "3P_440V_60Hz", 440, 3
        notes.append("Power System detected: 3P 440V 60Hz")
    elif ("단상" in text or "1p" in lower) and "220" in lower:
        power_sys, sys_v, sys_p = "1P_220V_60Hz", 220, 1
        notes.append("Power System detected: 1P 220V 60Hz")
    elif "220v" in lower and ("3상" in text or "3p" in lower):
        power_sys, sys_v, sys_p = "3P_220V_60Hz", 220, 3
        notes.append("Power System detected: 3P 220V 60Hz")
    else:
        notes.append("Power System default/detected: 3P 380V 60Hz")

    preferred_vendor = req.preferred_vendor or "LS Electric"
    plc_vendor = req.plc_vendor or "Mitsubishi Electric"
    if not req.preferred_vendor:
        if "abb" in lower:
            preferred_vendor = "ABB"
        elif "후지" in text or "fuji" in lower:
            preferred_vendor = "Fuji Electric"
        elif "오므론" in text or "omron" in lower:
            preferred_vendor = "Omron"
        elif "슈나이더" in text or "schneider" in lower:
            preferred_vendor = "Schneider Electric"
        elif "지멘스" in text or "siemens" in lower:
            preferred_vendor = "Siemens"
        elif "미쓰비시" in text or "mitsubishi" in lower:
            preferred_vendor = "Mitsubishi Electric"
    if not req.plc_vendor:
        if "rockwell" in lower or "allen" in lower or "ab plc" in lower or "controllogix" in lower or "로크웰" in text:
            plc_vendor = "Rockwell Automation"
        elif "beckhoff" in lower or "twincat" in lower or "백호프" in text:
            plc_vendor = "Beckhoff"
        elif "omron" in lower or "sysmac" in lower or "오므론" in text:
            plc_vendor = "Omron"
        elif "지멘스" in text or "s7" in lower or "siemens" in lower:
            plc_vendor = "Siemens"
        elif "ls" in lower or "xgt" in lower or "산전" in text:
            plc_vendor = "LS Electric"

    def _parse_power_kw(clause: str, default_kw: float) -> float:
        m_kw = re.search(r"(\d+(?:\.\d+)?)\s*kw", clause, re.IGNORECASE)
        if m_kw:
            return float(m_kw.group(1))
        m_w = re.search(r"(\d+(?:\.\d+)?)\s*w\b", clause, re.IGNORECASE)
        if m_w:
            return round(float(m_w.group(1)) / 1000.0, 3)
        return default_kw

    def _parse_qty(clause: str, default_qty: int = 1) -> int:
        m = re.search(r"(\d+)\s*(?:대|축|개소|개|점|ea|units?|axes?)", clause, re.IGNORECASE)
        if m:
            return max(1, int(m.group(1)))
        return default_qty

    clauses = [c.strip() for c in re.split(r"[,;\n•·]+", text) if c.strip()]
    idx_counters = {"inv": 1, "dol": 1, "srv": 1, "htr": 1, "sol": 1, "sen": 1}
    safety_added = False

    for clause in clauses:
        cl = clause.lower()
        if any(k in cl for k in ["비상정지", "안전", "e-stop", "estop", "safety", "도어", "emo"]):
            qty = _parse_qty(clause, 2)
            lvl = "PLe" if "ple" in cl else ("PLc" if "plc" in cl and "pld" not in cl else "PLd")
            loads.append(
                LoadUnit(
                    id=f"u_{uuid.uuid4().hex[:6]}",
                    tag="SAFETY_01",
                    name="비상정지 및 안전 인터록 회로",
                    load_type="safety_circuit",
                    power_kw=0.0,
                    quantity=qty,
                    voltage=24,
                    phases=0,
                    safety_level=lvl,
                )
            )
            safety_added = True
            notes.append(f"안전 회로 추출: 비상정지 {qty}개소 ({lvl} 등급)")

        elif any(k in cl for k in ["인버터", "컨베이어", "vfd", "inverter", "conveyor"]):
            kw = _parse_power_kw(clause, 1.5)
            qty = _parse_qty(clause, 2)
            n = idx_counters["inv"]
            idx_counters["inv"] += 1
            label = "컨베이어 인버터 모터" if ("컨베이어" in clause or "conveyor" in cl) else f"인버터 구동 모터 #{n}"
            loads.append(
                LoadUnit(
                    id=f"u_{uuid.uuid4().hex[:6]}",
                    tag=f"INV_{n:02d}",
                    name=label,
                    load_type="motor_inv",
                    power_kw=kw,
                    quantity=qty,
                    voltage=sys_v,
                    phases=sys_p,
                    cable_length_m=20.0,
                )
            )
            notes.append(f"인버터 부하 추출: {label} {kw}kW × {qty}대")

        elif any(k in cl for k in ["서보", "servo", "로봇", "리프트", "갠트리", "축"]):
            kw = _parse_power_kw(clause, 0.75)
            qty = _parse_qty(clause, 2)
            n = idx_counters["srv"]
            idx_counters["srv"] += 1
            label = "리프트 서보 축" if "리프트" in clause else ("갠트리 서보 축" if "갠트리" in clause else f"AC 서보 구동 축 #{n}")
            loads.append(
                LoadUnit(
                    id=f"u_{uuid.uuid4().hex[:6]}",
                    tag=f"SRV_{n:02d}",
                    name=label,
                    load_type="servo",
                    power_kw=kw,
                    quantity=qty,
                    voltage=220,
                    phases=3 if kw >= 1.5 else 1,
                    cable_length_m=15.0,
                )
            )
            notes.append(f"서보 부하 추출: {label} {kw}kW × {qty}축")

        elif any(k in cl for k in ["히터", "건조", "예열", "heater", "oven"]):
            kw = _parse_power_kw(clause, 3.0)
            qty = _parse_qty(clause, 1)
            n = idx_counters["htr"]
            idx_counters["htr"] += 1
            loads.append(
                LoadUnit(
                    id=f"u_{uuid.uuid4().hex[:6]}",
                    tag=f"HTR_{n:02d}",
                    name=f"공정 히터 존 #{n}",
                    load_type="heater",
                    power_kw=kw,
                    quantity=qty,
                    voltage=sys_v,
                    phases=sys_p,
                    power_factor=1.0,
                    efficiency=1.0,
                )
            )
            notes.append(f"히터 부하 추출: {kw}kW × {qty}대")

        elif any(k in cl for k in ["모터", "펌프", "블로워", "팬", "motor", "pump", "blower"]):
            kw = _parse_power_kw(clause, 2.2)
            qty = _parse_qty(clause, 1)
            n = idx_counters["dol"]
            idx_counters["dol"] += 1
            label = "순환 펌프 모터" if ("펌프" in clause or "pump" in cl) else ("집진 블로워 모터" if ("블로워" in clause or "blower" in cl) else f"직입 구동 모터 #{n}")
            loads.append(
                LoadUnit(
                    id=f"u_{uuid.uuid4().hex[:6]}",
                    tag=f"MTR_{n:02d}",
                    name=label,
                    load_type="motor_dol",
                    power_kw=kw,
                    quantity=qty,
                    voltage=sys_v,
                    phases=sys_p,
                    cable_length_m=18.0,
                )
            )
            notes.append(f"직입 모터 추출: {label} {kw}kW × {qty}대")

        elif any(k in cl for k in ["솔레노이드", "밸브", "실린더", "solenoid", "valve"]):
            qty = _parse_qty(clause, 8)
            n = idx_counters["sol"]
            idx_counters["sol"] += 1
            loads.append(
                LoadUnit(
                    id=f"u_{uuid.uuid4().hex[:6]}",
                    tag=f"SOL_{n:02d}",
                    name="공압 실린더 솔레노이드 그룹",
                    load_type="solenoid_group",
                    power_kw=0.0,
                    quantity=qty,
                    voltage=24,
                    phases=0,
                )
            )
            notes.append(f"솔레노이드 밸브 그룹 추출: {qty}개 (DC 24V)")

        elif any(k in cl for k in ["센서", "근접", "광전", "sensor", "limit"]):
            qty = _parse_qty(clause, 16)
            n = idx_counters["sen"]
            idx_counters["sen"] += 1
            loads.append(
                LoadUnit(
                    id=f"u_{uuid.uuid4().hex[:6]}",
                    tag=f"SEN_{n:02d}",
                    name="현장 감지 센서 그룹",
                    load_type="sensor_group",
                    power_kw=0.0,
                    quantity=qty,
                    voltage=24,
                    phases=0,
                )
            )
            notes.append(f"센서 그룹 추출: {qty}점 (DC 24V)")

    if not loads:
        loads = [
            LoadUnit(id="u_def1", tag="CONV_01", name="메인 컨베이어 인버터 모터", load_type="motor_inv", power_kw=1.5, quantity=2, voltage=sys_v, phases=sys_p),
            LoadUnit(id="u_def2", tag="SRV_01", name="이송 서보 축", load_type="servo", power_kw=0.75, quantity=2, voltage=220, phases=1),
            LoadUnit(id="u_def3", tag="SOL_01", name="공압 솔레노이드 밸브", load_type="solenoid_group", quantity=8, voltage=24, phases=0),
            LoadUnit(id="u_def4", tag="SEN_01", name="근접/광전 센서", load_type="sensor_group", quantity=12, voltage=24, phases=0),
        ]
        notes.append("명시적 부하 항목이 부족하여 표준 FA 자동화 기본 구성을 생성했습니다.")

    if not safety_added and any(l.load_type in ("motor_dol", "motor_inv", "servo") for l in loads):
        loads.append(
            LoadUnit(
                id=f"u_{uuid.uuid4().hex[:6]}",
                tag="SAFETY_01",
                name="비상정지 안전 회로 (자동 권고 추가)",
                load_type="safety_circuit",
                quantity=2,
                voltage=24,
                phases=0,
                safety_level="PLd",
            )
        )
        notes.append("IEC 60204-1 준수를 위해 비상정지 안전 회로(PLd, 2개소)를 자동 추가했습니다.")

    project = Project(
        id=f"PRJ-{uuid.uuid4().hex[:6].upper()}",
        tenant_id=req.tenant_id,
        name=req.project_name or "AI Auto-Generated Control Panel",
        client="AI Copilot Draft",
        description=f"Spec: {text[:160]}",
        settings=ProjectSettings(
            standard_profile="UL 508A" if power_sys == "3P_480V_60Hz" else "IEC 60204-1",
            power_system=power_sys,  # type: ignore[arg-type]
            preferred_vendor=preferred_vendor,
            plc_vendor=plc_vendor,
        ),
        loads=loads,
    )

    confidence = min(0.96, 0.72 + 0.05 * len(loads))
    return CopilotParseResponse(
        suggested_project=project,
        extracted_notes=notes,
        confidence=round(confidence, 2),
        engine_used="Offline Deterministic Parser",
    )


# ---------------------------------------------------------------------------
# Natural-Language -> IEC 61131-3 ST Interlock & Alarm Generator
# ---------------------------------------------------------------------------

def generate_interlock_code(
    design: ComputedDesign,
    requirement_text: str,
    llm_cfg: LlmConfig | None = None,
) -> InterlockResponse:
    """Generate IEC 61131-3 ST Interlock & Alarm FB grounded in active project's SSOT I/O."""
    if llm_cfg and llm_cfg.provider != "builtin":
        io_summary = "\n".join(
            f"- {ch.io_type} {ch.plc_address} ({ch.unit_tag}): {ch.signal_name}"
            for ch in design.plc_channels[:45]
        )
        sys_prompt = (
            "You are a senior PLC automation engineer specializing in IEC 61131-3 Structured Text and ISO 13849-1 safety interlocks. "
            "Given the project's actual PLC I/O map and the user's natural-language interlock requirements, return strict JSON: "
            '{"st_code": "IEC 61131-3 ST FUNCTION_BLOCK FB_InterlockAndAlarm ...", '
            '"alarms": [{"alarm_code": "ALM_001", "condition": "string", "action": "string", "reset_policy": "Manual Reset", "related_io": ["X000"]}], '
            '"notes": ["string"]}. '
            "Use ONLY real PLC addresses from the provided I/O table."
        )
        user_prompt = f"Project: {design.project.name} ({design.project.settings.plc_vendor})\nI/O Table:\n{io_summary}\n\nInterlock Requirements:\n{requirement_text}"
        data, engine_label = call_llm_json(llm_cfg, sys_prompt, user_prompt)
        if data and data.get("st_code"):
            alarms = []
            for a in data.get("alarms", []):
                try:
                    alarms.append(
                        InterlockRule(
                            alarm_code=str(a.get("alarm_code", "ALM")),
                            condition=str(a.get("condition", "")),
                            action=str(a.get("action", "")),
                            reset_policy=str(a.get("reset_policy", "수동 리셋 (FAULT_RESET_PB)")),
                            related_io=[str(x) for x in a.get("related_io", [])],
                        )
                    )
                except Exception:
                    continue
            return InterlockResponse(
                st_code=str(data["st_code"]),
                alarms=alarms,
                engine_used=engine_label,
                notes=[str(n) for n in data.get("notes", [])] or [f"{engine_label} 기반 인터록 코드 생성 완료"],
            )

    return _deterministic_interlock_generator(design, requirement_text)


def _deterministic_interlock_generator(design: ComputedDesign, requirement_text: str) -> InterlockResponse:
    """Grounded SSOT interlock & alarm synthesizer matching project PLC channels."""
    text = requirement_text.strip()
    lower = text.lower()
    channels = design.plc_channels

    def find_ch(io_type: str, keyword: str) -> list[str]:
        return [
            f"{ch.plc_address} ({ch.unit_tag})"
            for ch in channels
            if ch.io_type == io_type and keyword.lower() in ch.signal_name.lower()
        ]

    safety_di = find_ch("DI", "SAFETY_OK")
    inv_faults = find_ch("DI", "인버터 이상")
    srv_alarms = find_ch("DI", "서보 알람")
    srv_homes = find_ch("DI", "원점")
    htr_otps = find_ch("DI", "과승온")
    thr_trips = find_ch("DI", "과부하")
    drive_outs = [
        f"{ch.plc_address} ({ch.unit_tag})"
        for ch in channels
        if ch.io_type == "DO" and any(k in ch.signal_name for k in ("기동 지령", "정회전 지령", "서보 온", "히터 출력"))
    ]

    alarms: list[InterlockRule] = []
    st_body: list[str] = []
    notes: list[str] = []

    # Rule 1: E-Stop / Safety Interlock (always generated if safety or requested)
    if safety_di or any(k in lower for k in ["비상정지", "도어", "안전", "e-stop", "safety"]):
        addr = safety_di[0].split()[0] if safety_di else "bSafetyRelayOK"
        alarms.append(
            InterlockRule(
                alarm_code="ALM_001",
                condition=f"비상정지 또는 안전 도어 인터록 해제 (NOT {addr})",
                action="모든 동력/서보/히터 출력 즉시 차단 및 적색 램프/부저 점등 (Category 0/1 Stop)",
                reset_policy="위험원 해제 후 안전 릴레이 리셋 → FAULT_RESET_PB 상승엣지",
                related_io=safety_di[:2] + drive_outs[:3],
            )
        )
        st_body.extend([
            "(* [ALM_001] 비상정지 / 안전 도어 인터록 — ISO 13849-1 *)",
            "IF NOT iSafetyOK THEN",
            "    qAlm_SafetyTrip := TRUE;",
            "    qAllDriveEnable := FALSE;",
            "    qTowerRed       := TRUE;",
            "    qBuzzer         := TRUE;",
            "END_IF;",
            "",
        ])

    # Rule 2: Inverter / Motor Overload Interlock
    if inv_faults or thr_trips or any(k in lower for k in ["인버터", "컨베이어", "과부하", "fault", "motor"]):
        related = (inv_faults + thr_trips)[:4]
        alarms.append(
            InterlockRule(
                alarm_code="ALM_002",
                condition="인버터 FAULT 또는 모터 열동계전기(THR) 트립 감지",
                action="연동 컨베이어 라인 정지(물류 정체 방지) 및 해당 인버터 운전 지령 해제",
                reset_policy="원인 점검 후 FAULT_RESET_PB 1초 유지 (인버터 RST 출력 펄스)",
                related_io=related,
            )
        )
        st_body.extend([
            "(* [ALM_002] 인버터 / 모터 과부하 트립 인터록 *)",
            "IF iInverterFault OR iMotorOverload THEN",
            "    qAlm_DriveFault  := TRUE;",
            "    qConveyorRunCmd  := FALSE;",
            "END_IF;",
            "",
        ])

    # Rule 3: Servo Home & Ready Precondition
    if srv_alarms or srv_homes or any(k in lower for k in ["서보", "원점", "리프트", "servo", "home"]):
        alarms.append(
            InterlockRule(
                alarm_code="ALM_003",
                condition="서보 알람 발생 또는 서보 원점(HOME) 미복귀 상태에서 자동 기동 요청",
                action="서보 축 및 연동 컨베이어 기동 금지(Interlock Hold), 대기 램프 점멸",
                reset_policy="서보 알람 클리어(CLR) 후 원점 복귀 완료 시 자동 해제",
                related_io=(srv_alarms + srv_homes)[:4],
            )
        )
        st_body.extend([
            "(* [ALM_003] 서보 알람 및 원점 복귀 선행 조건 인터록 *)",
            "IF iServoAlarm THEN",
            "    qAlm_ServoFault  := TRUE;",
            "    qServoOnCmd      := FALSE;",
            "    qAllDriveEnable  := FALSE;",
            "END_IF;",
            "bStartPermissive := iSafetyOK AND iServoHomeDone AND NOT qAlm_ServoFault;",
            "",
        ])

    # Rule 4: Heater Over-Temperature Protection
    m_temp = re.search(r"(\d{2,3})\s*(?:도|℃|c\b)", text, re.IGNORECASE)
    temp_limit = int(m_temp.group(1)) if m_temp else 180
    if htr_otps or any(k in lower for k in ["히터", "온도", "과승온", "heater", "temp"]):
        alarms.append(
            InterlockRule(
                alarm_code="ALM_004",
                condition=f"히터 과승온 스위치(OTP) 트립 또는 측정 온도 > {temp_limit}°C 초과",
                action="히터 SSR/접촉기 출력 즉시 강제 차단 및 냉각 팬 최대 가동",
                reset_policy=f"온도 {temp_limit - 20}°C 이하 하강 확인 후 수동 리셋",
                related_io=htr_otps[:3],
            )
        )
        st_body.extend([
            f"(* [ALM_004] 공정 히터 과승온 보호 인터록 (상한 {temp_limit} C) *)",
            f"IF iHeaterOtpTrip OR (iProcessTemp_C > {temp_limit}) THEN",
            "    qAlm_OverTemp    := TRUE;",
            "    qHeaterEnableCmd := FALSE;",
            "END_IF;",
            "",
        ])

    # Rule 5: Custom user clause comment preservation & Manual Reset Latch
    st_body.extend([
        "(* 알람 통합 래치 및 수동 리셋 (FAULT_RESET_PB 상승엣지) *)",
        "qAnyAlarm := qAlm_SafetyTrip OR qAlm_DriveFault OR qAlm_ServoFault OR qAlm_OverTemp;",
        "IF iFaultResetPB AND iSafetyOK AND NOT iInverterFault AND NOT iServoAlarm AND NOT iHeaterOtpTrip THEN",
        "    qAlm_SafetyTrip := FALSE;",
        "    qAlm_DriveFault := FALSE;",
        "    qAlm_ServoFault := FALSE;",
        "    qAlm_OverTemp   := FALSE;",
        "    qBuzzer         := FALSE;",
        "    qTowerRed       := FALSE;",
        "    qAllDriveEnable := TRUE;",
        "END_IF;",
    ])

    notes.append(f"프로젝트 '{design.project.name}'의 실제 PLC I/O {len(channels)}점과 매핑하여 {len(alarms)}개 인터록·알람 규칙을 생성했습니다.")
    if m_temp:
        notes.append(f"자연어 요구사항에서 온도 상한 임계치({temp_limit}°C)를 추출하여 ST 코드에 반영했습니다.")

    header_lines = [
        "(* ========================================================================= *)",
        f"(* FB_InterlockAndAlarm — {design.project.name} ({design.project.settings.plc_vendor}) *)",
        f"(* 요구사항 요약: {text[:90]} *)",
        "(* ========================================================================= *)",
        "FUNCTION_BLOCK FB_InterlockAndAlarm",
        "VAR_INPUT",
        f"    iSafetyOK        : BOOL;  (* {safety_di[0] if safety_di else 'SAFETY_OK DI'} *)",
        f"    iInverterFault   : BOOL;  (* {inv_faults[0] if inv_faults else 'INV_FAULT DI'} *)",
        "    iMotorOverload   : BOOL;  (* THR Trip DI *)",
        f"    iServoAlarm      : BOOL;  (* {srv_alarms[0] if srv_alarms else 'SERVO_ALM DI'} *)",
        f"    iServoHomeDone   : BOOL;  (* {srv_homes[0] if srv_homes else 'SERVO_HOME DI'} *)",
        f"    iHeaterOtpTrip   : BOOL;  (* {htr_otps[0] if htr_otps else 'HEATER_OTP DI'} *)",
        "    iProcessTemp_C   : INT;   (* Process Temp Analog Input *)",
        "    iFaultResetPB    : BOOL;  (* FAULT_RESET_PB *)",
        "END_VAR",
        "VAR_OUTPUT",
        "    qAllDriveEnable  : BOOL := FALSE;",
        "    qConveyorRunCmd  : BOOL := FALSE;",
        "    qServoOnCmd      : BOOL := FALSE;",
        "    qHeaterEnableCmd : BOOL := FALSE;",
        "    qTowerRed        : BOOL := FALSE;",
        "    qBuzzer          : BOOL := FALSE;",
        "    qAnyAlarm        : BOOL := FALSE;",
        "    qAlm_SafetyTrip  : BOOL := FALSE;",
        "    qAlm_DriveFault  : BOOL := FALSE;",
        "    qAlm_ServoFault  : BOOL := FALSE;",
        "    qAlm_OverTemp    : BOOL := FALSE;",
        "END_VAR",
        "VAR",
        "    bStartPermissive : BOOL := FALSE;",
        "END_VAR",
        "",
    ]

    st_code = "\n".join(header_lines + st_body + ["END_FUNCTION_BLOCK"])
    return InterlockResponse(
        st_code=st_code,
        alarms=alarms,
        engine_used="Offline SSOT Interlock Synthesizer",
        notes=notes,
    )
