// Matter file API client. The base URL comes from VITE_API_URL at build time;
// when unset (e.g. in CI before Railway is provisioned), the helpers degrade
// gracefully — `enabled()` returns false and the UI hides matter-file actions.

const RAW_BASE = import.meta.env.VITE_API_URL || "";
const API_BASE = RAW_BASE.replace(/\/+$/, "");

export function enabled() {
  return Boolean(API_BASE);
}

function url(path) {
  return `${API_BASE}${path}`;
}

async function request(path, opts = {}) {
  if (!API_BASE) throw new Error("Matter file API not configured (VITE_API_URL)");
  const res = await fetch(url(path), {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  if (res.status === 204) return null;
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

export async function listEntries({ category, search } = {}) {
  const qs = new URLSearchParams();
  if (category) qs.set("category", category);
  if (search) qs.set("search", search);
  const q = qs.toString();
  return request(`/api/matter-file${q ? `?${q}` : ""}`);
}

export async function addEntry(card) {
  return request(`/api/matter-file`, {
    method: "POST",
    body: JSON.stringify({ card_data: card }),
  });
}

export async function removeEntry(id) {
  return request(`/api/matter-file/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function updateNotes(id, notes) {
  return request(`/api/matter-file/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify({ notes }),
  });
}

export async function checkSaved(ids) {
  if (!enabled() || !ids?.length) return new Set();
  const qs = new URLSearchParams({ ids: ids.join(",") });
  const data = await request(`/api/matter-file/check?${qs.toString()}`);
  return new Set(data?.saved || []);
}

// Triggers a browser download of the rendered Markdown.
export function exportMatterFileUrl() {
  return url(`/api/matter-file/export?format=md`);
}
