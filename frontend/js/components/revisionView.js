/** View 07: Project Version Management (Snapshots, Status Promotion, Rollback & ECN Diff) */

import { api } from "../api.js";
import { getLang, t } from "../i18n.js";

function won(n) {
  return `₩${Number(n || 0).toLocaleString()}`;
}

export async function renderRevisionsView(container, design, onReloadDesign, showToast) {
  const { project } = design;
  const [revisions, auditLogs] = await Promise.all([
    api.listRevisions(project.id),
    api.listAuditLogs(project.tenant_id),
  ]);
  const nextVer = `Rev.${String.fromCharCode(65 + Math.min(revisions.length, 25))}`;
  const isKo = getLang() === "ko";

  const revRows = revisions.length
    ? revisions
        .map(
          (r) => `
          <tr>
            <td class="mono" style="font-weight:700">${r.version_tag}</td>
            <td>
              <select class="input-inline" data-rev-status="${r.id}" style="font-weight:600;width:118px">
                <option value="Draft" ${r.status === "Draft" ? "selected" : ""}>Draft</option>
                <option value="In Review" ${r.status === "In Review" ? "selected" : ""}>In Review</option>
                <option value="Released" ${r.status === "Released" ? "selected" : ""}>Released</option>
              </select>
            </td>
            <td>${r.summary || "-"}</td>
            <td>${r.author}</td>
            <td class="num">${won(r.bom_total_krw)}</td>
            <td class="num">${r.total_io_points} pt</td>
            <td class="num">${r.error_count === 0 ? '<span class="sev-badge sev-INFO">PASS</span>' : `<span class="sev-badge sev-ERROR">${r.error_count} ERR</span>`}</td>
            <td class="mono" style="font-size:12px;color:var(--ink-muted)">${r.created_at}</td>
            <td><button class="btn btn-secondary btn-sm" data-restore-rev="${r.id}" data-rev-tag="${r.version_tag}" type="button">${t("btnRestore")}</button></td>
          </tr>`
        )
        .join("")
    : `<tr><td colspan="9" style="text-align:center;color:var(--ink-muted);padding:24px">${isKo ? "아직 저장된 리비전이 없습니다. 첫 리비전 스냅샷(Rev.A)을 발행해 보세요." : "No revisions saved yet. Create your first baseline snapshot (Rev.A) above."}</td></tr>`;

  const optionsHtml = revisions
    .map((r) => `<option value="${r.id}">${r.version_tag} (${r.created_at})</option>`)
    .join("");

  container.innerHTML = `
    <div class="stack-gap">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${t("v7SnapTitle")}</h2>
            <p class="panel-subtitle">${t("v7SnapSub")}</p>
          </div>
        </div>
        <div class="panel-body">
          <div class="settings-grid">
            <div class="field-group">
              <label class="field-label" for="revTag">${t("lblRevTag")}</label>
              <input id="revTag" class="input mono" value="${nextVer}" />
            </div>
            <div class="field-group">
              <label class="field-label" for="revStatus">${t("lblRevStatus")}</label>
              <select id="revStatus" class="input">
                <option value="Draft">Draft</option>
                <option value="In Review">In Review</option>
                <option value="Released">Released</option>
              </select>
            </div>
            <div class="field-group">
              <label class="field-label" for="revAuthor">${t("lblAuthor")}</label>
              <input id="revAuthor" class="input" value="${isKo ? "김전장 선임" : "Lead Controls Eng."}" />
            </div>
            <div class="field-group" style="grid-column:span 2">
              <label class="field-label" for="revSummary">${t("lblSummary")}</label>
              <input id="revSummary" class="input" placeholder="${isKo ? "예: 초도 출도 / 컨베이어 2.2kW 증설 반영" : "e.g., Initial baseline release / Added 2.2kW conveyor"}" />
            </div>
          </div>
          <div style="margin-top:12px;display:flex;justify-content:flex-end">
            <button id="btnSaveRevision" class="btn btn-primary" type="button">${t("btnSaveRev")}</button>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${t("v7HistoryTitle")} (${revisions.length})</h2>
            <p class="panel-subtitle">${t("v7HistorySub")}</p>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>${isKo ? "버전" : "Version"}</th>
                <th>${isKo ? "상태 (승격)" : "Status"}</th>
                <th>${isKo ? "변경 사유" : "Change Notes"}</th>
                <th>${isKo ? "담당자" : "Author"}</th>
                <th class="num">BOM</th>
                <th class="num">PLC I/O</th>
                <th class="num">ERC</th>
                <th>${isKo ? "발행 일시" : "Created"}</th>
                <th>${isKo ? "롤백" : "Rollback"}</th>
              </tr>
            </thead>
            <tbody>${revRows}</tbody>
          </table>
        </div>
      </div>

      ${
        revisions.length >= 2
          ? `
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${t("v7DiffTitle")}</h2>
            <p class="panel-subtitle">${t("v7DiffSub")}</p>
          </div>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
            <select id="diffBase" class="input" style="width:200px">${optionsHtml}</select>
            <span style="font-weight:700">→</span>
            <select id="diffTarget" class="input" style="width:200px">${optionsHtml}</select>
            <button id="btnRunDiff" class="btn btn-secondary btn-sm" type="button">${t("btnRunDiff")}</button>
          </div>
        </div>
        <div class="panel-body" id="diffOutput"></div>
      </div>`
          : ""
      }

      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${isKo ? "테넌트 워크스페이스 감사 로그 (Audit Trail)" : "Organization Workspace Audit Log"}</h2>
            <p class="panel-subtitle">${isKo ? "설계 수정, 표준 매크로 삽입, 패키지 출도 이력을 조직 단위로 기록합니다." : "Tracks project edits, EPLAN macro insertions, revisions, and package exports per manufacturer tenant."}</p>
          </div>
          <span class="tag-pill">${auditLogs.length} ${isKo ? "건" : "events"}</span>
        </div>
        <div class="table-wrap" style="max-height:260px;overflow-y:auto">
          <table class="data-table">
            <thead>
              <tr>
                <th>${isKo ? "작업" : "Action"}</th>
                <th>${isKo ? "프로젝트" : "Project"}</th>
                <th>${isKo ? "상세 내역" : "Detail"}</th>
                <th>${isKo ? "담당자" : "Actor"}</th>
                <th>${isKo ? "일시" : "Timestamp"}</th>
              </tr>
            </thead>
            <tbody>
              ${
                auditLogs.length
                  ? auditLogs
                      .map(
                        (a) => `
                      <tr>
                        <td><span class="tag-pill">${a.action}</span></td>
                        <td class="mono">${a.project_id}</td>
                        <td>${a.detail}</td>
                        <td>${a.actor}</td>
                        <td class="mono" style="font-size:11.5px;color:var(--ink-muted)">${a.created_at}</td>
                      </tr>`
                      )
                      .join("")
                  : `<tr><td colspan="5" style="text-align:center;color:var(--ink-muted);padding:18px">${isKo ? "기록된 감사 로그가 아직 없습니다." : "No audit events recorded yet."}</td></tr>`
              }
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;

  container.querySelector("#btnSaveRevision").addEventListener("click", async () => {
    const payload = {
      version_tag: container.querySelector("#revTag").value.trim() || nextVer,
      status: container.querySelector("#revStatus").value,
      author: container.querySelector("#revAuthor").value.trim() || "Controls Engineer",
      summary: container.querySelector("#revSummary").value.trim() || "Baseline snapshot",
    };
    await api.createRevision(project.id, payload);
    showToast(isKo ? `${payload.version_tag} 리비전이 저장되었습니다.` : `Saved revision ${payload.version_tag}.`);
    await renderRevisionsView(container, design, onReloadDesign, showToast);
  });

  // Status promotion
  container.querySelectorAll("[data-rev-status]").forEach((sel) => {
    sel.addEventListener("change", async () => {
      await api.updateRevisionStatus(project.id, sel.dataset.revStatus, sel.value);
      showToast(isKo ? `결재 상태가 ${sel.value}(으)로 변경되었습니다.` : `Revision status updated to ${sel.value}.`);
    });
  });

  // Snapshot rollback / restore
  container.querySelectorAll("[data-restore-rev]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const revId = btn.dataset.restoreRev;
      const revTag = btn.dataset.revTag;
      const restored = await api.restoreRevision(project.id, revId);
      showToast(isKo ? `${revTag} 스냅샷 시점으로 복원되었습니다.` : `Restored project state to ${revTag}.`);
      await onReloadDesign(restored);
    });
  });

  if (revisions.length >= 2) {
    const baseSel = container.querySelector("#diffBase");
    const targSel = container.querySelector("#diffTarget");
    baseSel.selectedIndex = 1;
    targSel.selectedIndex = 0;

    const runDiff = async () => {
      const diff = await api.diffRevisions(project.id, baseSel.value, targSel.value);
      const out = container.querySelector("#diffOutput");
      const costSign = diff.bom_cost_delta_krw >= 0 ? "+" : "";
      const ioSign = diff.io_points_delta >= 0 ? "+" : "";
      out.innerHTML = `
        <div class="stack-gap">
          <div style="display:flex;gap:12px;flex-wrap:wrap">
            <span class="tag-pill">${diff.base_version} → ${diff.target_version}</span>
            <span class="tag-pill">BOM Delta: ${costSign}${won(diff.bom_cost_delta_krw)}</span>
            <span class="tag-pill">PLC I/O Delta: ${ioSign}${diff.io_points_delta} pt</span>
          </div>
          <div class="grid-2">
            <div>
              <h3 style="margin:0 0 8px;font-size:13.5px">${isKo ? "기능 유닛 변경" : "Load Unit Changes"} (${diff.load_changes.length})</h3>
              ${
                diff.load_changes.length
                  ? diff.load_changes
                      .map(
                        (c) => `<div style="padding:6px 0;border-bottom:1px solid var(--border-subtle)">
                          <span class="diff-badge diff-${c.type}">${c.type}</span>
                          <strong class="mono" style="margin:0 6px">${c.tag}</strong>
                          <span>${c.detail}</span>
                        </div>`
                      )
                      .join("")
                  : `<span style="color:var(--ink-muted)">${isKo ? "변경 없음" : "No load changes"}</span>`
              }
            </div>
            <div>
              <h3 style="margin:0 0 8px;font-size:13.5px">${isKo ? "BOM 부품 변경" : "BOM Part Changes"} (${diff.bom_changes.length})</h3>
              ${
                diff.bom_changes.length
                  ? diff.bom_changes
                      .map(
                        (b) => `<div style="padding:6px 0;border-bottom:1px solid var(--border-subtle)">
                          <span class="diff-badge diff-${b.type}">${b.type}</span>
                          <strong class="mono" style="margin:0 6px">${b.part_number}</strong>
                          <span class="mono" style="font-weight:700">${b.qty_delta}</span>
                          <span style="color:var(--ink-muted);font-size:12px"> (${b.spec})</span>
                        </div>`
                      )
                      .join("")
                  : `<span style="color:var(--ink-muted)">${isKo ? "변경 없음" : "No BOM changes"}</span>`
              }
            </div>
          </div>
        </div>
      `;
    };

    container.querySelector("#btnRunDiff").addEventListener("click", runDiff);
    await runDiff();
  }
}
