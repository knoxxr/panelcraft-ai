/** PanelCraft AI — Main Workspace Controller (EN default / KO toggle, Auto-Updater, GitHub Community, PWA) */

import { api, setAuthToken } from "./api.js";
import { applyStaticTranslations, getLang, setLang, t } from "./i18n.js";
import { renderBomView } from "./components/bomView.js";
import { renderIoPlcView } from "./components/ioPlcView.js";
import { renderLayoutView } from "./components/layoutView.js";
import { renderLoadsView } from "./components/loadTable.js";
import { renderRevisionsView } from "./components/revisionView.js";
import { renderSchematicView } from "./components/schematicView.js";
import { renderVerifyView } from "./components/verifyView.js";

const state = {
  tenants: [],
  activeTenantId: null,
  projects: [],
  activeProjectId: null,
  design: null,
  activeTab: "loads",
  llmConfig: null,
  versionInfo: null,
};

const elTenantSelect = document.getElementById("tenantSelect");
const elProjectSelect = document.getElementById("projectSelect");
const elQuickVendor = document.getElementById("quickVendorSelect");
const elQuickPlc = document.getElementById("quickPlcSelect");
const elSummaryStrip = document.getElementById("summaryStrip");
const elViewContainer = document.getElementById("viewContainer");
const elBadgeIo = document.getElementById("badgeIoCount");
const elBadgeRule = document.getElementById("badgeRuleStatus");
const elSyncDot = document.getElementById("syncDot");
const elSyncText = document.getElementById("syncText");
const elLlmLabel = document.getElementById("llmStatusLabel");
const elVersionPill = document.getElementById("btnOpenUpdate");
const elToast = document.getElementById("toast");

let toastTimer = null;
function showToast(msg) {
  elToast.textContent = msg;
  elToast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    elToast.hidden = true;
  }, 3000);
}

function setSyncState(syncing) {
  elSyncDot.classList.toggle("syncing", syncing);
  elSyncText.textContent = syncing ? t("syncing") : t("syncDone");
}

function updateLlmBadge(cfg) {
  if (!cfg) return;
  if (cfg.provider === "builtin") {
    elLlmLabel.textContent = t("llmBuiltin");
  } else if (cfg.provider === "ollama") {
    elLlmLabel.textContent = `Ollama (${cfg.model})`;
  } else {
    elLlmLabel.textContent = `API (${cfg.model})`;
  }
}

function syncLangButtons() {
  const lang = getLang();
  document.getElementById("btnLangEn").classList.toggle("active", lang === "en");
  document.getElementById("btnLangKo").classList.toggle("active", lang === "ko");
  applyStaticTranslations();
  updateLlmBadge(state.llmConfig);
}

function renderSummaryStrip() {
  if (!state.design) return;
  const { power_summary: s, bom_total_krw, plc_channels, rule_checks, panel_layout } = state.design;
  const errCnt = rule_checks.filter((r) => r.severity === "ERROR").length;
  const warnCnt = rule_checks.filter((r) => r.severity === "WARNING").length;

  elSummaryStrip.innerHTML = `
    <div class="metric-tile">
      <div class="metric-label">${t("kpiPowerTitle")}</div>
      <div class="metric-value">${s.total_connected_kw} kW · ${s.main_breaker_rating_a}AT</div>
      <div class="metric-sub">${s.main_breaker_part} (${s.main_wire_sq} SQ)</div>
    </div>
    <div class="metric-tile">
      <div class="metric-label">${t("kpiSmpsTitle")}</div>
      <div class="metric-value">${s.total_dc24v_current_a}A · ${panel_layout.utilization_pct}%</div>
      <div class="metric-sub">${t("kpiHeat")} ${s.total_heat_loss_w}W · ${s.enclosure_part}</div>
    </div>
    <div class="metric-tile">
      <div class="metric-label">${t("kpiIoTitle")}</div>
      <div class="metric-value">${plc_channels.length} pt</div>
      <div class="metric-sub">${state.design.project.settings.plc_vendor} · ${state.design.plc_modules.length} ${t("kpiSlots")}</div>
    </div>
    <div class="metric-tile">
      <div class="metric-label">${t("kpiBomTitle")}</div>
      <div class="metric-value" style="color:var(--accent-blue)">₩${bom_total_krw.toLocaleString()}</div>
      <div class="metric-sub">${state.design.bom.length} ${t("kpiItems")} · ${state.design.project.settings.preferred_vendor}</div>
    </div>
    <div class="metric-tile">
      <div class="metric-label">${t("kpiVerifyTitle")}</div>
      <div class="metric-value" style="color:${errCnt > 0 ? "var(--err-red)" : warnCnt > 0 ? "var(--warn-amber)" : "var(--ok-green)"}">
        ${errCnt > 0 ? `${errCnt} ERROR` : warnCnt > 0 ? `${warnCnt} WARN` : "ALL PASS"}
      </div>
      <div class="metric-sub">${state.design.project.settings.standard_profile} ${t("kpiStdChecked")}</div>
    </div>
  `;

  elBadgeIo.textContent = String(plc_channels.length);
  elBadgeRule.className = "nav-badge";
  if (errCnt > 0) {
    elBadgeRule.textContent = `${errCnt} ERR`;
    elBadgeRule.classList.add("err");
  } else if (warnCnt > 0) {
    elBadgeRule.textContent = `${warnCnt} WARN`;
    elBadgeRule.classList.add("warn");
  } else {
    elBadgeRule.textContent = "PASS";
    elBadgeRule.classList.add("ok");
  }
}

