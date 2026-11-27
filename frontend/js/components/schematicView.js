/** View 04: Interactive Multi-Sheet IEC 61082 SVG Schematic Viewer & Terminal Strip */

import { api } from "../api.js";
import { getLang, t } from "../i18n.js";

let activeSheetIndex = 0;
let currentZoom = 1.0;

export function renderSchematicView(container, design) {
  const { project, schematic_sheets: sheets, terminals } = design;
  if (activeSheetIndex >= sheets.length) activeSheetIndex = 0;
  const activeSheet = sheets[activeSheetIndex];
  const isKo = getLang() === "ko";

  const tabsHtml = sheets
    .map(
      (sh, i) =>
        `<button type="button" class="sheet-tab ${i === activeSheetIndex ? "active" : ""}" data-sheet-idx="${i}">
          ${sh.code}: ${sh.title}
        </button>`
    )
    .join("");

  const termRows = terminals
    .slice(0, 60)
    .map(
      (tr) => `
      <tr>
        <td class="mono" style="font-weight:700">${tr.strip}:${String(tr.terminal_no).padStart(3, "0")}</td>
        <td class="mono">${tr.wire_number}</td>
        <td class="num">${tr.wire_sq} SQ</td>
        <td class="mono">${tr.wire_color}</td>
        <td>${tr.from_device}</td>
        <td>${tr.to_device}</td>
        <td>${tr.signal}</td>
      </tr>`
    )
    .join("");

  container.innerHTML = `
    <div class="stack-gap">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${t("v4Title")}</h2>
            <p class="panel-subtitle">${t("v4Sub")}</p>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button id="btnZoomOut" class="btn btn-secondary btn-sm" type="button">−</button>
            <button id="btnZoomReset" class="btn btn-secondary btn-sm mono" type="button">${Math.round(currentZoom * 100)}%</button>
            <button id="btnZoomIn" class="btn btn-secondary btn-sm" type="button">+</button>
            <a class="btn btn-secondary btn-sm" href="${api.exportUrl(project.id, "svg", { sheet: activeSheet.sheet_no })}">SVG</a>
            <a class="btn btn-secondary btn-sm" href="${api.exportUrl(project.id, "eplan_aml")}">EPLAN AML</a>
            <a class="btn btn-primary btn-sm" href="${api.exportUrl(project.id, "dxf")}">AutoCAD DXF</a>
          </div>
        </div>
        <div class="panel-body stack-gap">
          <div class="sheet-tabs">${tabsHtml}</div>
          <div class="inspector-bar" id="deviceInspector">
            <span><strong>${isKo ? "심볼 인스펙터:" : "Symbol Inspector:"}</strong> ${t("v4InspectorHint")}</span>
            <span class="mono" style="color:var(--accent-blue)">${activeSheet.code} (${activeSheet.sheet_no}/${sheets.length})</span>
          </div>
          <div class="schematic-stage" id="schematicStage">${activeSheet.svg}</div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${t("v4TermTitle")}</h2>
            <p class="panel-subtitle">${terminals.length} ${isKo ? "단자 포인트" : "terminal points"}</p>
          </div>
          <a class="btn btn-secondary btn-sm" href="${api.exportUrl(project.id, "terminals_csv")}">${t("btnTermCsv")}</a>
        </div>
        <div class="table-wrap" style="max-height:360px;overflow-y:auto">
          <table class="data-table">
            <thead>
              <tr>
                <th>${isKo ? "단자대" : "Terminal"}</th>
                <th>${isKo ? "와이어 번호" : "Wire No."}</th>
                <th class="num">${isKo ? "굵기" : "SQ"}</th>
                <th>${isKo ? "색상" : "Color"}</th>
                <th>${isKo ? "From (판넬 내부)" : "From (Internal)"}</th>
                <th>${isKo ? "To (현장 기기)" : "To (Field)"}</th>
                <th>${isKo ? "신호 설명" : "Signal"}</th>
              </tr>
            </thead>
            <tbody>${termRows}</tbody>
          </table>
        </div>
      </div>
    </div>
  `;

  const applyZoom = () => {
    const svg = container.querySelector(".schematic-svg");
    if (svg) svg.style.transform = `scale(${currentZoom})`;
    container.querySelector("#btnZoomReset").textContent = `${Math.round(currentZoom * 100)}%`;
  };
  applyZoom();

  container.querySelector("#btnZoomIn").addEventListener("click", () => {
    currentZoom = Math.min(2.0, +(currentZoom + 0.15).toFixed(2));
    applyZoom();
  });
  container.querySelector("#btnZoomOut").addEventListener("click", () => {
    currentZoom = Math.max(0.6, +(currentZoom - 0.15).toFixed(2));
    applyZoom();
  });
  container.querySelector("#btnZoomReset").addEventListener("click", () => {
    currentZoom = 1.0;
    applyZoom();
  });

  container.querySelectorAll("[data-sheet-idx]").forEach((btn) => {
    btn.addEventListener("click", () => {
      activeSheetIndex = Number(btn.dataset.sheetIdx);
      renderSchematicView(container, design);
    });
  });

  const inspector = container.querySelector("#deviceInspector");
  container.querySelectorAll(".sch-device").forEach((el) => {
    el.addEventListener("click", () => {
      const dev = el.getAttribute("data-device") || "";
      const desc = el.getAttribute("data-desc") || "";
      inspector.innerHTML = `
        <span><strong class="mono" style="color:var(--accent-blue)">${dev}</strong> — ${desc}</span>
        <span class="tag-pill">SSOT Synced</span>
      `;
    });
  });
}
