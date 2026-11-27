/** View 06: Deterministic ERC/DRC Verification & Knowledge-Base AI Review */

import { api } from "../api.js";
import { getLang, t } from "../i18n.js";

export function renderVerifyView(container, design) {
  const { project, rule_checks: rules } = design;
  const errCnt = rules.filter((r) => r.severity === "ERROR").length;
  const warnCnt = rules.filter((r) => r.severity === "WARNING").length;
  const aiCnt = rules.filter((r) => r.category === "AI_REVIEW").length;
  const isKo = getLang() === "ko";

  const cardsHtml = rules
    .map(
      (r) => `
      <article class="rule-row">
        <div class="rule-row-top">
          <span class="sev-badge sev-${r.severity}">${r.severity}</span>
          <span class="tag-pill">${r.rule_id}</span>
          <span class="tag-pill">${r.category}</span>
          <span class="rule-title">${r.title}</span>
          <span class="rule-ref">${r.standard_ref} · ${isKo ? "대상" : "Target"}: ${r.target_tag}</span>
        </div>
        <p class="rule-detail">${r.detail}</p>
        <p class="rule-rec">${t("lblAction")}: ${r.recommendation}</p>
      </article>`
    )
    .join("");

  container.innerHTML = `
    <div class="stack-gap">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">${t("v6Title")}</h2>
            <p class="panel-subtitle">${t("v6Sub")}</p>
          </div>
          <a class="btn btn-primary btn-sm" href="${api.exportUrl(project.id, "fat_md")}">${t("btnFatDownload")}</a>
        </div>
        <div class="panel-body stack-gap">
          <div style="display:flex;gap:12px;flex-wrap:wrap">
            <span class="sev-badge sev-ERROR">ERROR: ${errCnt}</span>
            <span class="sev-badge sev-WARNING">WARNING: ${warnCnt}</span>
            <span class="tag-pill">${isKo ? "AI 리뷰" : "AI Reviews"}: ${aiCnt}</span>
            <span class="tag-pill">${isKo ? "규격" : "Standard"}: ${project.settings.standard_profile}</span>
          </div>
          <div class="rule-list">${cardsHtml}</div>
        </div>
      </div>
    </div>
  `;
}