async function renderActiveView() {
  if (!state.design) return;
  renderSummaryStrip();

  elQuickVendor.value = state.design.project.settings.preferred_vendor;
  elQuickPlc.value = state.design.project.settings.plc_vendor;

  switch (state.activeTab) {
    case "loads":
      await renderLoadsView(elViewContainer, state.design, handleUpdateProject, handleReloadDesign, showToast);
      break;
    case "bom":
      renderBomView(elViewContainer, state.design);
      break;
    case "io":
      renderIoPlcView(elViewContainer, state.design, showToast);
      break;
    case "schematic":
      renderSchematicView(elViewContainer, state.design);
      break;
    case "layout":
      renderLayoutView(elViewContainer, state.design);
      break;
    case "verify":
      renderVerifyView(elViewContainer, state.design);
      break;
    case "revisions":
      await renderRevisionsView(elViewContainer, state.design, handleReloadDesign, showToast);
      break;
  }
}

async function refreshTenantList(selectTenantId = null) {
  state.tenants = await api.listTenants();
  elTenantSelect.innerHTML = state.tenants
    .map((org) => `<option value="${org.id}">${org.name}</option>`)
    .join("");
  const targetTenant = selectTenantId || state.activeTenantId || state.tenants[0]?.id;
  if (targetTenant) {
    state.activeTenantId = targetTenant;
    elTenantSelect.value = targetTenant;
    await refreshProjectList();
  }
}

async function refreshProjectList(selectId = null) {
  state.projects = await api.listProjects(state.activeTenantId);
  elProjectSelect.innerHTML = state.projects
    .map((p) => `<option value="${p.id}">${p.name} (${p.id})</option>`)
    .join("");

  const targetId =
    (selectId && state.projects.some((p) => p.id === selectId) ? selectId : null) ||
    (state.activeProjectId && state.projects.some((p) => p.id === state.activeProjectId) ? state.activeProjectId : null) ||
    state.projects[0]?.id;
  if (targetId) {
    elProjectSelect.value = targetId;
    await loadProject(targetId);
  }
}

async function loadProject(projectId) {
  setSyncState(true);
  try {
    state.activeProjectId = projectId;
    state.design = await api.getDesign(projectId);
    await renderActiveView();
  } finally {
    setSyncState(false);
  }
}

async function handleReloadDesign(precomputedDesign = null) {
  if (precomputedDesign) {
    state.design = precomputedDesign;
    await renderActiveView();
    return;
  }
  if (state.activeProjectId) {
    await loadProject(state.activeProjectId);
  }
}

async function handleUpdateProject(updatedProject) {
  setSyncState(true);
  try {
    state.design = await api.saveProject(updatedProject);
    const opt = elProjectSelect.querySelector(`option[value="${updatedProject.id}"]`);
    if (opt) opt.textContent = `${updatedProject.name} (${updatedProject.id})`;
    await renderActiveView();
    showToast(getLang() === "ko" ? "SSOT 모델이 모든 산출물에 반영되었습니다." : "SSOT model updated across all deliverables.");
  } catch (err) {
    showToast(err.message);
  } finally {
    setSyncState(false);
  }
}

