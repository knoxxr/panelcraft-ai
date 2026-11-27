/** View 03: PLC Rack Visualizer, I/O Table, ST Scaffolding & AI Natural-Language Interlock Generator */

import { api } from "../api.js";
import { getLang, t } from "../i18n.js";

export function renderIoPlcView(container, design, showToast) {
  const { project, plc_modules: modules, plc_channels: channels, plc_st_code: stCode } = design;
  const isKo = getLang() === "ko";

  const rackHtml = modules
    .map((m) => {
      const pct = m.channels > 0 ? Math.round((m.used_channels / m.channels) * 100) : 100;
      const pillCls = m.module_type === "DI" ? "pill-di" : m.module_type === "DO" ? "pill-do" : m.module_type === "AI" ? "pill-ai" : m.module_type === "AO" ? "pill-ao" : "";
      return `
        <div class="plc-slot">
          <div class="plc-slot-head">
            <span>SLOT ${m.slot}</span>
            <span class="tag-pill ${pillCls}">${m.module_type}</span>
          </div>
          <div class="plc-slot-pn">${m.part_number}</div>
          <div style="font-size:11px;color:var(--ink-muted)">${m.channels > 0 ? `${m.used_channels}/${m.channels} pt (${pct}%)` : (isKo ? "시스템 기본" : "System Base")}</div>
          ${
            m.channels > 0
              ? `<div class="plc-slot-bar"><div class="plc-slot-fill" style="width:${pct}%"></div></div>
                 <div class="mono" style="font-size:10.5px;color:var(--ink-secondary)">${m.start_address} ~ ${m.end_address}</div>`
              : `<div style="font-size:10.5px;color:var(--ink-secondary)">${m.manufacturer}</div>`
          }
        </div>`;
    })
    .join("");

  container.innerHTML = `
    <div class="stack-gap">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${t("v3RackTitle")} (${project.settings.plc_vendor} · ${isKo ? "예비율" : "Spare"} ${Math.round(project.settings.io_spare_ratio * 100)}%)</h2>
            <p class="panel-subtitle">${modules.length} ${t("kpiSlots")} · ${channels.length} ${isKo ? "활성 I/O 점" : "Active I/O Points"}</p>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <a class="btn btn-secondary btn-sm" href="${api.exportUrl(project.id, "eplan_aml")}">EPLAN PLC AML</a>
            <a class="btn btn-secondary btn-sm" href="${api.exportUrl(project.id, "plcopen_xml")}">PLCopen XML</a>
            <a class="btn btn-secondary btn-sm" href="${api.exportUrl(project.id, "io_csv")}">I/O CSV</a>
            <a class="btn btn-primary btn-sm" href="${api.exportUrl(project.id, "plc_st")}">ST (.st)</a>
          </div>
        </div>
        <div class="panel-body">
          <div class="plc-rack">${rackHtml}</div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${t("v3IlTitle")}</h2>
            <p class="panel-subtitle">${t("v3IlSub")}</p>
          </div>
          <span class="tag-pill" id="interlockEngineTag">${isKo ? "대기 중" : "Ready"}</span>
        </div>
        <div class="panel-body stack-gap">
          <div class="preset-chips">
            <span class="chip-label">${isKo ? "인터록 예시:" : "Presets:"}</span>
            <button type="button" class="chip-btn" data-il-preset="On E-Stop or safety door open, immediately stop all conveyors and servos and turn on red tower lamp & buzzer. Stop line on any inverter fault or overload. Require servo HOME complete before auto cycle start.">${isKo ? "안전·컨베이어·서보 통합 인터록" : "Safety + Conveyor + Servo Home"}</button>
            <button type="button" class="chip-btn" data-il-preset="On E-Stop cut all drives and heaters immediately. If chamber heater exceeds 185C or OTP trips, cut heater SSR output and latch alarm until temperature drops and manual reset PB is pressed.">${isKo ? "히터 과승온(185°C) + EMO 인터록" : "Heater Over-Temp (185°C) + EMO"}</button>
          </div>
          <div style="display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap">
            <textarea id="txtInterlockReq" class="textarea-full" rows="3" style="flex:1;min-width:280px" placeholder="${isKo ? "자연어로 인터록 및 알람 조건을 입력하세요..." : "Describe interlock & alarm rules in English or Korean..."}"></textarea>
            <button id="btnGenInterlock" class="btn btn-primary" type="button" style="height:42px">${t("btnGenIl")}</button>
          </div>
          <div id="interlockOutput" hidden class="stack-gap"></div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${t("v3IoTableTitle")}</h2>
            <p class="panel-subtitle">${t("v3IoTableSub")}</p>
          </div>
          <div style="display:flex;gap:8px;align-items:center">
            <select id="ioTypeFilter" class="input" style="width:110px">
              <option value="ALL">${isKo ? "전체" : "ALL"} (${channels.length})</option>
              <option value="DI">DI (${channels.filter((c) => c.io_type === "DI").length})</option>
              <option value="DO">DO (${channels.filter((c) => c.io_type === "DO").length})</option>
              <option value="AI">AI (${channels.filter((c) => c.io_type === "AI").length})</option>
              <option value="AO">AO (${channels.filter((c) => c.io_type === "AO").length})</option>
            </select>
            <input id="ioSearchInput" class="input" placeholder="${isKo ? "주소·태그·신호명 검색..." : "Search address, tag, signal..."}" style="width:200px" />
          </div>
        </div>
        <div class="table-wrap" style="max-height:360px;overflow-y:auto">
          <table class="data-table">
            <thead>
              <tr>
                <th>${isKo ? "구분" : "Type"}</th>
                <th>${isKo ? "PLC 주소" : "PLC Address"}</th>
                <th>${isKo ? "슬롯" : "Slot"}</th>
                <th>${isKo ? "단자번호" : "Terminal"}</th>
                <th>${isKo ? "와이어 번호" : "Wire No."}</th>
                <th>${isKo ? "유닛 태그" : "Unit Tag"}</th>
                <th>${isKo ? "신호명 (Comment)" : "Signal Description"}</th>
                <th>${isKo ? "전압" : "Level"}</th>
              </tr>
            </thead>
            <tbody id="ioTableBody"></tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${t("v3StTitle")}</h2>
            <p class="panel-subtitle">${t("v3StSub")}</p>
          </div>
          <button id="btnCopySt" class="btn btn-secondary btn-sm" type="button">${t("btnCopy")}</button>
        </div>
        <div class="panel-body">
          <pre class="code-block" id="stCodePre"></pre>
        </div>
      </div>
    </div>
  `;

  container.querySelector("#stCodePre").textContent = stCode;

  const txtReq = container.querySelector("#txtInterlockReq");
  const outDiv = container.querySelector("#interlockOutput");
  const engTag = container.querySelector("#interlockEngineTag");

  container.querySelectorAll("[data-il-preset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      txtReq.value = btn.dataset.ilPreset;
    });
  });

  container.querySelector("#btnGenInterlock").addEventListener("click", async () => {
    const reqText = txtReq.value.trim();
    if (!reqText) {
      showToast(isKo ? "인터록 요구사항을 입력하거나 예시를 선택하세요." : "Please enter interlock requirements or select a preset.");
      return;
    }
    const btn = container.querySelector("#btnGenInterlock");
    btn.disabled = true;
    btn.textContent = t("btnGenerating");
    try {
      const res = await api.generateInterlock(project.id, reqText);
      engTag.textContent = res.engine_used;
      const alarmRows = res.alarms
        .map(
          (a) => `
          <tr>
            <td class="mono" style="font-weight:700;color:var(--err-red)">${a.alarm_code}</td>
            <td>${a.condition}</td>
            <td>${a.action}</td>
            <td>${a.reset_policy}</td>
            <td class="mono" style="font-size:11.5px">${a.related_io.join(", ") || "-"}</td>
          </tr>`
        )
        .join("");

      outDiv.hidden = false;
      outDiv.innerHTML = `
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>${isKo ? "알람 코드" : "Alarm Code"}</th>
                <th>${isKo ? "발생 조건" : "Trigger Condition"}</th>
                <th>${isKo ? "인터록 조치" : "Interlock Action"}</th>
                <th>${isKo ? "복구 정책" : "Reset Policy"}</th>
                <th>${isKo ? "연계 PLC I/O" : "Linked I/O"}</th>
              </tr>
            </thead>
            <tbody>${alarmRows}</tbody>
          </table>
        </div>
        <div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <strong style="font-size:13px">FB_InterlockAndAlarm.st</strong>
            <button id="btnDownloadIlSt" class="btn btn-secondary btn-sm" type="button">Download .st</button>
          </div>
          <pre class="code-block" id="ilCodePre"></pre>
        </div>
      `;
      outDiv.querySelector("#ilCodePre").textContent = res.st_code;
      outDiv.querySelector("#btnDownloadIlSt").addEventListener("click", () => {
        const blob = new Blob([res.st_code], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${project.id}_FB_InterlockAndAlarm.st`;
        a.click();
        URL.revokeObjectURL(url);
      });
      showToast(isKo ? `ST 인터록 생성 완료 (${res.alarms.length}건)` : `Generated ST interlock block (${res.alarms.length} alarm rules).`);
    } catch (err) {
      showToast(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = t("btnGenIl");
    }
  });

  const tbody = container.querySelector("#ioTableBody");
  const filterEl = container.querySelector("#ioTypeFilter");
  const searchEl = container.querySelector("#ioSearchInput");

  const renderRows = () => {
    const typeVal = filterEl.value;
    const q = searchEl.value.trim().toLowerCase();
    const filtered = channels.filter((ch) => {
      if (typeVal !== "ALL" && ch.io_type !== typeVal) return false;
      if (!q) return true;
      return (
        ch.plc_address.toLowerCase().includes(q) ||
        ch.unit_tag.toLowerCase().includes(q) ||
        ch.signal_name.toLowerCase().includes(q) ||
        ch.wire_number.toLowerCase().includes(q)
      );
    });
    tbody.innerHTML = filtered
      .map(
        (ch) => `
        <tr>
          <td><span class="tag-pill pill-${ch.io_type.toLowerCase()}">${ch.io_type}</span></td>
          <td class="mono" style="font-weight:700">${ch.plc_address}</td>
          <td class="mono">S${ch.slot}.${String(ch.point_index).padStart(2, "0")}</td>
          <td class="mono">${ch.terminal_tag}</td>
          <td class="mono">${ch.wire_number}</td>
          <td class="mono">${ch.unit_tag}</td>
          <td>${ch.signal_name}</td>
          <td class="mono">${ch.voltage}</td>
        </tr>`
      )
      .join("");
  };

  filterEl.addEventListener("change", renderRows);
  searchEl.addEventListener("input", renderRows);
  renderRows();

  container.querySelector("#btnCopySt").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(stCode);
      const btn = container.querySelector("#btnCopySt");
      btn.textContent = t("btnCopied");
      setTimeout(() => (btn.textContent = t("btnCopy")), 1500);
    } catch {
      // ignore
    }
  });
}
