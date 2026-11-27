"""PLC I/O automatic allocation, rack/slot configuration, and IEC 61131-3 ST code generator."""

from __future__ import annotations

import math
from typing import Literal

from backend.catalog import PLC_CATALOG
from backend.models import PlcChannel, PlcModule, Project


def _format_address(plc_vendor: str, io_type: str, module_index: int, point_idx: int) -> str:
    """Format vendor-authentic PLC I/O addresses across 6 major global FA PLC platforms."""
    if plc_vendor == "Mitsubishi Electric":
        base_hex = module_index * 32 + point_idx
        if io_type == "DI":
            return f"X{base_hex:03X}"
        if io_type == "DO":
            return f"Y{base_hex:03X}"
        if io_type == "AI":
            return f"D{1000 + module_index * 10 + point_idx}"
        return f"D{2000 + module_index * 10 + point_idx}"

    if plc_vendor == "Siemens":
        byte_no = module_index * 4 + (point_idx // 8)
        bit_no = point_idx % 8
        if io_type == "DI":
            return f"%I{byte_no}.{bit_no}"
        if io_type == "DO":
            return f"%Q{byte_no}.{bit_no}"
        if io_type == "AI":
            return f"%IW{64 + (module_index * 8 + point_idx) * 2}"
        return f"%QW{64 + (module_index * 4 + point_idx) * 2}"

    if plc_vendor == "Rockwell Automation":
        slot_num = 2 + module_index
        if io_type == "DI":
            return f"Local:{slot_num}:I.Data.{point_idx}"
        if io_type == "DO":
            return f"Local:{slot_num}:O.Data.{point_idx}"
        if io_type == "AI":
            return f"Local:{slot_num}:I.Ch{point_idx}Data"
        return f"Local:{slot_num}:O.Ch{point_idx}Data"

    if plc_vendor == "Omron":
        if io_type == "DI":
            return f"NX_DI{module_index}_Bit{point_idx:02d}"
        if io_type == "DO":
            return f"NX_DO{module_index}_Bit{point_idx:02d}"
        if io_type == "AI":
            return f"NX_AI{module_index}_Ch{point_idx:02d}"
        return f"NX_AO{module_index}_Ch{point_idx:02d}"

    if plc_vendor == "Beckhoff":
        if io_type == "DI":
            return f"%IX{module_index}.{point_idx}"
        if io_type == "DO":
            return f"%QX{module_index}.{point_idx}"
        if io_type == "AI":
            return f"%IW{module_index * 8 + point_idx * 2}"
        return f"%QW{module_index * 8 + point_idx * 2}"

    # LS Electric (XGI IEC notation)
    if io_type == "DI":
        return f"%IX0.{module_index}.{point_idx}"
    if io_type == "DO":
        return f"%QX0.{module_index}.{point_idx}"
    if io_type == "AI":
        return f"%IW0.{module_index}.{point_idx}"
    return f"%QW0.{module_index}.{point_idx}"


def build_plc_and_io(project: Project) -> tuple[list[PlcModule], list[PlcChannel], str]:
    """Generate I/O signals from SSOT loads, size PLC rack with spare ratio, and emit ST code."""

    raw_signals: dict[Literal["DI", "DO", "AI", "AO"], list[tuple[str, str, str]]] = {
        "DI": [
            ("SYS", "MAIN_POWER_OK (주전원 정상)", "DC 24V"),
            ("SYS", "AUTO_MODE_SW (자동 운전 선택)", "DC 24V"),
            ("SYS", "CYCLE_START_PB (운전 시작 버튼)", "DC 24V"),
            ("SYS", "FAULT_RESET_PB (알람 리셋 버튼)", "DC 24V"),
        ],
        "DO": [
            ("SYS", "TOWER_LAMP_GREEN (운전 표시등)", "DC 24V"),
            ("SYS", "TOWER_LAMP_AMBER (대기 표시등)", "DC 24V"),
            ("SYS", "TOWER_LAMP_RED (이상 표시등)", "DC 24V"),
            ("SYS", "ALARM_BUZZER (경보 부저)", "DC 24V"),
        ],
        "AI": [],
        "AO": [],
    }

    for load in project.loads:
        qty = max(load.quantity, 1)
        if load.load_type == "motor_dol":
            for i in range(1, qty + 1):
                suffix = f"_{i:02d}" if qty > 1 else ""
                tag = f"{load.tag}{suffix}"
                raw_signals["DI"].append((tag, f"{load.name}{suffix} 운전 응답 (MC Aux)", "DC 24V"))
                raw_signals["DI"].append((tag, f"{load.name}{suffix} 과부하 이상 (THR Trip)", "DC 24V"))
                raw_signals["DO"].append((tag, f"{load.name}{suffix} 기동 지령 (MC Coil)", "DC 24V"))

        elif load.load_type == "motor_inv":
            for i in range(1, qty + 1):
                suffix = f"_{i:02d}" if qty > 1 else ""
                tag = f"{load.tag}{suffix}"
                raw_signals["DI"].append((tag, f"{load.name}{suffix} 인버터 운전중 (RUN)", "DC 24V"))
                raw_signals["DI"].append((tag, f"{load.name}{suffix} 인버터 이상 (FAULT)", "DC 24V"))
                raw_signals["DO"].append((tag, f"{load.name}{suffix} 정회전 지령 (FWD)", "DC 24V"))
                raw_signals["DO"].append((tag, f"{load.name}{suffix} 이상 리셋 (RST)", "DC 24V"))
                raw_signals["AO"].append((tag, f"{load.name}{suffix} 속도 지령 (0-10V)", "0-10V"))

        elif load.load_type == "servo":
            for i in range(1, qty + 1):
                suffix = f"_{i:02d}" if qty > 1 else ""
                tag = f"{load.tag}{suffix}"
                raw_signals["DI"].append((tag, f"{load.name}{suffix} 서보 레디 (RDY)", "DC 24V"))
                raw_signals["DI"].append((tag, f"{load.name}{suffix} 서보 알람 (ALM)", "DC 24V"))
                raw_signals["DI"].append((tag, f"{load.name}{suffix} 원점 센서 (HOME)", "DC 24V"))
                raw_signals["DO"].append((tag, f"{load.name}{suffix} 서보 온 (SON)", "DC 24V"))
                raw_signals["DO"].append((tag, f"{load.name}{suffix} 알람 클리어 (CLR)", "DC 24V"))

        elif load.load_type == "heater":
            for i in range(1, qty + 1):
                suffix = f"_{i:02d}" if qty > 1 else ""
                tag = f"{load.tag}{suffix}"
                raw_signals["DI"].append((tag, f"{load.name}{suffix} 과승온 알람 (OTP)", "DC 24V"))
                raw_signals["DO"].append((tag, f"{load.name}{suffix} 히터 출력 허가 (EN)", "DC 24V"))
                raw_signals["AI"].append((tag, f"{load.name}{suffix} 온도 센서 (4-20mA)", "4-20mA"))

        elif load.load_type == "solenoid_group":
            for i in range(1, qty + 1):
                tag = f"{load.tag}_{i:02d}"
                raw_signals["DO"].append((tag, f"{load.name} 밸브 #{i:02d} 구동", "DC 24V"))

        elif load.load_type == "sensor_group":
            for i in range(1, qty + 1):
                tag = f"{load.tag}_{i:02d}"
                raw_signals["DI"].append((tag, f"{load.name} 감지 센서 #{i:02d}", "DC 24V"))

        elif load.load_type == "safety_circuit":
            raw_signals["DI"].append((load.tag, "안전 릴레이 정상 (SAFETY_OK)", "DC 24V"))
            for i in range(1, qty + 1):
                raw_signals["DI"].append((f"{load.tag}_{i:02d}", f"비상정지 #{i:02d} 상태 모니터링", "DC 24V"))
            raw_signals["DO"].append((load.tag, "안전 릴레이 리셋 펄스 (SAF_RST)", "DC 24V"))

    plc_vendor = project.settings.plc_vendor
    plc_cat = PLC_CATALOG.get(plc_vendor, PLC_CATALOG["Mitsubishi Electric"])
    spare = project.settings.io_spare_ratio

    modules: list[PlcModule] = []
    channels: list[PlcChannel] = []
    slot = 0

    # Slot 0: PSU, Slot 1: CPU
    for base_type in ("PSU", "CPU"):
        item = plc_cat[base_type]
        modules.append(
            PlcModule(
                slot=slot,
                module_type=base_type,
                part_number=item.part_number,
                manufacturer=item.vendor,
                description=item.spec,
                channels=0,
                used_channels=0,
                start_address="-",
                end_address="-",
            )
        )
        slot += 1

    tb_idx = 1
    for io_type in ("DI", "DO", "AI", "AO"):
        sigs = raw_signals[io_type]
        if not sigs:
            continue
        item = plc_cat[io_type]
        ch_per_mod = item.channels
        required_with_spare = int(math.ceil(len(sigs) * (1.0 + spare)))
        num_mods = max(1, int(math.ceil(required_with_spare / ch_per_mod)))

        for m_idx in range(num_mods):
            chunk = sigs[m_idx * ch_per_mod : (m_idx + 1) * ch_per_mod]
            start_addr = _format_address(plc_vendor, io_type, m_idx, 0)
            end_addr = _format_address(plc_vendor, io_type, m_idx, ch_per_mod - 1)
            modules.append(
                PlcModule(
                    slot=slot,
                    module_type=io_type,
                    part_number=item.part_number,
                    manufacturer=item.vendor,
                    description=item.spec,
                    channels=ch_per_mod,
                    used_channels=len(chunk),
                    start_address=start_addr,
                    end_address=end_addr,
                )
            )
            for pt_idx, (u_tag, sig_name, volt) in enumerate(chunk):
                addr = _format_address(plc_vendor, io_type, m_idx, pt_idx)
                channels.append(
                    PlcChannel(
                        channel_id=f"{io_type}_{slot}_{pt_idx:02d}",
                        io_type=io_type,
                        plc_address=addr,
                        slot=slot,
                        point_index=pt_idx,
                        terminal_tag=f"-X2:{tb_idx:03d}",
                        wire_number=f"{io_type}{slot}{pt_idx:02d}",
                        unit_tag=u_tag,
                        signal_name=sig_name,
                        voltage=volt,
                    )
                )
                tb_idx += 1
            slot += 1

    st_code = _generate_st_scaffold(project, channels)
    return modules, channels, st_code


def _safe_ident(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in text.upper())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "SIG"


def _generate_st_scaffold(project: Project, channels: list[PlcChannel]) -> str:
    """Generate IEC 61131-3 Structured Text scaffolding synchronized with SSOT I/O."""
    lines = [
        "(* ========================================================================= *)",
        f"(* Project : {project.name}                                                 *)",
        f"(* PLC     : {project.settings.plc_vendor} | Standard: {project.settings.standard_profile} *)",
        "(* Auto-generated by PanelCraft AI SSOT Engine (IEC 61131-3 Structured Text) *)",
        "(* ========================================================================= *)",
        "",
        "VAR_GLOBAL",
    ]

    used_names: set[str] = set()
    di_safety = None
    motor_runs: list[tuple[str, str]] = []

    for ch in channels[:40]:
        raw_name = f"{ch.io_type}_{_safe_ident(ch.unit_tag)}_{ch.point_index:02d}"
        if raw_name in used_names:
            raw_name = f"{raw_name}_S{ch.slot}"
        used_names.add(raw_name)
        iec_type = "BOOL" if ch.io_type in ("DI", "DO") else "INT"
        lines.append(f"    {raw_name:<28} AT {ch.plc_address:<10} : {iec_type};  (* {ch.signal_name} *)")
        if "SAFETY_OK" in ch.signal_name:
            di_safety = raw_name
        if ch.io_type == "DO" and ("기동 지령" in ch.signal_name or "정회전 지령" in ch.signal_name):
            motor_runs.append((raw_name, ch.unit_tag))

    if len(channels) > 40:
        lines.append(f"    (* ... 외 {len(channels) - 40}개 I/O 포인트는 전체 .st 파일 다운로드 시 포함 ... *)")

    lines.extend([
        "    bSystemReady                 : BOOL := FALSE;",
        "    bAnyFault                    : BOOL := FALSE;",
        "    bAutoRunning                 : BOOL := FALSE;",
        "END_VAR",
        "",
        "PROGRAM PRG_MainControl",
        "(* 1. Safety & Power Interlock Check (ISO 13849-1) *)",
        f"bSystemReady := DI_SYS_00 AND {di_safety or 'TRUE'} AND NOT bAnyFault;",
        "",
        "(* 2. Auto Cycle Start / Stop Interlock *)",
        "IF NOT bSystemReady THEN",
        "    bAutoRunning := FALSE;",
        "ELSIF DI_SYS_01 AND DI_SYS_02 THEN",
        "    bAutoRunning := TRUE;",
        "END_IF;",
        "",
        "(* 3. Actuator & Drive Output Interlock *)",
    ])

    if motor_runs:
        for var_name, unit_tag in motor_runs[:8]:
            lines.append(f"{var_name} := bAutoRunning AND bSystemReady;  (* {unit_tag} 구동 인터록 *)")
    else:
        lines.append("(* No motor/inverter outputs mapped yet *)")

    lines.extend([
        "",
        "(* 4. Tower Lamp & Alarm Indication *)",
        "DO_SYS_00 := bAutoRunning;                   (* GREEN  : Auto Running *)",
        "DO_SYS_01 := bSystemReady AND NOT bAutoRunning; (* AMBER : Standby *)",
        "DO_SYS_02 := bAnyFault;                      (* RED    : Fault *)",
        "DO_SYS_03 := bAnyFault AND NOT DI_SYS_03;    (* BUZZER : Fault & Not Silenced *)",
        "END_PROGRAM",
    ])
    return "\n".join(lines)