// --- Language Switcher (Default: EN) ---

document.getElementById("btnLangEn").addEventListener("click", () => {
  setLang("en");
  syncLangButtons();
  renderActiveView();
});

document.getElementById("btnLangKo").addEventListener("click", () => {
  setLang("ko");
  syncLangButtons();
  renderActiveView();
});

// --- Topbar & Sidebar Events ---

elTenantSelect.addEventListener("change", async () => {
  state.activeTenantId = elTenantSelect.value;
  state.activeProjectId = null;
  await refreshProjectList();
  showToast(`Switched workspace: ${elTenantSelect.selectedOptions[0]?.textContent || ""}`);
});

elProjectSelect.addEventListener("change", () => loadProject(elProjectSelect.value));

elQuickVendor.addEventListener("change", () => {
  if (!state.design) return;
  const next = structuredClone(state.design.project);
  next.settings.preferred_vendor = elQuickVendor.value;
  handleUpdateProject(next);
});

elQuickPlc.addEventListener("change", () => {
  if (!state.design) return;
  const next = structuredClone(state.design.project);
  next.settings.plc_vendor = elQuickPlc.value;
  handleUpdateProject(next);
});

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.activeTab = btn.dataset.tab;
    renderActiveView();
  });
});

// Dropdown helpers (Export & Community)
function setupDropdown(btnId, menuId) {
  const btn = document.getElementById(btnId);
  const menu = document.getElementById(menuId);
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const open = menu.hidden;
    document.querySelectorAll(".dropdown-menu").forEach((m) => (m.hidden = true));
    menu.hidden = !open;
    btn.setAttribute("aria-expanded", String(open));
  });
  return menu;
}

const menuExport = setupDropdown("btnExportMenu", "exportMenuList");
setupDropdown("btnCommunityMenu", "communityMenuList");

document.addEventListener("click", () => {
  document.querySelectorAll(".dropdown-menu").forEach((m) => (m.hidden = true));
});

menuExport.querySelectorAll("[data-export]").forEach((link) => {
  link.addEventListener("click", (e) => {
    e.preventDefault();
    if (!state.activeProjectId) return;
    window.location.href = api.exportUrl(state.activeProjectId, link.dataset.export);
    menuExport.hidden = true;
    showToast(getLang() === "ko" ? "파일 다운로드를 시작했습니다." : "Artifact download started.");
  });
});

// --- AI Copilot & RFP PDF Modal ---

const copilotModal = document.getElementById("copilotModal");
const inpName = document.getElementById("copilotProjectName");
const inpPrompt = document.getElementById("copilotPrompt");
const inpPdfFile = document.getElementById("copilotPdfFile");

const closeCopilotModal = () => {
  copilotModal.hidden = true;
};

document.getElementById("btnOpenCopilot").addEventListener("click", () => {
  copilotModal.hidden = false;
  inpPrompt.focus();
});
document.getElementById("btnCloseCopilot").addEventListener("click", closeCopilotModal);
document.getElementById("btnCancelCopilot").addEventListener("click", closeCopilotModal);

document.querySelectorAll(".chip-btn").forEach((chip) => {
  chip.addEventListener("click", () => {
    inpPrompt.value = chip.dataset.preset;
    inpName.value = `${chip.textContent} Panel`;
  });
});

document.getElementById("btnRunCopilot").addEventListener("click", async () => {
  const prompt = inpPrompt.value.trim();
  if (!prompt) {
    showToast("Please enter specification text or select a preset.");
    return;
  }
  setSyncState(true);
  try {
    const parsed = await api.parseCopilot({
      prompt,
      tenant_id: state.activeTenantId || "TENANT-KBAT",
      project_name: inpName.value.trim() || "AI Control Panel Draft",
    });
    const savedDesign = await api.saveProject(parsed.suggested_project);
    closeCopilotModal();
    await refreshProjectList(savedDesign.project.id);
    showToast(`Draft created (${parsed.engine_used} · ${Math.round(parsed.confidence * 100)}%)`);
  } catch (err) {
    showToast(err.message);
  } finally {
    setSyncState(false);
  }
});

