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
  const thm = s.thermal_analysis;
  const selChecks = s.selectivity_checks || [];

  const coordBadge = (st) => {
    if (st === "TOTAL") return `<span class="sev-badge sev-INFO" style="background:var(--ok-bg);color:var(--ok-green)">TOTAL</span>`;
    if (st === "PARTIAL") return `<span class="sev-badge sev-WARNING">PARTIAL</span>`;
    return `<span class="sev-badge sev-ERROR">NON-SEL</span>`;
  };

  const selRows = selChecks
    .map(
      (sc) => `
      <tr>
        <td class="mono" style="font-weight:700">${sc.tag}</td>
        <td>${sc.name}</td>
        <td class="mono">${sc.upstream_part} (${sc.upstream_rating_a}AT)</td>
        <td class="mono">${sc.downstream_part} (${sc.downstream_rating_a}AT · Icu ${sc.downstream_icu_ka}kA)</td>
        <td class="num"><strong>${sc.ik3_branch_ka} kA</strong></td>
        <td class="num">${sc.selectivity_ratio}×</td>
        <td>${coordBadge(sc.coordination_status)}</td>
        <td>${sc.breaking_ok ? `<span class="sev-badge sev-INFO" style="background:var(--ok-bg);color:var(--ok-green)">Icu OK</span>` : `<span class="sev-badge sev-ERROR">Icu FAIL</span>`}</td>
        <td style="font-size:11.5px;color:var(--ink-secondary)">${sc.note}</td>
      </tr>`
    )
    .join("");

  const calcRows = calcs
    .map(
      (c) => `
      <tr>
        <td class="mono" style="font-weight:700">${c.tag}</td>
        <td>${c.name}</td>
        <td class="mono" style="font-size:11.5px">
          <a href="${api.exportEmaUrl(project.id, c.eplan_macro)}" style="color:var(--accent-blue);text-decoration:none" title="Download EPLAN Window Macro (.ema)">
            ${c.eplan_macro} <span class="tag-pill" style="font-size:10px;padding:1px 5px">Var ${c.eplan_macro_variant || "A"}</span>
          </a>
        </td>
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
        <td class="num">${b.quantity} ${b.unit && b.unit !== "EA" ? b.unit : ""}</td>
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
                <tr><td>${isKo ? "선정 주 차단기 (-Q0) / SCCR" : "Main MCCB (-Q0) / Panel SCCR"}</td><td class="num"><strong>${s.main_breaker_part}</strong> (${s.main_breaker_rating_a}AT · Icu ${s.main_breaker_icu_ka}kA)</td></tr>
                <tr><td>${isKo ? "IEC 60909 주모선 단락전류 (I''k3 / 피크 ip)" : "IEC 60909 Main Bus Fault (I''k3 / Peak ip)"}</td><td class="num"><strong>${s.ik3_main_ka} kA</strong> / ${s.ip_peak_ka} kA (Margin ${s.main_breaking_margin_pct}%)</td></tr>
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
              <h2 class="panel-title">${isKo ? "IEC 60890 정밀 열해석 · 냉각 용량 선정" : "IEC 60890 Precision Thermal & Cooling Analysis"}</h2>
              <p class="panel-subtitle">${isKo ? `주위온도 ${project.settings.ambient_temp_c}°C → 목표 ${project.settings.max_internal_temp_c}°C 이하` : `Ambient ${project.settings.ambient_temp_c}°C → Target ≤ ${project.settings.max_internal_temp_c}°C`}${thm ? ` · ${thm.install_type}` : ""}</p>
            </div>
            ${thm ? `<span class="tag-pill" style="background:${thm.cooling_mode === "PANEL_AC" ? "var(--warn-bg);color:var(--warn-amber)" : "var(--ok-bg);color:var(--ok-green)"}">${thm.cooling_mode}</span>` : ""}
          </div>
          <div class="panel-body">
            <table class="data-table">
              <tbody>
                <tr><td>${isKo ? "제어반 내부 총 발열량 (Q) / 자연방열 (P_nat)" : "Total Heat Loss (Q) / Natural Dissipation"}</td><td class="num"><strong>${s.total_heat_loss_w} W</strong> / ${thm ? `${thm.natural_dissipation_w} W (Ae ${thm.effective_surface_m2} m²)` : "-"}</td></tr>
                <tr><td>${isKo ? "미냉각 예상 온도 → 냉각 후 내부 온도" : "Predicted Uncooled → Cooled Internal Temp"}</td><td class="num">${thm ? `<span style="color:${thm.predicted_uncooled_temp_c > project.settings.max_internal_temp_c ? "var(--err-red)" : "var(--ok-green)"}">${thm.predicted_uncooled_temp_c}°C</span> → <strong style="color:var(--ok-green)">${thm.predicted_cooled_temp_c}°C</strong> (Δ+${thm.thermal_margin_c}K)` : "-"}</td></tr>
                <tr><td>${isKo ? "순 필요 냉각량 / 필요 환기 풍량" : "Net Cooling Required / Required Airflow"}</td><td class="num"><strong>${thm ? `${thm.net_cooling_required_w} W` : "-"}</strong> / ${s.cooling_required_m3h} m³/h</td></tr>
                <tr><td>${isKo ? "선정 냉각 장치 (BOM 자동 반영)" : "Selected Cooling Unit (Auto-BOM)"}</td><td class="num"><strong>${thm ? `${thm.recommended_cooling_part} (${thm.recommended_cooling_capacity_w}W)` : s.cooling_solution}</strong></td></tr>
                <tr><td>${isKo ? "추천 외함 규격 (W×H×D)" : "Enclosure Size (W×H×D)"}</td><td class="num"><strong>${s.enclosure_size_mm}</strong> (${s.enclosure_part})</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${isKo ? "IEC 60909 단락전류 및 주-분기 차단기 보호협조(Selectivity) 매트릭스" : "IEC 60909 Short-Circuit & Breaker Selectivity Coordination Matrix"}</h2>
            <p class="panel-subtitle">${isKo ? `전원변압기 ${project.settings.supply_transformer_kva}kVA (%Z ${project.settings.supply_impedance_pct}%, 간선 ${project.settings.feeder_length_m}m) · 주모선 I''k3 = ${s.ik3_main_ka}kA / ip = ${s.ip_peak_ka}kA / Ik1min = ${s.ik1_min_ka}kA` : `Supply Tx ${project.settings.supply_transformer_kva}kVA (%Z ${project.settings.supply_impedance_pct}%, Feeder ${project.settings.feeder_length_m}m) · Main I''k3 = ${s.ik3_main_ka}kA / ip = ${s.ip_peak_ka}kA / Ik1min = ${s.ik1_min_ka}kA`}</p>
          </div>
          <span class="tag-pill">${s.selectivity_summary || "VERIFIED"}</span>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>${isKo ? "태그" : "Tag"}</th>
                <th>${isKo ? "분기 회로" : "Branch Circuit"}</th>
                <th>${isKo ? "상위 주 차단기 (-Q0)" : "Upstream Main (-Q0)"}</th>
                <th>${isKo ? "하위 분기 차단기" : "Downstream Breaker"}</th>
                <th class="num">I''k3</th>
                <th class="num">${isKo ? "정격비" : "Ratio"}</th>
                <th>${isKo ? "협조 등급" : "Selectivity"}</th>
                <th>${isKo ? "차단용량" : "Icu Check"}</th>
                <th>${isKo ? "비고" : "Engineering Note"}</th>
              </tr>
            </thead>
            <tbody>${selRows || `<tr><td colspan="9" style="text-align:center;color:var(--ink-muted)">No AC power branches</td></tr>`}</tbody>
          </table>
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
            <a class="btn btn-secondary btn-sm" href="${api.exportEmaUrl(project.id)}">EPLAN .ema</a>
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
                <th>EPLAN Macro (.ema)</th>
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
