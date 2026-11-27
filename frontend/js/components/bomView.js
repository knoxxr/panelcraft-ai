/** View 02: Deterministic Capacity Calculations, Thermal Sizing & Synchronized Vendor BOM */

import { api } from "../api.js";
import { getLang, t } from "../i18n.js";

function won(n) {
  return `₩${Number(n || 0).toLocaleString()}`;
}

export function renderBomView(container, design) {
  const { project, power_summary: s, load_calculations: calcs, bom, bom_total_krw } = design;
  const smpsPct = Math.round((s.total_dc24v_current_a / Math.max(s.smps_capacity_a, 0.1)) * 100);
  const isKo = getLang() === "ko";

  const calcRows = calcs
    .map(
      (c) => `
      <tr>
        <td class="mono" style="font-weight:700">${c.tag}</td>
        <td>${c.name}</td>
        <td class="mono" style="font-size:11.5px;color:var(--accent-blue)">${c.eplan_macro}</td>
        <td class="num">${c.rated_current_a} A</td>
        <td class="num">${c.starting_current_a} A</td>
        <td class="num">${project.settings.standard_profile === "UL 508A" ? `${c.wire_sq}SQ / ${c.wire_awg}` : `${c.wire_sq} SQ`}</td>
        <td class="num" style="color:${c.voltage_drop_pct > 3 ? "var(--err-red)" : "var(--ok-green)"}">${c.voltage_drop_pct}%</td>
        <td class="mono">${c.breaker_part} (${c.breaker_icu_ka}kA)</td>
        <td class="num">${c.heat_loss_w} W</td>
        <td class="mono" style="font-size:11.5px;color:var(--ink-secondary)">${c.formula_trace}</td>
      </tr>`
    )
    .join("");

  const bomRows = bom
    .map(
      (b) => `
      <tr>
        <td class="num">${b.line_no}</td>
        <td><strong>${b.category}</strong></td>
        <td class="mono" style="font-size:12px">${b.iec_tags.join(", ")}</td>
        <td>${b.manufacturer}</td>
        <td class="mono" style="font-weight:700;color:${b.lifecycle_status.includes("사내표준") ? "var(--ok-green)" : "var(--accent-blue)"}">
          ${b.part_number}
          ${b.lifecycle_status.includes("사내표준") ? `<span class="sev-badge sev-INFO" style="margin-left:4px">${isKo ? "사내DB" : "CUSTOM"}</span>` : ""}
        </td>
        <td>${b.spec}</td>
        <td class="num">${b.quantity}</td>
        <td class="num">${won(b.unit_price_krw)}</td>
        <td class="num">${won(b.total_price_krw)}</td>
        <td class="num">${b.lead_time_days}${isKo ? "일" : "d"}</td>
      </tr>`
    )
    .join("");

  container.innerHTML = `
    <div class="stack-gap">
      <div class="grid-2">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">${t("v2PowerTitle")}</h2>
              <p class="panel-subtitle">${t("v2PowerSub")} (${project.settings.standard_profile} · SCCR ${s.panel_sccr_ka}kA)</p>
            </div>
          </div>
          <div class="panel-body">
            <table class="data-table">
              <tbody>
                <tr><td>${isKo ? "설비 총 연결 / 수용 용량" : "Connected / Demand Power"}</td><td class="num"><strong>${s.total_connected_kw} kW</strong> / ${s.total_demand_kw} kW</td></tr>
                <tr><td>${isKo ? "주전원 정격 / 수용 전류" : "Rated / Demand Current"}</td><td class="num">${s.total_rated_current_a} A / <strong>${s.total_demand_current_a} A</strong></td></tr>
                <tr><td>${isKo ? "선정 주 차단기 (-Q0) / SCCR" : "Main MCCB (-Q0) / Panel SCCR"}</td><td class="num"><strong>${s.main_breaker_part}</strong> (${s.main_breaker_rating_a}AT · ${s.panel_sccr_ka}kA)</td></tr>
                <tr><td>${isKo ? "주 인입 케이블 (SQ / AWG)" : "Main Feeder Cable (SQ / AWG)"}</td><td class="num"><strong>${s.main_wire_sq} mm² (${s.main_wire_awg})</strong></td></tr>
                <tr><td>${isKo ? "강압 변압기 (-T1)" : "Step-Down Transformer (-T1)"}</td><td class="num">${s.transformer_part ? `<strong>${s.transformer_part} (${s.transformer_kva}kVA)</strong>` : (isKo ? "불필요 (직결)" : "Not Required")}</td></tr>
                <tr><td>${isKo ? "DC 24V 제어전원 부하 / SMPS" : "DC 24V Load / SMPS"}</td><td class="num">${s.total_dc24v_current_a} A / <strong>${s.smps_selected_part} (${s.smps_capacity_a}A, ${smpsPct}%)</strong></td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">${t("v2ThermalTitle")}</h2>
              <p class="panel-subtitle">${isKo ? `주위온도 ${project.settings.ambient_temp_c}°C → 내부 목표 ${project.settings.max_internal_temp_c}°C 이하` : `Ambient ${project.settings.ambient_temp_c}°C → Max Internal ${project.settings.max_internal_temp_c}°C`}</p>
            </div>
          </div>
          <div class="panel-body">
            <table class="data-table">
              <tbody>
                <tr><td>${isKo ? "제어반 내부 총 발열량 (Q)" : "Total Internal Heat Loss (Q)"}</td><td class="num"><strong>${s.total_heat_loss_w} W</strong></td></tr>
                <tr><td>${isKo ? "필요 환기 풍량" : "Required Cooling Airflow"}</td><td class="num"><strong>${s.cooling_required_m3h} m³/h</strong></td></tr>
                <tr><td>${isKo ? "자동 선정 냉각 솔루션" : "Cooling Solution"}</td><td class="num">${s.cooling_solution}</td></tr>
                <tr><td>${isKo ? "추천 외함 규격 (W×H×D)" : "Enclosure Size (W×H×D)"}</td><td class="num"><strong>${s.enclosure_size_mm}</strong></td></tr>
                <tr><td>${isKo ? "선정 외함 파트넘버" : "Enclosure Part Number"}</td><td class="num">${s.enclosure_part}</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${t("v2BomTitle")} — ${project.settings.preferred_vendor}</h2>
            <p class="panel-subtitle">${t("v2BomSub")}</p>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <a class="btn btn-secondary btn-sm" href="${api.exportUrl(project.id, "dossier_html")}" target="_blank" rel="noopener">${isKo ? "계산서 인쇄 (HTML)" : "Print Dossier"}</a>
            <a class="btn btn-secondary btn-sm" href="${api.exportUrl(project.id, "eplan_aml")}">EPLAN AML</a>
            <a class="btn btn-secondary btn-sm" href="${api.exportUrl(project.id, "bom_csv")}">${t("btnDownloadBom")}</a>
            <a class="btn btn-primary btn-sm" href="${api.exportUrl(project.id, "package_zip")}">${isKo ? "전체 패키지 ZIP" : "Full Package ZIP"}</a>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th class="num">#</th>
                <th>${isKo ? "품목 분류" : "Category"}</th>
                <th>${isKo ? "IEC 태그" : "IEC Tags"}</th>
                <th>${isKo ? "제조사" : "Manufacturer"}</th>
                <th>${isKo ? "파트넘버" : "Part Number"}</th>
                <th>${isKo ? "규격 / 사양" : "Specification"}</th>
                <th class="num">${isKo ? "수량" : "Qty"}</th>
                <th class="num">${isKo ? "단가" : "Unit Price"}</th>
                <th class="num">${isKo ? "합계" : "Total"}</th>
                <th class="num">${isKo ? "납기" : "Lead"}</th>
              </tr>
            </thead>
            <tbody>
              ${bomRows}
              <tr class="total-row">
                <td colspan="8" style="text-align:right">${t("bomTotalLabel")}</td>
                <td class="num" style="color:var(--accent-blue);font-size:15px">${won(bom_total_krw)}</td>
                <td></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${t("v2AuditTitle")}</h2>
            <p class="panel-subtitle">${t("v2AuditSub")}</p>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>${isKo ? "태그" : "Tag"}</th>
                <th>${isKo ? "유닛명" : "Unit"}</th>
                <th>EPLAN Macro</th>
                <th class="num">${isKo ? "정격" : "Rated"}</th>
                <th class="num">${isKo ? "기동" : "Start"}</th>
                <th class="num">${isKo ? "전선" : "Wire"}</th>
                <th class="num">${isKo ? "전압강하" : "ΔV"}</th>
                <th>${isKo ? "차단기" : "Breaker"}</th>
                <th class="num">${isKo ? "발열" : "Heat"}</th>
                <th>${isKo ? "적용 수식" : "Formula Trace"}</th>
              </tr>
            </thead>
            <tbody>${calcRows}</tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}