document.getElementById("btnParsePdf").addEventListener("click", async () => {
  const file = inpPdfFile.files?.[0];
  if (!file) {
    showToast("Please select a PDF or TXT RFP file first.");
    return;
  }
  setSyncState(true);
  try {
    const parsed = await api.parsePdfCopilot(file, inpName.value.trim(), state.activeTenantId || "TENANT-KBAT");
    const savedDesign = await api.saveProject(parsed.suggested_project);
    closeCopilotModal();
    await refreshProjectList(savedDesign.project.id);
    showToast(`RFP parsed (${parsed.engine_used} · ${parsed.suggested_project.loads.length} units)`);
  } catch (err) {
    showToast(err.message);
  } finally {
    setSyncState(false);
  }
});

// --- External / Local LLM Gateway Modal ---

const llmModal = document.getElementById("llmModal");
const selProvider = document.getElementById("llmProvider");
const inpBaseUrl = document.getElementById("llmBaseUrl");
const inpModel = document.getElementById("llmModel");
const inpApiKey = document.getElementById("llmApiKey");
const elEndpointFields = document.getElementById("llmEndpointFields");
const elApiKeyField = document.getElementById("llmApiKeyField");
const elLlmTestRes = document.getElementById("llmTestResult");

function syncLlmModalFields() {
  const p = selProvider.value;
  elEndpointFields.style.display = p === "builtin" ? "none" : "grid";
  elApiKeyField.style.display = p === "openai_compat" ? "flex" : "none";
}

function readLlmForm() {
  return {
    provider: selProvider.value,
    base_url: inpBaseUrl.value.trim() || "http://localhost:11434",
    model: inpModel.value.trim() || "qwen2.5:14b",
    api_key: inpApiKey.value.trim(),
    temperature: 0.1,
    timeout_sec: 25,
  };
}

selProvider.addEventListener("change", syncLlmModalFields);

document.getElementById("btnOpenLlmConfig").addEventListener("click", async () => {
  const cfg = await api.getLlmConfig();
  state.llmConfig = cfg;
  selProvider.value = cfg.provider;
  inpBaseUrl.value = cfg.base_url;
  inpModel.value = cfg.model;
  inpApiKey.value = cfg.api_key || "";
  elLlmTestRes.hidden = true;
  syncLlmModalFields();
  llmModal.hidden = false;
});

document.getElementById("btnCloseLlm").addEventListener("click", () => (llmModal.hidden = true));

document.getElementById("btnTestLlm").addEventListener("click", async () => {
  elLlmTestRes.hidden = false;
  elLlmTestRes.textContent = "Testing connection...";
  try {
    const res = await api.testLlmConfig(readLlmForm());
    elLlmTestRes.innerHTML = `<strong style="color:${res.ok ? "var(--ok-green)" : "var(--err-red)"}">${res.ok ? "OK" : "Failed"}</strong> — ${res.message}`;
  } catch (err) {
    elLlmTestRes.textContent = err.message;
  }
});

document.getElementById("btnSaveLlm").addEventListener("click", async () => {
  const saved = await api.saveLlmConfig(readLlmForm());
  state.llmConfig = saved;
  updateLlmBadge(saved);
  llmModal.hidden = true;
  showToast("LLM gateway settings saved.");
});

// --- App Version, Auto-Update & GitHub Community Modal ---

const updateModal = document.getElementById("updateModal");
const inpUpdRepo = document.getElementById("updGithubRepo");
const selUpdChannel = document.getElementById("updChannel");
const chkUpdAuto = document.getElementById("updAutoCheck");
const elUpdOutput = document.getElementById("updateCheckOutput");

