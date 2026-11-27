/** PanelCraft AI Bilingual i18n Dictionary (English default, Korean toggle) */

const STORAGE_KEY = "panelcraft_lang";

export const DICT = {
  en: {
    pageTitle: "PanelCraft AI — Control Panel Design Automation",
    brandSub: "Multi-Tenant Cloud Control Panel SSOT",
    org: "Org",
    project: "Project",
    vendor: "Vendor",
    plc: "PLC",
    llmBtnPrefix: "LLM",
    llmBuiltin: "Built-in",
    aiDraftBtn: "AI Spec · RFP Draft",
    exportBtn: "Export ▾",
    communityBtn: "Community ▾",
    navSection: "Engineering Workflow",
    navLoads: "Specs · Excel Import",
    navBom: "Sizing · BOM",
    navIo: "PLC · I/O · Interlock",
    navSchematic: "Schematics · Terminals",
    navLayout: "2D Panel Layout",
    navVerify: "Verify · AI Review",
    navRevisions: "Versions · ECN",
    syncDone: "SSOT Model Synchronized",
    syncing: "Recalculating SSOT Model...",
    sidebarHint: "Any change to specs or catalog updates sizing, BOM, I/O, schematics, and 2D layout immediately.",

    // Export menu
    expEplan: "EPLAN AML / XML (.aml)",
    expDxf: "Schematic AutoCAD (.dxf)",
    expLayoutDxf: "2D Mounting Plate (.dxf)",
    expBomCsv: "Unified BOM (.csv)",
    expIoCsv: "PLC I/O Schedule (.csv)",
    expTermCsv: "Terminals & Wire List (.csv)",
    expPlcSt: "PLC IEC 61131-3 ST (.st)",
    expFatMd: "FAT / SAT Checklist (.md)",

    // Community / GitHub menu
    ghReportBug: "Report Bug (GitHub Issues)",
    ghFeatureReq: "Request Feature (GitHub Issues)",
    ghDiscussions: "Community Q&A (GitHub Discussions)",
    ghReleases: "Releases & Installers",
    checkUpdates: "Version & Auto-Update...",

    // Telemetry strip
    kpiPowerTitle: "Total Power / Main MCCB",
    kpiSmpsTitle: "DC 24V SMPS / Plate Usage",
    kpiIoTitle: "Active PLC I/O Points",
    kpiBomTitle: "Estimated BOM Total",
    kpiVerifyTitle: "ERC/DRC · AI Verification",
    kpiSlots: "slots",
    kpiItems: "items",
    kpiHeat: "Heat",
    kpiStdChecked: "verified",

    // View 01: Loads & Importers
    v1ProfileTitle: "Project Profile & Electrical System (SSOT Baseline)",
    v1ProfileSub: "Changing power system, standard, ambient temp, or I/O spare ratio immediately recalculates all deliverables.",
    lblProjectName: "Project Name",
    lblClient: "Client / Line",
    lblStandard: "Standard Profile",
    lblPowerSys: "Primary Power System",
    lblAmbient: "Ambient Temp (°C)",
    lblSpare: "PLC I/O Spare (%)",
    v1ImportLoadsTitle: "Import Load Schedule (Excel .xlsx / CSV)",
    v1ImportLoadsSub: "Upload existing Excel/CSV load tables directly into the SSOT model.",
    btnLoadTpl: "Load Template CSV",
    optReplace: "Replace All",
    optAppend: "Append",
    btnImportLoads: "Import Loads",
    v1CatalogTitle: "Company Component Catalog DB (BOM Priority)",
    v1CatalogSubPrefix: "Active preferred company parts:",
    btnCatTpl: "Catalog Template",
    btnReset: "Reset",
    btnImportCat: "Upload Catalog",
    catEmpty: "No custom company parts uploaded yet. Uploaded parts override default vendor parts in BOM.",
    v1LoadListTitle: "Functional Units & Load Schedule",
    v1LoadListSub: "Edit cells inline to synchronize current, cable SQ, breaker sizing, PLC I/O, and 2D layout.",
    btnAddInv: "+ VFD Motor",
    btnAddServo: "+ Servo Axis",
    btnAddHeater: "+ Heater",
    btnAddSol: "+ Solenoid",
    btnAddSafety: "+ Safety",
    thTag: "Unit Tag",
    thName: "Load / Unit Name",
    thType: "Type",
    thKw: "Power (kW)",
    thQty: "Qty",
    thCable: "Cable (m)",
    thOptions: "Safety / Protection",
    thRatedA: "Rated A",
    thWireSq: "Wire SQ",
    thBreaker: "Breaker",
    btnDelete: "Delete",
    optEmi: "EMI Filter",
    optSurge: "Surge Diode",

    // View 02: BOM & Calculations
    v2PowerTitle: "Main Power & Control Power (SMPS) Sizing",
    v2PowerSub: "Deterministic engineering formula results",
    v2ThermalTitle: "Panel Heat Dissipation & Enclosure Sizing (IEC 60890)",
    v2BomTitle: "Unified Vendor BOM",
    v2BomSub: "Switch vendors in the top bar or upload a company catalog to swap part numbers & pricing instantly.",
    v2AuditTitle: "Branch Circuit Calculation Audit Trail",
    v2AuditSub: "Full formula trace, starting current, voltage drop, and heat dissipation per load.",
    btnDownloadBom: "Download BOM CSV",
    bomTotalLabel: "Estimated Material Cost (excl. VAT)",

    // View 03: PLC / I/O / Interlock
    v3RackTitle: "PLC Hardware Rack Layout",
    v3IlTitle: "AI Natural-Language PLC Interlock & Alarm Generator (IEC 61131-3 ST)",
    v3IlSub: "Generates safety interlocks & alarm matrices grounded in this project's real PLC I/O addresses.",
    btnGenIl: "Generate ST Interlock",
    btnGenerating: "Generating...",
    v3IoTableTitle: "PLC I/O Allocation Table (Synced with Terminals & Wires)",
    v3IoTableSub: "Filter by I/O type or search by address, tag, or signal comment.",
    v3StTitle: "Auto-Generated IEC 61131-3 ST Base Scaffold",
    v3StSub: "Global I/O symbol declarations, safety interlocks, auto/manual mode, and tower lamp logic.",
    btnCopy: "Copy Code",
    btnCopied: "Copied!",

    // View 04: Schematics
    v4Title: "Auto-Synthesized Multi-Sheet Electrical Schematics (IEC 61082)",
    v4Sub: "Click any schematic symbol to inspect its synchronized SSOT device parameters.",
    v4InspectorHint: "Click any breaker, drive, motor, safety relay, or PLC pin to inspect SSOT parameters.",
    v4TermTitle: "Terminal Strips & Wire Numbering (-X1 Power / -X2 Control & I/O)",
    btnTermCsv: "Download Terminals CSV",

    // View 05: 2D Mounting Plate Layout
    v5Title: "2D Control Panel Mounting Plate Automatic Layout",
    v5Sub: "Enforces IEC 61439 power/control segregation (60mm wire duct) and 100mm thermal clearance around drives.",
    btnEmcMode: "EMC Zone Layout",
    btnThermalMode: "Thermal Heatmap",
    v5InspectorHint: "Click any mounted component to inspect exact X/Y mm coordinates, W×H×D dimensions, and Watt dissipation.",
    v5TableTitle: "Mounting Plate Coordinates & Dimensions (Machining Schedule)",
    v5TableSub: "100% synchronized with EPLAN Pro Panel AML and 1:1 mm AutoCAD DXF output.",

    // View 06: Verification
    v6Title: "Hybrid Design Verification (Deterministic ERC/DRC + AI Knowledge Review)",
    v6Sub: "Electrical & safety rules run deterministically; field troubleshooting heuristics are added by AI review.",
    btnFatDownload: "FAT / SAT Checklist (.md)",
    lblAction: "Recommendation",

    // View 07: Revisions & App Version
    v7SnapTitle: "Create Project Revision Snapshot (ECN Baseline)",
    v7SnapSub: "Freeze current SSOT loads, settings, BOM, and I/O into an immutable revision snapshot with rollback support.",
    lblRevTag: "Revision Tag",
    lblRevStatus: "Approval Status",
    lblAuthor: "Engineer",
    lblSummary: "ECN Change Summary",
    btnSaveRev: "Save Revision Snapshot",
    v7HistoryTitle: "Project Revision History & Rollback",
    v7HistorySub: "Promote revision status or restore/rollback the project to any prior snapshot.",
    btnRestore: "Restore",
    v7DiffTitle: "ECN Impact Comparison (Revision Diff)",
    v7DiffSub: "Compare added/removed/modified loads, BOM quantity/cost delta, and PLC I/O delta.",
    btnRunDiff: "Compare Diff",

    // Modals
    copilotTitle: "AI Spec & RFP PDF → Control Panel Draft Generator",
    copilotSub: "Upload a customer RFP (PDF/TXT) or describe requirements to generate loads, safety PL, I/O, schematics, and 2D layout.",
    copilotUploadTitle: "Upload RFP Document (PDF / TXT / MD)",
    copilotUploadSub: "Extracts text automatically and parses via your configured External/Local LLM or Built-in engine.",
    btnParsePdf: "Analyze PDF",
    btnRunCopilot: "Generate Project Draft",
    btnCancel: "Cancel",

    llmTitle: "External & On-Premise Local LLM Gateway Settings",
    llmSub: "Configure AI engine for RFP PDF parsing and natural-language ST interlocks. Electrical calculations remain 100% deterministic.",
    btnTestLlm: "Test Connection",
    btnSave: "Save Settings",

    updateTitle: "Version Management, Auto-Updater & GitHub Community",
    updateSub: "Check GitHub Releases for new desktop/Android installers, view changelog, or open GitHub Issues & Discussions.",
    btnCheckNow: "Check for Updates Now",
    btnSaveUpdateCfg: "Save Update Config",

    // Load Type Labels
    lt_motor_inv: "VFD Inverter Motor",
    lt_motor_dol: "DOL Motor",
    lt_servo: "AC Servo Axis",
    lt_heater: "Process Heater",
    lt_solenoid_group: "Solenoid Group (24V)",
    lt_sensor_group: "Sensor Group (24V)",
    lt_safety_circuit: "Safety Circuit (E-Stop)",
  },

  ko: {
    pageTitle: "PanelCraft AI — 전장·제어반 자동화 제어설계 플랫폼",
    brandSub: "멀티테넌트 클라우드 제어설계 SSOT",
    org: "제조사",
    project: "프로젝트",
    vendor: "전장 벤더",
    plc: "PLC",
    llmBtnPrefix: "LLM",
    llmBuiltin: "내장",
    aiDraftBtn: "AI 사양 · RFP 초안",
    exportBtn: "산출물 내보내기 ▾",
    communityBtn: "커뮤니티 ▾",
    navSection: "엔지니어링 워크플로우",
    navLoads: "사양 · Excel 임포트",
    navBom: "용량계산 · BOM",
    navIo: "PLC · I/O · 인터록",
    navSchematic: "전기회로도 · 단자대",
    navLayout: "중판 2D 배치도",
    navVerify: "검증 · AI 리뷰",
    navRevisions: "버전관리 · ECN",
    syncDone: "SSOT 모델 동기화 완료",
    syncing: "SSOT 모델 재계산 중...",
    sidebarHint: "사양·부품 DB 변경 시 용량·BOM·I/O·회로도·중판 배치도가 즉시 동기화됩니다.",

    expEplan: "EPLAN AML / XML (.aml)",
    expDxf: "전기회로도 AutoCAD (.dxf)",
    expLayoutDxf: "중판 2D 배치도 AutoCAD (.dxf)",
    expBomCsv: "통합 부품표 BOM (.csv)",
    expIoCsv: "PLC I/O 리스트 (.csv)",
    expTermCsv: "단자대 · 배선 리스트 (.csv)",
    expPlcSt: "PLC 기초코드 IEC 61131-3 (.st)",
    expFatMd: "FAT / SAT 시운전 체크시트 (.md)",

    ghReportBug: "버그 제보 (GitHub Issues)",
    ghFeatureReq: "기능 제안 (GitHub Issues)",
    ghDiscussions: "질문 및 토론 (GitHub Discussions)",
    ghReleases: "릴리즈 및 플랫폼 설치파일",
    checkUpdates: "버전 관리 · 자동 업데이트...",

    kpiPowerTitle: "총 설비 용량 / 주 차단기",
    kpiSmpsTitle: "DC 24V SMPS / 중판 점유율",
    kpiIoTitle: "PLC I/O 총점 (활성)",
    kpiBomTitle: "통합 BOM 예상 자재비",
    kpiVerifyTitle: "ERC/DRC · AI 검증 상태",
    kpiSlots: "슬롯",
    kpiItems: "품목",
    kpiHeat: "발열",
    kpiStdChecked: "기준 검도 완료",

    v1ProfileTitle: "프로젝트 기본 사양 및 전원 계통 (SSOT 기준 프로필)",
    v1ProfileSub: "전원 계통, 규격, 주위온도, I/O 예비율을 변경하면 모든 계산·BOM·도면·중판 배치도가 실시간 갱신됩니다.",
    lblProjectName: "프로젝트명",
    lblClient: "고객사 / 라인",
    lblStandard: "적용 규격",
    lblPowerSys: "주전원 계통",
    lblAmbient: "주위온도 (°C)",
    lblSpare: "PLC I/O 예비율 (%)",
    v1ImportLoadsTitle: "사내 Excel / CSV 부하표 일괄 업로드",
    v1ImportLoadsSub: "기존 엑셀 부하 리스트(.xlsx / .csv)를 업로드해 SSOT 모델에 자동 반영합니다.",
    btnLoadTpl: "부하표 양식 CSV",
    optReplace: "전체 교체",
    optAppend: "기존에 추가",
    btnImportLoads: "부하표 임포트",
    v1CatalogTitle: "사내 표준 부품 DB 업로드 (BOM 우선 매칭)",
    v1CatalogSubPrefix: "활성 사내 표준 부품:",
    btnCatTpl: "부품 DB 양식",
    btnReset: "초기화",
    btnImportCat: "부품 DB 등록",
    catEmpty: "등록된 사내 표준 부품 DB가 없습니다. Excel(.xlsx)/CSV 업로드 시 BOM 선정에서 최우선 매칭됩니다.",
    v1LoadListTitle: "기능 유닛 및 부하 리스트 (Load & Actuator Schedule)",
    v1LoadListSub: "셀을 수정하면 정격전류, 전선 굵기(SQ), 차단기 정격, PLC I/O, 중판 배치도가 자동 동기화됩니다.",
    btnAddInv: "+ 인버터 모터",
    btnAddServo: "+ 서보 축",
    btnAddHeater: "+ 히터",
    btnAddSol: "+ 솔레노이드",
    btnAddSafety: "+ 안전회로",
    thTag: "기능 태그",
    thName: "부하 / 유닛명",
    thType: "유닛 유형",
    thKw: "용량 (kW)",
    thQty: "수량",
    thCable: "케이블 (m)",
    thOptions: "안전/보호 옵션",
    thRatedA: "정격 전류",
    thWireSq: "선정 SQ",
    thBreaker: "차단기",
    btnDelete: "삭제",
    optEmi: "EMI 필터",
    optSurge: "서지 억제",

    v2PowerTitle: "주전원 · 제어전원(SMPS) 용량 계산 요약",
    v2PowerSub: "결정론적 수식 기반 자동 선정 결과",
    v2ThermalTitle: "제어반 열부하 및 외함 크기 추정 (IEC 60890)",
    v2BomTitle: "통합 부품표 (SSOT Vendor BOM)",
    v2BomSub: "상단 전장 벤더 전환 또는 사내 부품 DB 업로드 시 전체 파트넘버·단가가 즉시 갱신됩니다.",
    v2AuditTitle: "분기 회로별 계산 근거 추적표 (Calculation Audit Trail)",
    v2AuditSub: "모든 자동 선정 결과의 수식·기동전류·전압강하·발열량 산출 근거",
    btnDownloadBom: "BOM CSV 다운로드",
    bomTotalLabel: "총 예상 자재비 (VAT 별도)",

    v3RackTitle: "PLC 하드웨어 랙 구성",
    v3IlTitle: "AI 자연어 PLC 인터록 · 알람 코드 생성기 (IEC 61131-3 ST)",
    v3IlSub: "현재 프로젝트의 실제 PLC I/O 주소와 연결된 안전 인터록 및 알람 매트릭스를 자동 생성합니다.",
    btnGenIl: "ST 인터록 생성",
    btnGenerating: "생성 중...",
    v3IoTableTitle: "PLC I/O 할당 테이블 (단자대·와이어 번호 동기화)",
    v3IoTableSub: "유형별 필터 및 신호명 검색으로 I/O 주소를 즉시 조회합니다.",
    v3StTitle: "기본 I/O 심볼 및 운전 프로그램 스캐폴드 (IEC 61131-3 ST)",
    v3StSub: "I/O 심볼 선언, 안전 인터록(SAFETY_OK), 운전 모드 및 타워램프 뼈대 코드",
    btnCopy: "코드 복사",
    btnCopied: "복사 완료",

    v4Title: "자동 합성 전기회로도 (IEC 61082 Multi-Sheet Schematic)",
    v4Sub: "회로 심볼을 클릭하면 SSOT 기기 사양을 하단 인스펙터에서 즉시 확인할 수 있습니다.",
    v4InspectorHint: "도면 위 차단기·인버터·모터·안전릴레이·PLC 핀을 클릭하면 연결된 SSOT 스펙이 표시됩니다.",
    v4TermTitle: "단자대 배열 및 와이어 넘버링 리스트 (-X1 동력 / -X2 제어·I/O)",
    btnTermCsv: "단자대·배선 CSV 다운로드",

    v5Title: "제어반 중판(Mounting Plate) 2D 자동 배치도",
    v5Sub: "강전/약전 물리적 분리(배선덕트 60mm) 및 인버터·서보 상/하부 100mm 방열 이격 자동 반영",
    btnEmcMode: "EMC 구역 배치",
    btnThermalMode: "열 분포 히트맵",
    v5InspectorHint: "배치도 위 부품을 클릭하면 정확한 좌표(X, Y mm), 외형 치수(W×H×D), 발열량(W)이 표시됩니다.",
    v5TableTitle: "중판 배치 좌표 및 외형 치수표 (Hole Machining Schedule)",
    v5TableSub: "EPLAN Pro Panel AML 및 1:1 mm AutoCAD DXF 좌표와 100% 동기화됩니다.",

    v6Title: "하이브리드 설계 검증 결과 (결정론적 ERC/DRC + AI 지식 리뷰)",
    v6Sub: "전기적 정합성·안전 규격은 결정론적 룰 엔진이 판정하고, 현장 트러블슈팅 사례는 AI 리뷰어가 보완합니다.",
    btnFatDownload: "FAT / SAT 시운전 체크시트 (.md)",
    lblAction: "조치 권고",

    v7SnapTitle: "프로젝트 리비전 스냅샷 발행 (ECN 기준선 저장)",
    v7SnapSub: "현재 SSOT 사양·BOM·I/O·검증 상태를 불변 스냅샷으로 저장하고 언제든 롤백·복원할 수 있습니다.",
    lblRevTag: "리비전 태그",
    lblRevStatus: "결재 상태",
    lblAuthor: "담당자",
    lblSummary: "변경 사유 (ECN 내용)",
    btnSaveRev: "리비전 스냅샷 저장",
    v7HistoryTitle: "프로젝트 리비전 이력 및 롤백 복원",
    v7HistorySub: "결재 상태를 변경하거나 이전 스냅샷 시점으로 설계를 원클릭 복원할 수 있습니다.",
    btnRestore: "복원",
    v7DiffTitle: "ECN 변경 영향도 비교 (Revision Diff)",
    v7DiffSub: "부하 변경, BOM 파트넘버/수량 변동, 자재비 및 PLC I/O 증감을 자동 대조합니다.",
    btnRunDiff: "Diff 비교",

    copilotTitle: "AI 사양 · RFP PDF → 제어반 설계 초안 생성",
    copilotSub: "고객사 RFP(PDF/TXT) 파일을 업로드하거나 자연어로 입력하면 부하·안전·I/O·회로도·중판 배치까지 자동 생성합니다.",
    copilotUploadTitle: "RFP 문서 업로드 (PDF / TXT / MD)",
    copilotUploadSub: "PDF 텍스트를 자동 추출하고 설정된 외부/로컬 LLM 또는 내장 엔진으로 사양을 구조화합니다.",
    btnParsePdf: "PDF 분석 생성",
    btnRunCopilot: "자연어 분석 및 프로젝트 생성",
    btnCancel: "취소",

    llmTitle: "외부 / 온프레미스 로컬 LLM 게이트웨이 설정",
    llmSub: "RFP PDF 파싱과 자연어 PLC 인터록 코드 생성에 사용할 AI 엔진을 선택합니다. (전기 계산은 항상 결정론적 엔진 유지)",
    btnTestLlm: "연결 테스트",
    btnSave: "설정 저장",

    updateTitle: "앱 버전 관리 · 자동 업데이트 · GitHub 커뮤니티",
    updateSub: "GitHub Releases에서 Windows/macOS/Linux/Android 최신 설치파일을 확인하고 Issue·Discussion으로 바로 이동합니다.",
    btnCheckNow: "지금 업데이트 확인",
    btnSaveUpdateCfg: "업데이트 설정 저장",

    lt_motor_inv: "인버터 모터 (VFD)",
    lt_motor_dol: "직입 모터 (DOL)",
    lt_servo: "AC 서보 축",
    lt_heater: "공정 히터",
    lt_solenoid_group: "솔레노이드 그룹 (24V)",
    lt_sensor_group: "센서 그룹 (24V)",
    lt_safety_circuit: "안전 회로 (E-Stop)",
  },
};

let currentLang = (() => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "ko" || saved === "en") return saved;
  } catch {
    // ignore storage errors
  }
  return "en"; // Default language: English
})();

export function getLang() {
  return currentLang;
}

export function setLang(lang) {
  currentLang = lang === "ko" ? "ko" : "en";
  try {
    localStorage.setItem(STORAGE_KEY, currentLang);
  } catch {
    // ignore
  }
  document.documentElement.lang = currentLang;
  document.title = t("pageTitle");
}

export function t(key) {
  return DICT[currentLang]?.[key] ?? DICT.en[key] ?? key;
}

export function applyStaticTranslations() {
  document.documentElement.lang = currentLang;
  document.title = t("pageTitle");
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (key) el.textContent = t(key);
  });
}
