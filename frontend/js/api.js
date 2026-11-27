/** REST API client for PanelCraft AI backend (with JWT Auth & RBAC support) */

const TOKEN_KEY = "panelcraft_jwt";

export function getAuthToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function setAuthToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore
  }
}

async function request(url, options = {}) {
  const isFormData = options.body instanceof FormData;
  const token = getAuthToken();
  const headers = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    let msg = await res.text();
    try {
      const parsed = JSON.parse(msg);
      if (parsed.detail) msg = parsed.detail;
    } catch {
      // keep raw
    }
    throw new Error(`(${res.status}) ${msg}`);
  }
  return res.json();
}

export const api = {
  // Authentication & RBAC
  login: (email, password) =>
    request("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (payload) =>
    request("/api/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  authMe: () => request("/api/auth/me"),
  listUsers: (tenantId = null) =>
    request(tenantId ? `/api/auth/users?tenant_id=${encodeURIComponent(tenantId)}` : "/api/auth/users"),

  // Interactive 2D Mounting Plate Layout Drag & Reset
  saveLayoutPositions: (projectId, positions) =>
    request(`/api/projects/${encodeURIComponent(projectId)}/layout/positions`, {
      method: "POST",
      body: JSON.stringify({ positions }),
    }),
  resetLayoutPositions: (projectId) =>
    request(`/api/projects/${encodeURIComponent(projectId)}/layout/reset`, { method: "POST" }),

  // Version, Auto-Update & GitHub Community
  getVersionInfo: () => request("/api/version"),
  getUpdateConfig: () => request("/api/update/config"),
  saveUpdateConfig: (cfg) =>
    request("/api/update/config", { method: "POST", body: JSON.stringify(cfg) }),
  checkUpdates: (cfg = null) =>
    request("/api/update/check", {
      method: "POST",
      body: cfg ? JSON.stringify(cfg) : undefined,
    }),

  // Multi-Tenant Organizations
  listTenants: () => request("/api/tenants"),
  createTenant: (tenant) =>
    request("/api/tenants", { method: "POST", body: JSON.stringify(tenant) }),

  // Standard Circuit Macro Library & Audit Logs
  listMacros: () => request("/api/macros"),
  applyMacro: (projectId, macroId) =>
    request(`/api/projects/${encodeURIComponent(projectId)}/macros/${encodeURIComponent(macroId)}`, {
      method: "POST",
    }),
  listAuditLogs: (tenantId = null) =>
    request(tenantId ? `/api/audit?tenant_id=${encodeURIComponent(tenantId)}` : "/api/audit"),

  // Projects (Tenant-Scoped)
  listProjects: (tenantId = null) =>
    request(tenantId ? `/api/projects?tenant_id=${encodeURIComponent(tenantId)}` : "/api/projects"),
  getDesign: (projectId) => request(`/api/projects/${encodeURIComponent(projectId)}/design`),
  saveProject: (project) =>
    request("/api/projects", {
      method: "POST",
      body: JSON.stringify(project),
    }),
  deleteProject: (projectId) =>
    request(`/api/projects/${encodeURIComponent(projectId)}`, { method: "DELETE" }),

  // Excel / CSV Importers & Custom Company Catalog (Tenant-Scoped)
  importLoadsFile: (projectId, file, mode = "replace") => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("mode", mode);
    return request(`/api/projects/${encodeURIComponent(projectId)}/import/loads`, {
      method: "POST",
      body: fd,
    });
  },
  listCustomCatalog: (tenantId = null) =>
    request(tenantId ? `/api/catalog/custom?tenant_id=${encodeURIComponent(tenantId)}` : "/api/catalog/custom"),
  importCatalogFile: (file, tenantId = "TENANT-KBAT") => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("tenant_id", tenantId);
    return request("/api/import/catalog", {
      method: "POST",
      body: fd,
    });
  },
  deleteCustomCatalogItem: (itemId, tenantId = null) =>
    request(
      tenantId
        ? `/api/catalog/custom/${encodeURIComponent(itemId)}?tenant_id=${encodeURIComponent(tenantId)}`
        : `/api/catalog/custom/${encodeURIComponent(itemId)}`,
      { method: "DELETE" }
    ),
  templateUrl: (kind) => `/api/templates/${encodeURIComponent(kind)}`,

  // External / Local LLM Gateway & Copilot
  getLlmConfig: () => request("/api/llm/config"),
  saveLlmConfig: (cfg) =>
    request("/api/llm/config", { method: "POST", body: JSON.stringify(cfg) }),
  testLlmConfig: (cfg) =>
    request("/api/llm/test", { method: "POST", body: JSON.stringify(cfg) }),

  parseCopilot: (payload) =>
    request("/api/copilot/parse", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  parsePdfCopilot: (file, projectName = "", tenantId = "TENANT-KBAT") => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("tenant_id", tenantId);
    if (projectName) fd.append("project_name", projectName);
    return request("/api/copilot/parse-pdf", {
      method: "POST",
      body: fd,
    });
  },
  generateInterlock: (projectId, requirementText) =>
    request(`/api/projects/${encodeURIComponent(projectId)}/copilot/interlock`, {
      method: "POST",
      body: JSON.stringify({ requirement_text: requirementText }),
    }),

  // Revisions, Status Promotion, Rollback & ECN Diff
  listRevisions: (projectId) =>
    request(`/api/projects/${encodeURIComponent(projectId)}/revisions`),
  createRevision: (projectId, payload) =>
    request(`/api/projects/${encodeURIComponent(projectId)}/revisions`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateRevisionStatus: (projectId, revId, status) =>
    request(`/api/projects/${encodeURIComponent(projectId)}/revisions/${encodeURIComponent(revId)}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  restoreRevision: (projectId, revId) =>
    request(`/api/projects/${encodeURIComponent(projectId)}/revisions/${encodeURIComponent(revId)}/restore`, {
      method: "POST",
    }),
  diffRevisions: (projectId, baseId, targetId) =>
    request(
      `/api/projects/${encodeURIComponent(projectId)}/revisions/diff?base_id=${encodeURIComponent(baseId)}&target_id=${encodeURIComponent(targetId)}`
    ),

  // Artifact Exporters
  exportUrl: (projectId, fmt, params = {}) => {
    const base = `/api/projects/${encodeURIComponent(projectId)}/export/${fmt}`;
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== false)
    ).toString();
    return qs ? `${base}?${qs}` : base;
  },
};