function populateGitHubLinks(info) {
  if (!info?.github_links) return;
  const g = info.github_links;
  elVersionPill.textContent = `v${info.app_version}`;
  document.getElementById("lnkGhBug").href = g.new_bug_url;
  document.getElementById("lnkGhFeature").href = g.new_feature_url;
  document.getElementById("lnkGhDiscuss").href = g.discussions_url;
  document.getElementById("lnkGhReleases").href = g.releases_url;

  document.getElementById("updateRuntimeBar").innerHTML = `
    <span class="tag-pill">Version: v${info.app_version}</span>
    <span class="tag-pill">OS: ${info.os} (${info.arch})</span>
    <span class="tag-pill">Python ${info.python_version}</span>
    <span class="tag-pill">Platforms: Win · macOS · Linux · Android</span>
  `;

  document.getElementById("updateCommunityLinks").innerHTML = `
    <a class="btn btn-secondary btn-sm" href="${g.new_bug_url}" target="_blank" rel="noopener">Report Bug (Issue)</a>
    <a class="btn btn-secondary btn-sm" href="${g.new_feature_url}" target="_blank" rel="noopener">Feature Request</a>
    <a class="btn btn-secondary btn-sm" href="${g.discussions_url}" target="_blank" rel="noopener">GitHub Discussions</a>
    <a class="btn btn-secondary btn-sm" href="${g.releases_url}" target="_blank" rel="noopener">All Releases</a>
  `;

  const fmtMd = (txt) =>
    String(txt)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, '<code class="mono" style="background:var(--bg-hover);padding:1px 4px;border-radius:3px;font-size:11.5px">$1</code>');

  document.getElementById("changelogBox").innerHTML = (info.changelog || [])
    .map(
      (entry) => `
      <div style="margin-bottom:10px">
        <strong class="mono">v${entry.version}</strong> <span style="color:var(--ink-muted)">(${entry.date})</span>
        <ul style="margin:4px 0 0 18px;padding:0">
          ${entry.items.map((it) => `<li style="margin-bottom:3px">${fmtMd(it)}</li>`).join("")}
        </ul>
      </div>`
    )
    .join("");
}

async function openUpdateModal() {
  const info = await api.getVersionInfo();
  state.versionInfo = info;
  populateGitHubLinks(info);
  inpUpdRepo.value = info.update_config.github_repo;
  selUpdChannel.value = info.update_config.channel;
  chkUpdAuto.checked = info.update_config.auto_check_on_startup;
  elUpdOutput.hidden = true;
  updateModal.hidden = false;
}

elVersionPill.addEventListener("click", openUpdateModal);
document.getElementById("lnkCheckUpdate").addEventListener("click", (e) => {
  e.preventDefault();
  openUpdateModal();
});
document.getElementById("btnBannerOpenUpdate").addEventListener("click", openUpdateModal);
document.getElementById("btnCloseUpdate").addEventListener("click", () => (updateModal.hidden = true));

function readUpdateForm() {
  return {
    github_repo: inpUpdRepo.value.trim() || "panelcraft-ai/panelcraft-ai",
    channel: selUpdChannel.value,
    auto_check_on_startup: chkUpdAuto.checked,
  };
}

document.getElementById("btnSaveUpdateCfg").addEventListener("click", async () => {
  await api.saveUpdateConfig(readUpdateForm());
  const info = await api.getVersionInfo();
  state.versionInfo = info;
  populateGitHubLinks(info);
  showToast("Update & GitHub repository configuration saved.");
});

document.getElementById("btnCheckUpdateNow").addEventListener("click", async () => {
  elUpdOutput.hidden = false;
  elUpdOutput.textContent = "Checking GitHub Releases...";
  try {
    const res = await api.checkUpdates(readUpdateForm());
    const assetsHtml = res.assets.length
      ? `<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">
          ${res.assets.map((a) => `<a class="btn btn-primary btn-sm" href="${a.download_url}" target="_blank" rel="noopener">${a.platform}: ${a.name} (${a.size_mb}MB)</a>`).join("")}
         </div>`
      : "";
    elUpdOutput.innerHTML = `
      <div><strong style="color:${res.update_available ? "var(--accent-blue)" : res.status === "up_to_date" ? "var(--ok-green)" : "var(--warn-amber)"}">${res.message}</strong></div>
      <div style="font-size:11.5px;color:var(--ink-muted);margin-top:3px">Checked: ${res.checked_at} · <a href="${res.release_url}" target="_blank" rel="noopener">Open Releases Page</a></div>
      ${assetsHtml}
    `;
  } catch (err) {
    elUpdOutput.textContent = err.message;
  }
});

// --- New Manufacturer Organization Modal ---

