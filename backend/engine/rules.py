"""Deterministic ERC/DRC validation engine + Knowledge-Base AI Design Reviewer."""

from __future__ import annotations

from collections import Counter

from backend.models import (
    LoadCalculationResult,
    PlcChannel,
    PlcModule,
    PowerSummary,
    Project,
    RuleCheckItem,
)


def run_design_verification(
    project: Project,
    summary: PowerSummary,
    calcs: list[LoadCalculationResult],
    plc_modules: list[PlcModule],
    plc_channels: list[PlcChannel],
) -> list[RuleCheckItem]:
    """Execute 100% deterministic ERC/DRC checks followed by knowledge-base AI reviews."""
    checks: list[RuleCheckItem] = []

    # 1. Duplicate Functional Unit Tags (DRC-001)
    tag_counts = Counter(l.tag.strip().upper() for l in project.loads)
    for tag, count in tag_counts.items():
        if count > 1:
            checks.append(
                RuleCheckItem(
                    rule_id="DRC-001",
                    severity="ERROR",
                    category="DRC",
                    standard_ref="IEC 81346-1",
                    target_tag=tag,
                    title="기기 기능 태그(Tag) 중복",
                    detail=f"태그 '{tag}'가 {count}회 중복 정의되었습니다. 도면·BOM·PLC 주소 충돌을 유발합니다.",
                    recommendation="각 기능 유닛에 고유한 태그(예: CONV_01, CONV_02)를 부여하세요.",
                )
            )

    # 2. Safety Circuit Presence & PL Adequacy (SAF-001)
    safety_loads = [l for l in project.loads if l.load_type == "safety_circuit"]
    motion_loads = [l for l in project.loads if l.load_type in ("motor_dol", "motor_inv", "servo")]
    if motion_loads and not safety_loads:
        checks.append(
            RuleCheckItem(
                rule_id="SAF-001",
                severity="ERROR",
                category="SAFETY",
                standard_ref="IEC 60204-1 §9.2.5.4 / ISO 13849-1",
                target_tag="PROJECT",
                title="비상정지 및 안전 회로 누락",
                detail=f"동력/모션 부하가 {len(motion_loads)}건 있으나 비상정지(E-Stop) 및 안전 릴레이 회로가 정의되지 않았습니다.",
                recommendation="최소 PLd 등급 이상의 이중화 안전 회로(safety_circuit) 유닛을 추가하세요.",
            )
        )
    elif safety_loads and any((l.safety_level or "PLc") == "PLc" for l in safety_loads) and any(l.load_type == "servo" for l in motion_loads):
        checks.append(
            RuleCheckItem(
                rule_id="SAF-002",
                severity="WARNING",
                category="SAFETY",
                standard_ref="ISO 13849-1 / IEC 61800-5-2",
                target_tag=safety_loads[0].tag,
                title="서보 모션 축 대비 안전 등급(PLc) 검토 필요",
                detail="서보 모션 축이 포함된 설비에 PLc 등급이 설정되었습니다. 고속/협동 위험 구간은 PLd 이상 이중화(STO)가 권장됩니다.",
                recommendation="안전 등급을 PLd 또는 PLe로 상향하고 서보 STO 이중화 입력을 연결하세요.",
            )
        )

    # 3. Voltage Drop Check (ERC-001)
    for c in calcs:
        limit = 3.0 if c.load_type in ("motor_dol", "motor_inv", "servo", "heater") else 5.0
        if c.voltage_drop_pct > limit:
            checks.append(
                RuleCheckItem(
                    rule_id="ERC-001",
                    severity="ERROR",
                    category="ERC",
                    standard_ref="IEC 60364-5-52 / KEC 232",
                    target_tag=c.tag,
                    title="허용 전압강하 기준 초과",
                    detail=f"{c.name}({c.tag}) 회로의 전압강하가 {c.voltage_drop_pct}%로 허용 기준({limit}%)을 초과합니다.",
                    recommendation=f"현재 전선({c.wire_sq} SQ)을 한 단계 이상 상향하거나 케이블 길이를 단축하세요.",
                )
            )

    # 4. Main Breaker Margin Check (ERC-002)
    if summary.main_breaker_rating_a < summary.total_demand_current_a * 1.15:
        checks.append(
            RuleCheckItem(
                rule_id="ERC-002",
                severity="ERROR",
                category="ERC",
                standard_ref="IEC 60204-1 §7.2",
                target_tag="-Q0",
                title="주 차단기 정격 여유율 부족",
                detail=f"수용 전류({summary.total_demand_current_a}A) 대비 주 차단기({summary.main_breaker_rating_a}AT) 여유가 15% 미만입니다.",
                recommendation="차단기 프레임을 상위 정격으로 변경하거나 분기 부하를 2개 제어반으로 분산하세요.",
            )
        )

    # 5. SMPS Load Utilization Check (ERC-003)
    smps_util = (summary.total_dc24v_current_a / max(summary.smps_capacity_a, 0.1)) * 100.0
    if smps_util > 85.0:
        checks.append(
            RuleCheckItem(
                rule_id="ERC-003",
                severity="WARNING",
                category="ERC",
                standard_ref="IEC 60204-1 §9.1",
                target_tag="-G1",
                title="DC 24V SMPS 부하율 85% 초과",
                detail=f"선정된 SMPS({summary.smps_selected_part}, {summary.smps_capacity_a}A)의 부하율이 {smps_util:.1f}%입니다.",
                recommendation="장기 신뢰성 및 돌입전류 여유 확보를 위해 상위 용량 SMPS 또는 2대 병렬/분리 구성을 권장합니다.",
            )
        )

    # 6. PLC Address Uniqueness & Spare Ratio Check (ERC-004)
    addr_counts = Counter(ch.plc_address for ch in plc_channels)
    dup_addrs = [a for a, cnt in addr_counts.items() if cnt > 1]
    if dup_addrs:
        checks.append(
            RuleCheckItem(
                rule_id="ERC-004",
                severity="ERROR",
                category="ERC",
                standard_ref="IEC 61131-3",
                target_tag="PLC",
                title="PLC I/O 주소 중복 감지",
                detail=f"중복 할당된 PLC 주소가 감지되었습니다: {', '.join(dup_addrs[:5])}",
                recommendation="I/O 모듈 자동 재할당을 실행하세요.",
            )
        )

    for mod in plc_modules:
        if mod.channels > 0:
            spare_pct = ((mod.channels - mod.used_channels) / mod.channels) * 100.0
            if spare_pct < project.settings.io_spare_ratio * 100.0 * 0.5:
                checks.append(
                    RuleCheckItem(
                        rule_id="DRC-002",
                        severity="WARNING",
                        category="DRC",
                        standard_ref="사내 표준 I/O 예비율 기준",
                        target_tag=f"PLC Slot {mod.slot}",
                        title=f"{mod.module_type} 모듈 예비 포인트 부족",
                        detail=f"Slot {mod.slot} ({mod.part_number}) 사용률 {mod.used_channels}/{mod.channels}점 (예비 {spare_pct:.0f}%).",
                        recommendation="현장 증설 대비 I/O 예비율(20% 이상) 확보를 위해 모듈 추가를 검토하세요.",
                    )
                )

    # 7. IEC 60909 Short-Circuit Breaking Capacity Check (ERC-005)
    if summary.ik3_main_ka > 0 and summary.main_breaker_icu_ka < summary.ik3_main_ka:
        checks.append(
            RuleCheckItem(
                rule_id="ERC-005",
                severity="ERROR",
                category="ERC",
                standard_ref="IEC 60909-0 / IEC 60947-2",
                target_tag="-Q0",
                title="주 차단기 정격차단용량(Icu) 부족 (IEC 60909)",
                detail=f"예상 3상 단락전류 I''k3={summary.ik3_main_ka}kA(피크 {summary.ip_peak_ka}kA)가 주 차단기({summary.main_breaker_part}) Icu={summary.main_breaker_icu_ka}kA를 초과합니다.",
                recommendation="고차단용량(H/L 타입, Icu ≥ 36~50kA) MCCB로 상향하거나 한류형 퓨즈/백업 보호를 적용하세요.",
            )
        )
    for sc in summary.selectivity_checks:
        if not sc.breaking_ok:
            checks.append(
                RuleCheckItem(
                    rule_id="ERC-005",
                    severity="ERROR",
                    category="ERC",
                    standard_ref="IEC 60909-0 / IEC 60947-2",
                    target_tag=sc.tag,
                    title=f"분기 차단기 차단용량 부족 ({sc.downstream_part})",
                    detail=f"{sc.name} 분기점 단락전류 I''k3={sc.ik3_branch_ka}kA > 분기 차단기 Icu={sc.downstream_icu_ka}kA.",
                    recommendation="분기 차단기를 상위 차단용량 모델로 교체하거나 상위 차단기와 캐스케이딩 인증 조합을 적용하세요.",
                )
            )
        elif sc.coordination_status == "NON_SELECTIVE":
            checks.append(
                RuleCheckItem(
                    rule_id="ERC-006",
                    severity="WARNING",
                    category="ERC",
                    standard_ref="IEC 60364-5-53 / 보호협조(Selectivity)",
                    target_tag=sc.tag,
                    title="주-분기 차단기 선택적 보호협조(Selectivity) 미흡",
                    detail=f"주 차단기({sc.upstream_rating_a}AT) 대비 분기({sc.downstream_rating_a}AT) 정격비={sc.selectivity_ratio}x (<1.6x). 분기 사고 시 주 차단기 동시 트립 위험이 있습니다.",
                    recommendation="주 차단기 정격 프레임 상향, 전자식 트립(LSIG) 지연 설정, 또는 부하 분산을 검토하세요.",
                )
            )

    # 8. IEC 60890 Thermal Headroom Check (THM-001)
    thm = summary.thermal_analysis
    if thm and thm.predicted_uncooled_temp_c > project.settings.max_internal_temp_c:
        checks.append(
            RuleCheckItem(
                rule_id="THM-001",
                severity="WARNING" if thm.cooling_mode == "PANEL_AC" else "INFO",
                category="THERMAL",
                standard_ref="IEC 60890 / IEC 61439-1",
                target_tag="=A1+P1",
                title=f"IEC 60890 열해석: 강제 냉각 필수 ({thm.cooling_mode})",
                detail=(
                    f"유효 방열면적 Ae={thm.effective_surface_m2}m², 자연방열 {thm.natural_dissipation_w}W 대비 총 발열 {summary.total_heat_loss_w}W. "
                    f"미냉각 시 내부온도 {thm.predicted_uncooled_temp_c}°C 예상 → {thm.recommended_cooling_part}({thm.recommended_cooling_capacity_w}W) 적용 시 {thm.predicted_cooled_temp_c}°C 유지."
                ),
                recommendation="선정된 냉각장치(필터팬 또는 Blue e+ 판넬 에어컨)의 흡·배기 동선과 드라이브 상·하 100mm 이격거리를 유지하세요.",
            )
        )
    elif summary.total_heat_loss_w > 500 and project.settings.ambient_temp_c >= 40:
        checks.append(
            RuleCheckItem(
                rule_id="THM-001",
                severity="WARNING",
                category="THERMAL",
                standard_ref="IEC 60890 / IEC 61439-1",
                target_tag="=A1+P1",
                title="고온 환경(40°C+) 및 고발열 제어반 냉각 주의",
                detail=f"주위온도 {project.settings.ambient_temp_c}°C, 내부 발열 {summary.total_heat_loss_w}W 조건에서는 필터팬만으로 45°C 유지가 어렵습니다.",
                recommendation="밀폐형 제어반 에어컨(판넬 쿨러) 적용 및 인버터 상·하부 100mm 이상 방열 이격거리를 확보하세요.",
            )
        )

    # 8. AI Knowledge-Base Design Reviews (Past Field Troubleshooting Patterns)
    for load in project.loads:
        if load.load_type == "solenoid_group" and not load.has_surge_suppressor:
            checks.append(
                RuleCheckItem(
                    rule_id="AI-KB-101",
                    severity="WARNING",
                    category="AI_REVIEW",
                    standard_ref="사내 트러블슈팅 DB #TR-2024-018",
                    target_tag=load.tag,
                    title="[AI 리뷰] 유도성 솔레노이드 서지 억제기(Flyback Diode) 누락",
                    detail=f"{load.name}({load.quantity}개)에 서지 억제기가 비활성화되어 있습니다. 과거 유사 설비에서 PLC DO 트랜지스터 소손 및 오동작 사례가 다수 발생했습니다.",
                    recommendation="각 솔레노이드 코일 또는 릴레이 소켓에 플라이백 다이오드/바리스터 서지 억제기를 활성화하세요.",
                )
            )
        if load.load_type == "motor_inv" and not load.has_emi_filter:
            checks.append(
                RuleCheckItem(
                    rule_id="AI-KB-102",
                    severity="WARNING",
                    category="AI_REVIEW",
                    standard_ref="IEC 61800-3 / 트러블슈팅 DB #TR-2025-004",
                    target_tag=load.tag,
                    title="[AI 리뷰] 인버터 입력 EMI 노이즈 필터 미적용",
                    detail=f"{load.name} 인버터 입력측에 EMI 필터가 제외되었습니다. 아날로그(4-20mA) 센서 및 서보 엔코더 통신 노이즈 유입 위험이 있습니다.",
                    recommendation="인버터 전단 EMI 필터 추가 및 동력선/신호선 덕트 물리적 분리(100mm 이상)를 적용하세요.",
                )
            )

    # Always include positive confirmation summary if zero ERRORs
    error_cnt = sum(1 for ch in checks if ch.severity == "ERROR")
    if error_cnt == 0:
        checks.append(
            RuleCheckItem(
                rule_id="ERC-PASS",
                severity="INFO",
                category="ERC",
                standard_ref=project.settings.standard_profile,
                target_tag="SYSTEM",
                title="결정론적 전기·안전 필수 규격(ERC/DRC) 통과",
                detail=f"총 {len(calcs)}개 기능 유닛, {len(plc_channels)}개 PLC I/O, 주 차단기 {summary.main_breaker_rating_a}AT 및 SMPS {summary.smps_capacity_a}A 정합성이 검증되었습니다.",
                recommendation="출도 전 리비전 스냅샷(Rev)을 저장하고 FAT 체크시트를 발행하세요.",
            )
        )

    return checks
