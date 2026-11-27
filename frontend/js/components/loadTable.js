/** View 01: Project Settings, Excel/CSV Load Schedule & Company Catalog Importer, and Load Editor */

import { api } from "../api.js";
import { getLang, t } from "../i18n.js";

const LOAD_TYPE_KEYS = ["motor_inv", "motor_dol", "servo", "heater", "solenoid_group", "sensor_group", "safety_circuit"];

function esc(val) {
  return String(val ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export async function renderLoadsView(container, design, onUpdateProject, onReloadDesign, showToast) {
  const { project, load_calculations } = design;
  const calcMap = new Map(load_calculations.map((c) => [c.unit_id, c]));
  const [customCatalog, macros, customMacros] = await Promise.all([
    api.listCustomCatalog(project.tenant_id),
    api.listMacros(),
    api.listCustomMacros(project.tenant_id),
  ]);
  const isKo = getLang() === "ko";
  const isUL = project.settings.standard_profile === "UL 508A";

  const rowsHtml = project.loads
    .map((u, idx) => {
      const calc = calcMap.get(u.id);
      const isPower = ["motor_dol", "motor_inv", "servo", "heater"].includes(u.load_type);
      const isSafety = u.load_type === "safety_circuit";
      const isSol = u.load_type === "solenoid_group";
      const isInv = u.load_type === "motor_inv";

      let optCell = '<span style="color:var(--ink-muted);font-size:12px">-</span>';
      if (isSafety) {
        optCell = `
          <select class="input-inline mono" data-field="safety_level" data-idx="${idx}">
            <option value="PLc" ${u.safety_level === "PLc" ? "selected" : ""}>PLc</option>
            <option value="PLd" ${(u.safety_level || "PLd") === "PLd" ? "selected" : ""}>PLd</option>
            <option value="PLe" ${u.safety_level === "PLe" ? "selected" : ""}>PLe</option>
          </select>`;
      } else if (isInv) {
        optCell = `
          <label style="font-size:12px;display:inline-flex;align-items:center;gap:4px;cursor:pointer">
            <input type="checkbox" data-field="has_emi_filter" data-idx="${idx}" ${u.has_emi_filter ? "checked" : ""}/>
            ${t("optEmi")}
          </label>`;
      } else if (isSol) {
        optCell = `
          <label style="font-size:12px;display:inline-flex;align-items:center;gap:4px;cursor:pointer">
            <input type="checkbox" data-field="has_surge_suppressor" data-idx="${idx}" ${u.has_surge_suppressor ? "checked" : ""}/>
            ${t("optSurge")}
          </label>`;
      }

      return `
        <tr>
          <td><input class="input-inline mono" data-field="tag" data-idx="${idx}" value="${esc(u.tag)}" style="width:105px;font-weight:700" /></td>
          <td><input class="input-inline" data-field="name" data-idx="${idx}" value="${esc(u.name)}" style="min-width:170px" /></td>
          <td>
            <select class="input-inline" data-field="load_type" data-idx="${idx}" style="min-width:140px">
              ${LOAD_TYPE_KEYS.map((k) => `<option value="${k}" ${u.load_type === k ? "selected" : ""}>${t("lt_" + k)}</option>`).join("")}
            </select>
          </td>
          <td class="num">
            ${
              isPower
                ? `<input class="input-inline num" type="number" step="0.1" min="0" data-field="power_kw" data-idx="${idx}" value="${u.power_kw}" style="width:72px" />`
                : '<span style="color:var(--ink-muted)">DC24V</span>'
            }
          </td>
          <td class="num"><input class="input-inline num" type="number" min="1" max="128" data-field="quantity" data-idx="${idx}" value="${u.quantity}" style="width:58px" /></td>
          <td class="num"><input class="input-inline num" type="number" min="1" max="200" data-field="cable_length_m" data-idx="${idx}" value="${u.cable_length_m}" style="width:60px" /></td>
          <td>${optCell}</td>
          <td class="num">${calc ? `${calc.rated_current_a} A` : "-"}</td>
          <td class="num">${calc ? (isUL ? `${calc.wire_sq}SQ / ${calc.wire_awg}` : `${calc.wire_sq} SQ`) : "-"}</td>
          <td class="num" title="${esc(calc?.formula_trace || "")}">${calc ? `${calc.breaker_rating_a}A` : "-"}</td>
          <td><button class="btn btn-danger-ghost" data-remove="${idx}" type="button">${t("btnDelete")}</button></td>
        </tr>`;
    })
    .join("");

  const catalogListHtml = customCatalog.length
    ? `
      <div class="table-wrap" style="margin-top:10px;max-height:190px;overflow-y:auto">
        <table class="data-table">
          <thead>
            <tr>
              <th>${isKo ? "분류" : "Category"}</th>
              <th>${isKo ? "제조사" : "Manufacturer"}</th>
              <th>${isKo ? "사내 표준 파트넘버" : "Part Number"}</th>
              <th class="num">${isKo ? "정격" : "Rating"}</th>
              <th>${isKo ? "사양" : "Spec"}</th>
              <th class="num">${isKo ? "단가" : "Unit Price"}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            ${customCatalog
              .map(
                (it) => `
              <tr>
                <td><span class="tag-pill">${esc(it.category)}</span></td>
                <td>${esc(it.manufacturer)}</td>
                <td class="mono" style="font-weight:700;color:var(--ok-green)">${esc(it.part_number)}</td>
                <td class="num">${it.rated_value} ${it.category === "INVERTER" || it.category === "SERVO" ? "kW" : "A"}</td>
                <td>${esc(it.spec)}</td>
                <td class="num">₩${Number(it.unit_price_krw).toLocaleString()}</td>
                <td><button class="btn btn-danger-ghost" data-del-cat="${esc(it.id)}" type="button">${t("btnDelete")}</button></td>
              </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>`
    : `<p style="margin:8px 0 0;font-size:12px;color:var(--ink-muted)">${t("catEmpty")}</p>`;

  const customMacrosHtml = customMacros.length
    ? `
      <div class="table-wrap" style="margin-top:10px">
        <table class="data-table">
          <thead>
            <tr>
              <th>${isKo ? "코드" : "Code"}</th>
              <th>${isKo ? "적용 부하유형" : "Target Load Type"}</th>
              <th>EPLAN .ema ${isKo ? "파일 경로" : "Path"}</th>
              <th>${isKo ? "변형/유형" : "Variant / Type"}</th>
              <th>${isKo ? "설명" : "Template Name"}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            ${customMacros
              .map(
                (cm) => `
              <tr>
                <td class="mono" style="font-weight:700">${esc(cm.macro_code)}</td>
                <td><span class="tag-pill">${esc(t("lt_" + cm.target_load_type))}</span></td>
                <td class="mono" style="font-size:11.5px;color:var(--accent-blue)">${esc(cm.eplan_file)}</td>
                <td class="mono">Var ${esc(cm.variant)} · ${esc(cm.representation_type)}</td>
                <td>${esc(cm.name)}</td>
                <td style="white-space:nowrap">
                  <a class="btn btn-secondary btn-sm" href="${api.exportEmaUrl(project.id, cm.eplan_file)}" style="margin-right:4px">.ema XML</a>
                  <button class="btn btn-danger-ghost" data-del-macro="${esc(cm.id)}" type="button">${t("btnDelete")}</button>
                </td>
              </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>`
    : `<p style="margin:8px 0 0;font-size:12px;color:var(--ink-muted)">${isKo ? "등록된 사내 커스텀 .ema 매크로가 없습니다. 아래에서 등록하면 해당 부하유형의 EPLAN AML / 회로도 / .ema XML에 자동 매핑됩니다." : "No company custom .ema overrides yet. Add one below to override default EPLAN macro mappings across AML, schematics, and .ema XML exports."}</p>`;

  container.innerHTML = `
    <div class="stack-gap">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${t("v1ProfileTitle")}</h2>
            <p class="panel-subtitle">${t("v1ProfileSub")}</p>
          </div>
          <span class="tag-pill">${esc(project.id)}</span>
        </div>
        <div class="panel-body">
          <div class="settings-grid">
            <div class="field-group">
              <label class="field-label" for="inpProjName">${t("lblProjectName")}</label>
              <input id="inpProjName" class="input" value="${esc(project.name)}" />
            </div>
            <div class="field-group">
              <label class="field-label" for="inpClient">${t("lblClient")}</label>
              <input id="inpClient" class="input" value="${esc(project.client)}" />
            </div>
            <div class="field-group">
              <label class="field-label" for="selStandard">${t("lblStandard")}</label>
              <select id="selStandard" class="input">
                ${["IEC 60204-1", "KS C IEC 60364", "UL 508A"]
                  .map((s) => `<option value="${s}" ${project.settings.standard_profile === s ? "selected" : ""}>${s}</option>`)
                  .join("")}
              </select>
            </div>
            <div class="field-group">
              <label class="field-label" for="selPowerSys">${t("lblPowerSys")}</label>
              <select id="selPowerSys" class="input">
                <option value="3P_380V_60Hz" ${project.settings.power_system === "3P_380V_60Hz" ? "selected" : ""}>3P 380V 60Hz</option>
                <option value="3P_440V_60Hz" ${project.settings.power_system === "3P_440V_60Hz" ? "selected" : ""}>3P 440V 60Hz</option>
                <option value="3P_480V_60Hz" ${project.settings.power_system === "3P_480V_60Hz" ? "selected" : ""}>3P 480V 60Hz (UL 508A)</option>
                <option value="3P_220V_60Hz" ${project.settings.power_system === "3P_220V_60Hz" ? "selected" : ""}>3P 220V 60Hz</option>
                <option value="1P_220V_60Hz" ${project.settings.power_system === "1P_220V_60Hz" ? "selected" : ""}>1P 220V 60Hz</option>
              </select>
            </div>
            <div class="field-group">
              <label class="field-label" for="inpAmbient">${t("lblAmbient")}</label>
              <input id="inpAmbient" class="input mono" type="number" min="15" max="50" value="${project.settings.ambient_temp_c}" />
            </div>
            <div class="field-group">
              <label class="field-label" for="inpSpare">${t("lblSpare")}</label>
              <input id="inpSpare" class="input mono" type="number" min="0" max="50" step="5" value="${Math.round(project.settings.io_spare_ratio * 100)}" />
            </div>
            <div class="field-group">
              <label class="field-label" for="inpTxKva">${isKo ? "수전 변압기 (kVA · IEC 60909)" : "Supply Tx (kVA · IEC 60909)"}</label>
              <input id="inpTxKva" class="input mono" type="number" min="50" max="5000" step="50" value="${project.settings.supply_transformer_kva || 500}" />
            </div>
            <div class="field-group">
              <label class="field-label" for="inpTxZ">${isKo ? "변압기 %Z / 간선(m)" : "Tx %Z / Feeder (m)"}</label>
              <div style="display:flex;gap:6px">
                <input id="inpTxZ" class="input mono" type="number" min="2" max="12" step="0.5" value="${project.settings.supply_impedance_pct || 4.5}" style="width:50%" title="Transformer %Z" />
                <input id="inpFeederM" class="input mono" type="number" min="1" max="500" step="5" value="${project.settings.feeder_length_m || 25}" style="width:50%" title="Main Feeder Length (m)" />
              </div>
            </div>
            <div class="field-group">
              <label class="field-label" for="selInstallType">${isKo ? "외함 설치형태 (IEC 60890)" : "Enclosure Install (IEC 60890)"}</label>
              <select id="selInstallType" class="input">
                <option value="freestanding_all_open" ${(project.settings.enclosure_install_type || "freestanding_all_open") === "freestanding_all_open" ? "selected" : ""}>${isKo ? "자립형 (사방 개방)" : "Freestanding (All Sides Open)"}</option>
                <option value="wall_mounted" ${project.settings.enclosure_install_type === "wall_mounted" ? "selected" : ""}>${isKo ? "벽부형 (후면 밀착)" : "Wall-Mounted (Rear Covered)"}</option>
                <option value="bayed_side_by_side" ${project.settings.enclosure_install_type === "bayed_side_by_side" ? "selected" : ""}>${isKo ? "열반 연립형 (측면 밀착)" : "Bayed Side-by-Side"}</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div class="grid-2">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">${t("v1ImportLoadsTitle")}</h2>
              <p class="panel-subtitle">${t("v1ImportLoadsSub")}</p>
            </div>
            <a class="btn btn-secondary btn-sm" href="${api.templateUrl("loads_csv")}">${t("btnLoadTpl")}</a>
          </div>
          <div class="panel-body">
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
              <input id="inpLoadsFile" type="file" accept=".xlsx,.csv" style="flex:1;min-width:170px;font-size:12px" />
              <select id="selImportMode" class="input" style="width:120px">
                <option value="replace">${t("optReplace")}</option>
                <option value="append">${t("optAppend")}</option>
              </select>
              <button id="btnUploadLoads" class="btn btn-primary btn-sm" type="button">${t("btnImportLoads")}</button>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">${t("v1CatalogTitle")}</h2>
              <p class="panel-subtitle">${t("v1CatalogSubPrefix")} <strong>${customCatalog.length}</strong> (MCCB · MC · VFD · Servo · SMPS)</p>
            </div>
            <div style="display:flex;gap:6px">
              <a class="btn btn-secondary btn-sm" href="${api.templateUrl("catalog_csv")}">${t("btnCatTpl")}</a>
              ${customCatalog.length ? `<button id="btnClearCatalog" class="btn btn-danger-ghost" type="button">${t("btnReset")}</button>` : ""}
            </div>
          </div>
          <div class="panel-body">
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
              <input id="inpCatalogFile" type="file" accept=".xlsx,.csv" style="flex:1;min-width:170px;font-size:12px" />
              <button id="btnUploadCatalog" class="btn btn-primary btn-sm" type="button">${t("btnImportCat")}</button>
            </div>
            ${catalogListHtml}
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${isKo ? "표준 EPLAN 회로 매크로 라이브러리 (1-Click 모듈 조립)" : "Standard EPLAN Circuit Macro Library (1-Click Module Assembly)"}</h2>
            <p class="panel-subtitle">${isKo ? "검증된 표준 전장·제어 모듈(.ema)을 클릭해 부하·I/O·BOM·회로도를 즉시 조립합니다." : "Insert standardized EPLAN circuit macros (.ema) with pre-configured protection, I/O, and BOM specs."}</p>
          </div>
          <span class="tag-pill">${macros.length} ${isKo ? "개 표준 매크로" : "Standard Macros"}</span>
        </div>
        <div class="panel-body">
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px">
            ${macros
              .map(
                (m) => `
              <div style="border:1px solid var(--border-subtle);border-radius:var(--radius-sm);padding:10px 12px;background:var(--bg-subtle);display:flex;flex-direction:column;gap:6px">
                <div style="display:flex;justify-content:space-between;align-items:center;gap:6px">
                  <span class="tag-pill">${esc(m.category)}</span>
                  <span class="mono" style="font-size:10.5px;color:var(--accent-blue)">${esc(m.eplan_file)}</span>
                </div>
                <strong style="font-size:13px">${esc(isKo ? m.name_ko : m.name_en)}</strong>
                <span style="font-size:11.5px;color:var(--ink-secondary);flex:1">${esc(isKo ? m.description_ko : m.description_en)}</span>
                <button class="btn btn-secondary btn-sm" data-apply-macro="${esc(m.macro_id)}" type="button">+ ${isKo ? "프로젝트에 삽입" : "Insert Macro"}</button>
              </div>`
              )
              .join("")}
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${isKo ? "사내 EPLAN Electric P8 .ema 매크로 템플릿 에디터" : "Company EPLAN Electric P8 .ema Macro Library Editor"}</h2>
            <p class="panel-subtitle">${isKo ? "제조사/조직별 사내 표준 .ema 파일 경로, Variant(A~P), Placeholder 변수 매핑을 관리하고 EPLAN용 .ema XML을 즉시 생성합니다." : "Map company-standard .ema macro paths, Variants (A–P), and Placeholder variables for EPLAN AML & .ema XML generation."}</p>
          </div>
          <a class="btn btn-secondary btn-sm" href="${api.exportEmaUrl(project.id)}">${isKo ? "현재 프로젝트 .ema 다운로드" : "Download .ema XML"}</a>
        </div>
        <div class="panel-body">
          <div style="display:grid;grid-template-columns:120px 150px 1fr 80px 160px auto;gap:8px;align-items:end">
            <div class="field-group">
              <label class="field-label" for="emaCode">${isKo ? "매크로 코드" : "Macro Code"}</label>
              <input id="emaCode" class="input mono" placeholder="STD-VFD-01" />
            </div>
            <div class="field-group">
              <label class="field-label" for="emaLoadType">${isKo ? "대상 부하유형" : "Load Type"}</label>
              <select id="emaLoadType" class="input">
                ${LOAD_TYPE_KEYS.map((k) => `<option value="${k}">${t("lt_" + k)}</option>`).join("")}
              </select>
            </div>
            <div class="field-group">
              <label class="field-label" for="emaFile">EPLAN .ema ${isKo ? "파일명/경로" : "File Path"}</label>
              <input id="emaFile" class="input mono" placeholder="$(MD_MACROS)\\Company\\VFD_3P_v2.ema" />
            </div>
            <div class="field-group">
              <label class="field-label" for="emaVar">Variant</label>
              <select id="emaVar" class="input mono">
                ${["A", "B", "C", "D", "E", "F"].map((v) => `<option value="${v}">${v}</option>`).join("")}
              </select>
            </div>
            <div class="field-group">
              <label class="field-label" for="emaName">${isKo ? "템플릿명" : "Template Name"}</label>
              <input id="emaName" class="input" placeholder="Company VFD Standard" />
            </div>
            <button id="btnSaveCustomMacro" class="btn btn-primary btn-sm" type="button">${isKo ? "매크로 저장" : "Save .ema"}</button>
          </div>
          ${customMacrosHtml}
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${t("v1LoadListTitle")}</h2>
            <p class="panel-subtitle">${t("v1LoadListSub")}</p>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button id="btnAddMotorInv" class="btn btn-secondary btn-sm" type="button">${t("btnAddInv")}</button>
            <button id="btnAddServo" class="btn btn-secondary btn-sm" type="button">${t("btnAddServo")}</button>
            <button id="btnAddHeater" class="btn btn-secondary btn-sm" type="button">${t("btnAddHeater")}</button>
            <button id="btnAddSolenoid" class="btn btn-secondary btn-sm" type="button">${t("btnAddSol")}</button>
            <button id="btnAddSafety" class="btn btn-secondary btn-sm" type="button">${t("btnAddSafety")}</button>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>${t("thTag")}</th>
                <th>${t("thName")}</th>
                <th>${t("thType")}</th>
                <th class="num">${t("thKw")}</th>
                <th class="num">${t("thQty")}</th>
                <th class="num">${t("thCable")}</th>
                <th>${t("thOptions")}</th>
                <th class="num">${t("thRatedA")}</th>
                <th class="num">${t("thWireSq")}</th>
                <th class="num">${t("thBreaker")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>${rowsHtml}</tbody>
          </table>
        </div>
      </div>
    </div>
  `;

  const commitSettings = () => {
    const next = structuredClone(project);
    next.name = container.querySelector("#inpProjName").value.trim() || next.name;
    next.client = container.querySelector("#inpClient").value.trim();
    next.settings.standard_profile = container.querySelector("#selStandard").value;
    next.settings.power_system = container.querySelector("#selPowerSys").value;
    next.settings.ambient_temp_c = Number(container.querySelector("#inpAmbient").value) || 35;
    next.settings.io_spare_ratio = Math.max(0, Math.min(0.5, (Number(container.querySelector("#inpSpare").value) || 20) / 100));
    next.settings.supply_transformer_kva = Math.max(50, Number(container.querySelector("#inpTxKva").value) || 500);
    next.settings.supply_impedance_pct = Math.max(2, Math.min(12, Number(container.querySelector("#inpTxZ").value) || 4.5));
    next.settings.feeder_length_m = Math.max(1, Number(container.querySelector("#inpFeederM").value) || 25);
    next.settings.enclosure_install_type = container.querySelector("#selInstallType").value;
    onUpdateProject(next);
  };

  ["#inpProjName", "#inpClient", "#selStandard", "#selPowerSys", "#inpAmbient", "#inpSpare", "#inpTxKva", "#inpTxZ", "#inpFeederM", "#selInstallType"].forEach((sel) => {
    container.querySelector(sel).addEventListener("change", commitSettings);
  });

  container.querySelector("#btnSaveCustomMacro").addEventListener("click", async () => {
    const macro_code = container.querySelector("#emaCode").value.trim();
    const eplan_file = container.querySelector("#emaFile").value.trim();
    const target_load_type = container.querySelector("#emaLoadType").value;
    const variant = container.querySelector("#emaVar").value;
    const name = container.querySelector("#emaName").value.trim() || `${macro_code} (${target_load_type})`;
    if (!macro_code || !eplan_file) {
      showToast(isKo ? "매크로 코드와 .ema 파일 경로를 입력하세요." : "Enter both Macro Code and EPLAN .ema file path.");
      return;
    }
    try {
      await api.saveCustomMacro({
        tenant_id: project.tenant_id,
        macro_code,
        eplan_file,
        variant,
        representation_type: "Multi-line",
        target_load_type,
        name,
        description: `Company template mapped to ${target_load_type}`,
        placeholder_vars: {
          "<DeviceTag>": "{iec_device_tag}",
          "<MCCB_Part>": "{breaker_part}",
          "<Drive_or_MC>": "{drive_or_mc}",
          "<Wire_SQ>": "{wire_sq}",
        },
      });
      showToast(isKo ? `사내 EPLAN 매크로 ${macro_code} 저장 완료` : `Saved company EPLAN macro ${macro_code} (Var ${variant})`);
      await onReloadDesign();
    } catch (err) {
      showToast(err.message);
    }
  });

  container.querySelectorAll("[data-del-macro]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await api.deleteCustomMacro(btn.dataset.delMacro);
        showToast(isKo ? "사내 매크로 매핑을 삭제했습니다." : "Deleted custom EPLAN macro mapping.");
        await onReloadDesign();
      } catch (err) {
        showToast(err.message);
      }
    });
  });

  container.querySelector("#btnUploadLoads").addEventListener("click", async () => {
    const file = container.querySelector("#inpLoadsFile").files?.[0];
    if (!file) {
      showToast(isKo ? "Excel(.xlsx) 또는 CSV 부하표 파일을 선택하세요." : "Please select an Excel (.xlsx) or CSV load schedule file.");
      return;
    }
    try {
      const mode = container.querySelector("#selImportMode").value;
      const res = await api.importLoadsFile(project.id, file, mode);
      showToast(isKo ? `부하표 임포트 완료 (${res.imported_count}개 유닛)` : `Imported ${res.imported_count} load units.`);
      await onReloadDesign(res.design);
    } catch (err) {
      showToast(err.message);
    }
  });

  container.querySelector("#btnUploadCatalog").addEventListener("click", async () => {
    const file = container.querySelector("#inpCatalogFile").files?.[0];
    if (!file) {
      showToast(isKo ? "사내 부품 DB(.xlsx/.csv) 파일을 선택하세요." : "Please select a company catalog (.xlsx/.csv) file.");
      return;
    }
    try {
      const res = await api.importCatalogFile(file, project.tenant_id);
      showToast(isKo ? `사내 부품 DB ${res.imported_count}건 등록 완료` : `Registered ${res.imported_count} custom catalog items.`);
      await onReloadDesign();
    } catch (err) {
      showToast(err.message);
    }
  });

  const btnClear = container.querySelector("#btnClearCatalog");
  if (btnClear) {
    btnClear.addEventListener("click", async () => {
      await api.deleteCustomCatalogItem("__ALL__", project.tenant_id);
      showToast(isKo ? "사내 부품 DB를 초기화했습니다." : "Cleared custom company catalog.");
      await onReloadDesign();
    });
  }

  container.querySelectorAll("[data-del-cat]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api.deleteCustomCatalogItem(btn.dataset.delCat);
      await onReloadDesign();
    });
  });

  // 1-Click Standard EPLAN Macro insertion
  container.querySelectorAll("[data-apply-macro]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const macroId = btn.dataset.applyMacro;
      try {
        const updatedDesign = await api.applyMacro(project.id, macroId);
        showToast(isKo ? `표준 매크로 ${macroId} 삽입 완료 (회로도·BOM·I/O 자동 갱신)` : `Inserted macro ${macroId} — BOM, I/O & schematics updated.`);
        await onReloadDesign(updatedDesign);
      } catch (err) {
        showToast(err.message);
      }
    });
  });

  container.querySelectorAll("[data-field]").forEach((el) => {
    el.addEventListener("change", () => {
      const idx = Number(el.dataset.idx);
      const field = el.dataset.field;
      const next = structuredClone(project);
      const item = next.loads[idx];
      if (!item) return;

      if (el.type === "checkbox") item[field] = el.checked;
      else if (field === "power_kw" || field === "cable_length_m") item[field] = Math.max(0, Number(el.value) || 0);
      else if (field === "quantity") item[field] = Math.max(1, parseInt(el.value, 10) || 1);
      else {
        item[field] = el.value;
        if (field === "load_type") {
          if (["solenoid_group", "sensor_group", "safety_circuit"].includes(el.value)) {
            item.power_kw = 0; item.voltage = 24; item.phases = 0;
            if (el.value === "safety_circuit" && !item.safety_level) item.safety_level = "PLd";
          } else if (el.value === "servo") {
            item.power_kw = item.power_kw || 0.75; item.voltage = 220; item.phases = 1;
          } else {
            item.power_kw = item.power_kw || 1.5; item.voltage = 380; item.phases = 3;
          }
        }
      }
      onUpdateProject(next);
    });
  });

  container.querySelectorAll("[data-remove]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = structuredClone(project);
      next.loads.splice(Number(btn.dataset.remove), 1);
      onUpdateProject(next);
    });
  });

  const addPreset = (preset) => {
    const next = structuredClone(project);
    next.loads.push({
      id: `u_${Date.now().toString(36)}_${next.loads.length + 1}`,
      cable_length_m: 15, power_factor: 0.85, efficiency: 0.88, demand_factor: 0.85,
      has_surge_suppressor: true, has_emi_filter: true, notes: "",
      ...preset,
    });
    onUpdateProject(next);
  };

  container.querySelector("#btnAddMotorInv").addEventListener("click", () =>
    addPreset({ tag: `INV_${project.loads.length + 1}`, name: isKo ? "신규 컨베이어 인버터" : "Conveyor VFD Motor", load_type: "motor_inv", power_kw: 1.5, quantity: 1, voltage: 380, phases: 3 })
  );
  container.querySelector("#btnAddServo").addEventListener("click", () =>
    addPreset({ tag: `SRV_${project.loads.length + 1}`, name: isKo ? "신규 AC 서보 축" : "AC Servo Axis", load_type: "servo", power_kw: 0.75, quantity: 1, voltage: 220, phases: 1 })
  );
  container.querySelector("#btnAddHeater").addEventListener("click", () =>
    addPreset({ tag: `HTR_${project.loads.length + 1}`, name: isKo ? "신규 공정 히터" : "Process Heater Zone", load_type: "heater", power_kw: 3.0, quantity: 1, voltage: 380, phases: 3, power_factor: 1.0, efficiency: 1.0 })
  );
  container.querySelector("#btnAddSolenoid").addEventListener("click", () =>
    addPreset({ tag: `SOL_${project.loads.length + 1}`, name: isKo ? "신규 솔레노이드 그룹" : "Pneumatic Solenoid Group", load_type: "solenoid_group", power_kw: 0, quantity: 8, voltage: 24, phases: 0 })
  );
  container.querySelector("#btnAddSafety").addEventListener("click", () =>
    addPreset({ tag: "SAFETY_01", name: isKo ? "비상정지 안전 회로" : "E-Stop Safety Circuit", load_type: "safety_circuit", power_kw: 0, quantity: 2, voltage: 24, phases: 0, safety_level: "PLd" })
  );
}