const tenantModal = document.getElementById("tenantModal");
document.getElementById("btnNewTenant").addEventListener("click", () => {
  tenantModal.hidden = false;
  document.getElementById("tntName").focus();
});
document.getElementById("btnCloseTenant").addEventListener("click", () => (tenantModal.hidden = true));
document.getElementById("btnCancelTenant").addEventListener("click", () => (tenantModal.hidden = true));
document.getElementById("btnSaveTenant").addEventListener("click", async () => {
  const name = document.getElementById("tntName").value.trim();
  if (!name) {
    showToast("Please enter a manufacturer / organization name.");
    return;
  }
  const slug = name.replace(/[^A-Za-z0-9]/g, "").slice(0, 6).toUpperCase() || "ORG";
  const created = await api.createTenant({
    id: `TENANT-${slug}${Math.floor(10 + Math.random() * 89)}`,
    name,
    industry: document.getElementById("tntIndustry").value.trim() || "Industrial Automation",
    titleblock_company: name.toUpperCase(),
    default_standard: document.getElementById("tntStandard").value,
    default_vendor: document.getElementById("tntVendor").value,
    default_plc: document.getElementById("tntPlc").value,
  });
  tenantModal.hidden = true;
  document.getElementById("tntName").value = "";
  await refreshTenantList(created.id);
  showToast(`Created organization workspace: ${created.name}`);
});

// --- SaaS Authentication & RBAC Modal ---

const authModal = document.getElementById("authModal");
const elAuthBadge = document.getElementById("authBadgeLabel");
const elAuthStatus = document.getElementById("authStatusBox");
const elAuthRegExtra = document.getElementById("authRegisterExtra");
const btnToggleReg = document.getElementById("btnToggleReg");
const btnAuthSubmit = document.getElementById("btnAuthSubmit");
const btnLogout = document.getElementById("btnLogout");
let isRegisterMode = false;

async function refreshAuthStatus() {
  try {
    const me = await api.authMe();
    const dbTxt = `${me.db?.backend || "SQLite"}`;
    if (me.authenticated && me.user) {
      elAuthBadge.textContent = `${me.user.full_name} (${me.user.role})`;
      btnLogout.hidden = false;
      elAuthStatus.innerHTML = `
        <div><strong>Signed in:</strong> ${me.user.full_name} (<span class="mono">${me.user.email}</span>) · <span class="tag-pill">${me.user.role.toUpperCase()}</span></div>
        <div style="margin-top:4px;font-size:11.5px;color:var(--ink-secondary)"><strong>Permissions:</strong> <span class="mono">${me.user.permissions.join(", ")}</span></div>
        <div style="margin-top:4px;font-size:11.5px;color:var(--ink-muted)"><strong>Database Engine:</strong> ${dbTxt}</div>
      `;
    } else {
      elAuthBadge.textContent = "Account (Demo)";
      btnLogout.hidden = true;
      elAuthStatus.innerHTML = `
        <div><strong>Demo Mode (Unauthenticated)</strong> — Sign in or click a Demo Role below to test live RBAC enforcement.</div>
        <div style="margin-top:4px;font-size:11.5px;color:var(--ink-muted)"><strong>Database Engine:</strong> ${dbTxt}</div>
      `;
    }
  } catch {
    setAuthToken("");
    elAuthBadge.textContent = "Account (Demo)";
  }
}

document.getElementById("btnOpenAuth").addEventListener("click", async () => {
  isRegisterMode = false;
  elAuthRegExtra.hidden = true;
  btnAuthSubmit.textContent = "Sign In";
  btnToggleReg.textContent = "Register New Account";
  await refreshAuthStatus();
  authModal.hidden = false;
});
document.getElementById("btnCloseAuth").addEventListener("click", () => (authModal.hidden = true));

btnToggleReg.addEventListener("click", () => {
  isRegisterMode = !isRegisterMode;
  elAuthRegExtra.hidden = !isRegisterMode;
  btnAuthSubmit.textContent = isRegisterMode ? "Create Account & Sign In" : "Sign In";
  btnToggleReg.textContent = isRegisterMode ? "Back to Sign In" : "Register New Account";
});

