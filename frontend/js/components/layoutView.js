/** View 05: Interactive Drag-and-Drop 2D Control Panel Mounting Plate Layout, Collision Check & Wire Duct Routing */

import { api } from "../api.js";
import { getLang, t } from "../i18n.js";

let thermalMode = false;
let layoutZoom = 1.0;

function won(n) {
  return `₩${Number(n || 0).toLocaleString()}`;
}

export function renderLayoutView(container, design, onReloadDesign, showToast) {
  const { project, panel_layout: layout, power_summary: s } = design;
  const activeSvg = thermalMode ? layout.svg_thermal : layout.svg;
  const isKo = getLang() === "ko";
  const hasOverrides = Object.keys(project.layout_overrides || {}).length > 0;
  const issues = layout.layout_issues || [];
  const wireList = layout.wire_length_summary || [];

  const ZONE_LABELS = isKo
    ? { POWER: "Zone 1 · 강전/차단기", DRIVE: "Zone 2 · 인버터/서보", CONTROL: "Zone 3 · 약전/PLC/안전", TERMINAL: "Zone 4 · 하부 단자대" }
    : { POWER: "Zone 1 · Power / MCCB", DRIVE: "Zone 2 · VFD / Servo", CONTROL: "Zone 3 · Control / PLC", TERMINAL: "Zone 4 · Terminals" };

  const issuesHtml = issues.length
    ? `<div style="display:flex;flex-direction:column;gap:6px">
        ${issues
          .map(
            (iss) => `
          <div style="display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:var(--radius-sm);background:${iss.severity === "ERROR" ? "var(--err-red-soft)" : "var(--warn-amber-soft)"};border:1px solid ${iss.severity === "ERROR" ? "#fca5a5" : "#fcd34d"};font-size:12.5px">
            <span class="sev-badge sev-${iss.severity}">${iss.code}</span>
            <strong>${iss.targets.join(" ↔ ")}</strong>
            <span>${iss.message}</span>
          </div>`
          )
          .join("")}
       </div>`
    : `<div style="padding:8px 12px;border-radius:var(--radius-sm);background:var(--ok-green-soft);border:1px solid #a7f3d0;color:var(--ok-green);font-size:12.5px;font-weight:600">
        ✓ ${isKo ? "물리적 충돌 없음 · 중판 경계 및 100mm 방열 이격거리 정상 (드래그하여 부품을 자유롭게 이동할 수 있습니다)" : "Zero collisions · Mounting plate bounds & thermal clearance verified (Drag any component directly on the plate to reposition)"}
       </div>`;

  const wireRows = wireList
    .map(
      (w) => `
      <tr>
        <td class="mono" style="font-weight:700">${w.wire_sq} SQ (${w.wire_awg})</td>
        <td>${w.purpose}</td>
        <td class="num">${w.route_count}</td>
        <td class="num" style="font-weight:700;color:var(--accent-blue)">${w.total_length_m} m</td>
        <td class="num">${won(w.unit_price_per_m_krw)}/m</td>
        <td class="num">${won(w.total_price_krw)}</td>
      </tr>`
    )
    .join("");

  const compRows = layout.components
    .map(
      (c) => `
      <tr>
        <td class="mono" style="font-weight:700">${c.tag}</td>
        <td><span class="tag-pill">${ZONE_LABELS[c.zone] || c.zone}</span></td>
        <td>${c.label}</td>
        <td class="mono" style="color:var(--accent-blue)">${c.part_number}</td>
        <td class="num">(${Math.round(c.x_mm)}, ${Math.round(c.y_mm)})</td>
        <td class="num">${Math.round(c.w_mm)} × ${Math.round(c.h_mm)} × ${Math.round(c.d_mm)}</td>
        <td class="num">${c.clearance_mm > 0 ? `${Math.round(c.clearance_mm)} mm` : "-"}</td>
        <td class="num" style="color:${c.heat_w >= 45 ? "var(--err-red)" : c.heat_w >= 20 ? "var(--warn-amber)" : "var(--ink-primary)"}">${c.heat_w} W</td>
      </tr>`
    )
    .join("");

  container.innerHTML = `
    <div class="stack-gap">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${t("v5Title")}</h2>
            <p class="panel-subtitle">${t("v5Sub")}</p>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
            <button id="btnModeStandard" class="sheet-tab ${!thermalMode ? "active" : ""}" type="button">${t("btnEmcMode")}</button>
            <button id="btnModeThermal" class="sheet-tab ${thermalMode ? "active" : ""}" type="button">${t("btnThermalMode")}</button>
            ${hasOverrides ? `<button id="btnResetLayout" class="btn btn-secondary btn-sm" type="button">${isKo ? "자동 배치 초기화" : "Auto-Reset Layout"}</button>` : ""}
            <button id="btnLayZoomOut" class="btn btn-secondary btn-sm" type="button">−</button>
            <button id="btnLayZoomReset" class="btn btn-secondary btn-sm mono" type="button">${Math.round(layoutZoom * 100)}%</button>
            <button id="btnLayZoomIn" class="btn btn-secondary btn-sm" type="button">+</button>
            <a class="btn btn-secondary btn-sm" href="${api.exportUrl(project.id, "layout_svg", { thermal: thermalMode ? "true" : null })}">SVG</a>
            <a class="btn btn-secondary btn-sm" href="${api.exportUrl(project.id, "eplan_aml")}">EPLAN AML</a>
            <a class="btn btn-primary btn-sm" href="${api.exportUrl(project.id, "layout_dxf")}">1:1 DXF</a>
          </div>
        </div>
        <div class="panel-body stack-gap">
          <div style="display:flex;gap:12px;flex-wrap:wrap">
            <span class="tag-pill">${isKo ? "외함" : "Enclosure"}: ${layout.enclosure_w_mm}×${layout.enclosure_h_mm}×${layout.enclosure_d_mm} mm (${s.enclosure_part})</span>
            <span class="tag-pill">${isKo ? "중판" : "Plate"}: ${layout.plate_w_mm}×${layout.plate_h_mm} mm</span>
            <span class="tag-pill">${isKo ? "면적 점유율" : "Usage"}: ${layout.utilization_pct}%</span>
            <span class="tag-pill" style="background:var(--ok-green-soft);color:var(--ok-green)">${isKo ? "배선 덕트 경유 총 전선 길이" : "Duct-Routed Panel Wire"}: ${layout.total_panel_wire_m} m</span>
          </div>

          ${issuesHtml}

          <div class="inspector-bar" id="layoutInspector">
            <span><strong>${isKo ? "드래그 편집 · 인스펙터:" : "Drag Editor · Inspector:"}</strong> ${t("v5InspectorHint")}</span>
            <span class="mono" style="color:var(--accent-blue)">Snap: 10mm · ${layout.components.length} ${isKo ? "부품" : "parts"}</span>
          </div>

          <div class="schematic-stage" id="layoutStage">${activeSvg}</div>
        </div>
      </div>

      <!-- Auto-Routed Internal Panel Wire Summary (Synced to BOM) -->
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${isKo ? "배선 덕트 경유 판넬 내부 전선 길이 자동 산출 (BOM 자동 반영)" : "Duct-Routed Panel Internal Wire Length Estimator (Synced to BOM)"}</h2>
            <p class="panel-subtitle">${isKo ? "2D 배치 좌표를 기반으로 배선 덕트 경로(+18% 단말 여유)를 계산하며, 부품을 드래그하면 전선 길이와 BOM 자재비가 자동 재계산됩니다." : "Calculates Manhattan wire-duct routing (+18% termination slack) from live 2D coordinates and injects wire meters directly into BOM."}</p>
          </div>
          <span class="tag-pill mono">Total: ${layout.total_panel_wire_m} m</span>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>${isKo ? "전선 규격 (SQ / AWG)" : "Wire Gauge (SQ / AWG)"}</th>
                <th>${isKo ? "배선 용도" : "Routing Purpose"}</th>
                <th class="num">${isKo ? "경로 수" : "Conductors"}</th>
                <th class="num">${isKo ? "산출 길이" : "Estimated Length"}</th>
                <th class="num">${isKo ? "단가" : "Unit Price"}</th>
                <th class="num">${isKo ? "합계 (BOM 반영)" : "BOM Subtotal"}</th>
              </tr>
            </thead>
            <tbody>${wireRows}</tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${t("v5TableTitle")}</h2>
            <p class="panel-subtitle">${t("v5TableSub")}</p>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>${isKo ? "IEC 태그" : "IEC Tag"}</th>
                <th>${isKo ? "배치 구역" : "Zone"}</th>
                <th>${isKo ? "기기명" : "Component"}</th>
                <th>${isKo ? "파트넘버" : "Part Number"}</th>
                <th class="num">${isKo ? "좌표 X, Y (mm)" : "Pos X, Y (mm)"}</th>
                <th class="num">${isKo ? "외형 W×H×D (mm)" : "Size W×H×D (mm)"}</th>
                <th class="num">${isKo ? "방열 이격" : "Clearance"}</th>
                <th class="num">${isKo ? "발열량" : "Heat"}</th>
              </tr>
            </thead>
            <tbody>${compRows}</tbody>
          </table>
        </div>
      </div>
    </div>
  `;

  const svg = container.querySelector(".interactive-layout-svg");
  const inspector = container.querySelector("#layoutInspector");

  const applyZoom = () => {
    if (svg) svg.style.transform = `scale(${layoutZoom})`;
    container.querySelector("#btnLayZoomReset").textContent = `${Math.round(layoutZoom * 100)}%`;
  };
  applyZoom();

  container.querySelector("#btnModeStandard").addEventListener("click", () => {
    thermalMode = false;
    renderLayoutView(container, design, onReloadDesign, showToast);
  });
  container.querySelector("#btnModeThermal").addEventListener("click", () => {
    thermalMode = true;
    renderLayoutView(container, design, onReloadDesign, showToast);
  });
  container.querySelector("#btnLayZoomIn").addEventListener("click", () => {
    layoutZoom = Math.min(2.0, +(layoutZoom + 0.15).toFixed(2));
    applyZoom();
  });
  container.querySelector("#btnLayZoomOut").addEventListener("click", () => {
    layoutZoom = Math.max(0.6, +(layoutZoom - 0.15).toFixed(2));
    applyZoom();
  });
  container.querySelector("#btnLayZoomReset").addEventListener("click", () => {
    layoutZoom = 1.0;
    applyZoom();
  });

  const btnReset = container.querySelector("#btnResetLayout");
  if (btnReset) {
    btnReset.addEventListener("click", async () => {
      try {
        const fresh = await api.resetLayoutPositions(project.id);
        showToast(isKo ? "중판 배치를 IEC 61439 자동 배치로 초기화했습니다." : "Reset 2D mounting plate to auto-placement.");
        await onReloadDesign(fresh);
      } catch (err) {
        showToast(err.message);
      }
    });
  }

  // --- Interactive SVG Drag-and-Drop (10mm Grid Snap + Live Collision & Wire Re-Calculation) ---
  if (svg) {
    const scale = parseFloat(svg.dataset.scale || "0.35");
    const marginLeft = parseFloat(svg.dataset.marginLeft || "80");
    const marginTop = parseFloat(svg.dataset.marginTop || "58");
    const plateOffX = parseFloat(svg.dataset.plateOffX || "50");
    const plateOffY = parseFloat(svg.dataset.plateOffY || "70");
    const plateW = parseFloat(svg.dataset.plateW || "1000");
    const plateH = parseFloat(svg.dataset.plateH || "1600");

    let dragState = null;

    const clientToSvgPt = (evt) => {
      const pt = svg.createSVGPoint();
      pt.x = evt.clientX;
      pt.y = evt.clientY;
      const ctm = svg.getScreenCTM();
      return ctm ? pt.matrixTransform(ctm.inverse()) : { x: 0, y: 0 };
    };

    svg.querySelectorAll(".layout-comp").forEach((el) => {
      el.style.cursor = "grab";

      el.addEventListener("pointerdown", (evt) => {
        if (evt.button !== 0) return;
        evt.preventDefault();
        el.setPointerCapture(evt.pointerId);
        el.style.cursor = "grabbing";
        const startPt = clientToSvgPt(evt);
        const origX = parseFloat(el.dataset.xMm || "0");
        const origY = parseFloat(el.dataset.yMm || "0");
        const wMm = parseFloat(el.dataset.wMm || "80");
        const hMm = parseFloat(el.dataset.hMm || "80");
        dragState = {
          el,
          tag: el.getAttribute("data-device") || "",
          desc: el.getAttribute("data-desc") || "",
          startSvgX: startPt.x,
          startSvgY: startPt.y,
          origX,
          origY,
          curX: origX,
          curY: origY,
          wMm,
          hMm,
          moved: false,
        };
      });

      el.addEventListener("pointermove", (evt) => {
        if (!dragState || dragState.el !== el) return;
        const pt = clientToSvgPt(evt);
        const dxMm = (pt.x - dragState.startSvgX) / scale;
        const dyMm = (pt.y - dragState.startSvgY) / scale;
        if (Math.abs(dxMm) > 3 || Math.abs(dyMm) > 3) dragState.moved = true;

        // 10mm grid snap clamped loosely inside plate area
        const nextX = Math.max(0, Math.min(plateW - dragState.wMm + 40, Math.round((dragState.origX + dxMm) / 10) * 10));
        const nextY = Math.max(0, Math.min(plateH - dragState.hMm + 40, Math.round((dragState.origY + dyMm) / 10) * 10));
        dragState.curX = nextX;
        dragState.curY = nextY;

        const svgX = marginLeft + (plateOffX + nextX) * scale;
        const svgY = marginTop + (plateOffY + nextY) * scale;
        el.setAttribute("transform", `translate(${svgX.toFixed(1)},${svgY.toFixed(1)})`);
        inspector.innerHTML = `
          <span><strong class="mono" style="color:var(--accent-blue)">${dragState.tag}</strong> → Moving to <strong class="mono">(${nextX}, ${nextY}) mm</strong></span>
          <span class="tag-pill">Snap 10mm · Drop to Check Collisions &amp; Wire Length</span>
        `;
      });

      el.addEventListener("pointerup", async (evt) => {
        if (!dragState || dragState.el !== el) return;
        el.style.cursor = "grab";
        try {
          el.releasePointerCapture(evt.pointerId);
        } catch {
          // ignore
        }
        const finished = dragState;
        dragState = null;

        if (!finished.moved) {
          inspector.innerHTML = `
            <span><strong class="mono" style="color:var(--accent-blue)">${finished.tag}</strong> — ${finished.desc}</span>
            <span class="tag-pill">1:1 mm Synced</span>
          `;
          return;
        }

        try {
          const updated = await api.saveLayoutPositions(project.id, {
            [finished.tag]: { x_mm: finished.curX, y_mm: finished.curY },
          });
          const errCount = (updated.panel_layout.layout_issues || []).filter((i) => i.severity === "ERROR").length;
          showToast(
            errCount > 0
              ? (isKo ? `${finished.tag} 이동 완료 (충돌 ${errCount}건 감지!)` : `Moved ${finished.tag} (${errCount} collision warning!)`)
              : (isKo ? `${finished.tag} → (${finished.curX}, ${finished.curY})mm 저장 · 전선 ${updated.panel_layout.total_panel_wire_m}m 재산출` : `Saved ${finished.tag} at (${finished.curX}, ${finished.curY})mm · Wire ${updated.panel_layout.total_panel_wire_m}m`)
          );
          await onReloadDesign(updated);
        } catch (err) {
          showToast(err.message);
          await onReloadDesign();
        }
      });
    });
  }
}