document.querySelectorAll("[data-demo-login]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const [email, password] = btn.dataset.demoLogin.split("|");
    try {
      const res = await api.login(email, password);
      setAuthToken(res.access_token);
      await refreshAuthStatus();
      authModal.hidden = true;
      showToast(`Signed in as ${res.user.full_name} (${res.user.role})`);
    } catch (err) {
      showToast(err.message);
    }
  });
});

btnAuthSubmit.addEventListener("click", async () => {
  const email = document.getElementById("authEmail").value.trim();
  const password = document.getElementById("authPassword").value;
  if (!email || !password) {
    showToast("Please enter email and password.");
    return;
  }
  try {
    const res = isRegisterMode
      ? await api.register({
          email,
          password,
          full_name: document.getElementById("authFullName").value.trim() || email.split("@")[0],
          role: document.getElementById("authRole").value,
          tenant_id: state.activeTenantId || "TENANT-KBAT",
        })
      : await api.login(email, password);
    setAuthToken(res.access_token);
    await refreshAuthStatus();
    authModal.hidden = true;
    showToast(`Welcome, ${res.user.full_name} (${res.user.role})!`);
  } catch (err) {
    showToast(err.message);
  }
});

btnLogout.addEventListener("click", async () => {
  setAuthToken("");
  await refreshAuthStatus();
  showToast("Signed out.");
});

// --- Model Context Protocol (MCP) Server & Live Tool Playground ---

const mcpModal = document.getElementById("mcpModal");
const elMcpMeta = document.getElementById("mcpMetaBox");
const elMcpConfigCode = document.getElementById("mcpConfigCode");
const elMcpToolSelect = document.getElementById("mcpToolSelect");
const elMcpToolDesc = document.getElementById("mcpToolDesc");
const elMcpArgsInput = document.getElementById("mcpArgsInput");
const elMcpOutput = document.getElementById("mcpOutputCode");
let mcpInfoCache = null;

function defaultArgsForMcpTool(toolName) {
  const pid = state.activeProjectId || "PRJ-BAT01";
  const presets = {
    list_tenants: {},
    list_projects: { tenant_id: state.activeTenantId || "TENANT-KBAT" },
    get_panel_design_summary: { project_id: pid },
    create_project_from_rfp: {
      spec_text: "3P 380V, 2x 1.5kW VFD conveyors, 2x 750W servos, 12 pneumatic solenoids, PLe safety circuit",
      project_name: "MCP Auto-Designed Cell Panel",
      tenant_id: state.activeTenantId || "TENANT-KBAT",
    },
    add_load_unit: {
      project_id: pid,
      tag: "PUMP_MCP1",
      name: "Coolant Circulation Pump",
      load_type: "motor_dol",
      power_kw: 2.2,
      quantity: 1,
    },
    apply_circuit_macro: { project_id: pid, macro_id: "MACRO-HEATER-PID" },
    switch_panel_vendor_or_standard: { project_id: pid, preferred_vendor: "Schneider Electric" },
    run_engineering_verification: { project_id: pid },
    get_bom_and_io_schedule: { project_id: pid },
    generate_plc_interlock_st: {
      project_id: pid,
      requirement_text: "Stop all conveyors immediately on E-Stop or VFD overload fault and require manual reset.",
    },
    move_mounting_plate_component: { project_id: pid, reset: true },
    export_engineering_artifact: { project_id: pid, format: "eplan_aml" },
  };
  return presets[toolName] ?? { project_id: pid };
}

function updateMcpToolSelection() {
  if (!mcpInfoCache) return;
  const tool = mcpInfoCache.tools.find((x) => x.name === elMcpToolSelect.value);
  if (!tool) return;
  elMcpToolDesc.textContent = tool.description;
  elMcpArgsInput.value = JSON.stringify(defaultArgsForMcpTool(tool.name), null, 2);
}

document.getElementById("btnOpenMcp").addEventListener("click", async () => {
  try {
    mcpInfoCache = await api.getMcpInfo();
    elMcpMeta.innerHTML = `
      <div><strong>Server:</strong> <span class="mono">${mcpInfoCache.name}</span> v${mcpInfoCache.version} · Protocol <span class="tag-pill">${mcpInfoCache.protocol_version}</span></div>
      <div style="margin-top:4px;font-size:12px;color:var(--ink-secondary)">
        <strong>Streamable HTTP:</strong> <span class="mono">${mcpInfoCache.transports.streamable_http}</span> &nbsp;|&nbsp;
        <strong>Stdio:</strong> <span class="mono">${mcpInfoCache.transports.stdio_command.join(" ")}</span>
      </div>
      <div style="margin-top:4px;font-size:12px;color:var(--ok-green)">
        <strong>Registered:</strong> ${mcpInfoCache.tools_count} Engineering Tools · ${mcpInfoCache.resources_count} Resources · ${mcpInfoCache.prompts_count} Prompts
      </div>
    `;
    elMcpConfigCode.textContent = JSON.stringify(mcpInfoCache.client_configs.claude_desktop_stdio, null, 2);
    elMcpToolSelect.innerHTML = mcpInfoCache.tools
      .map((tool) => `<option value="${tool.name}">${tool.name}</option>`)
      .join("");
    elMcpToolSelect.value = "get_panel_design_summary";
    updateMcpToolSelection();
    elMcpOutput.textContent = "// Click 'Execute tools/call' to send a live JSON-RPC 2.0 request to POST /mcp";
    mcpModal.hidden = false;
  } catch (err) {
    showToast(err.message);
  }
});

document.getElementById("btnCloseMcp").addEventListener("click", () => (mcpModal.hidden = true));
elMcpToolSelect.addEventListener("change", updateMcpToolSelection);

document.getElementById("btnMcpCfgStdio").addEventListener("click", () => {
  if (!mcpInfoCache) return;
  elMcpConfigCode.textContent = JSON.stringify(mcpInfoCache.client_configs.claude_desktop_stdio, null, 2);
});
document.getElementById("btnMcpCfgHttp").addEventListener("click", () => {
  if (!mcpInfoCache) return;
  elMcpConfigCode.textContent = JSON.stringify(mcpInfoCache.client_configs.streamable_http, null, 2);
});
document.getElementById("btnCopyMcpCfg").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(elMcpConfigCode.textContent);
    showToast("Copied MCP client configuration JSON.");
  } catch {
    showToast("Select and copy the MCP JSON block.");
  }
});

document.getElementById("btnRunMcpTool").addEventListener("click", async () => {
  const toolName = elMcpToolSelect.value;
  let parsedArgs = {};
  try {
    parsedArgs = JSON.parse(elMcpArgsInput.value || "{}");
  } catch (e) {
    showToast(`Invalid JSON arguments: ${e.message}`);
    return;
  }
  elMcpOutput.textContent = "Executing MCP JSON-RPC 2.0 tools/call ...";
  try {
    const rpcRes = await api.callMcpRpc({
      jsonrpc: "2.0",
      id: Date.now(),
      method: "tools/call",
      params: { name: toolName, arguments: parsedArgs },
    });
    elMcpOutput.textContent = JSON.stringify(rpcRes, null, 2);
    const mutating = [
      "create_project_from_rfp",
      "add_load_unit",
      "apply_circuit_macro",
      "switch_panel_vendor_or_standard",
      "move_mounting_plate_component",
    ];
    if (mutating.includes(toolName) && !rpcRes?.result?.isError) {
      await refreshProjectList(state.activeProjectId);
      showToast(`MCP tool '${toolName}' applied to workspace.`);
    }
  } catch (err) {
    elMcpOutput.textContent = `ERROR: ${err.message}`;
  }
});

// Register PWA Service Worker (Android / Desktop installable)
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

// Initialize Workspace (English Default, Multi-Tenant SaaS)
(async () => {
  syncLangButtons();
  await refreshAuthStatus();
  try {
    const [llmCfg, verInfo] = await Promise.all([api.getLlmConfig(), api.getVersionInfo()]);
    state.llmConfig = llmCfg;
    state.versionInfo = verInfo;
    updateLlmBadge(llmCfg);
    populateGitHubLinks(verInfo);

    if (verInfo.update_config.auto_check_on_startup) {
      api.checkUpdates().then((u) => {
        if (u.update_available) {
          document.getElementById("updateBannerText").textContent =
            `Update available: PanelCraft AI v${u.latest_version} (current v${u.current_version})`;
          document.getElementById("updateBanner").hidden = false;
        }
      }).catch(() => {});
    }
  } catch {
    // ignore startup metadata failure
  }
  await refreshTenantList();
})();
