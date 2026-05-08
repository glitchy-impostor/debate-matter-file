// Loads card JSON files from /data, served as static assets by Vite.
// In production VITE_BASE prepends the repo path on GitHub Pages.

const base = import.meta.env.BASE_URL;

export async function loadIndex() {
  const res = await fetch(`${base}data/index.json`, { cache: "no-cache" });
  if (!res.ok) throw new Error(`index.json: HTTP ${res.status}`);
  return res.json();
}

export async function loadDay(dateStr) {
  const res = await fetch(`${base}data/cards/${dateStr}.json`, { cache: "no-cache" });
  if (res.status === 404) return { date: dateStr, cards: [] };
  if (!res.ok) throw new Error(`${dateStr}: HTTP ${res.status}`);
  return res.json();
}

export function relativeTime(iso) {
  if (!iso) return "";
  const dt = new Date(iso);
  const diffMs = Date.now() - dt.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function formatDate(dateStr) {
  if (!dateStr) return "";
  const dt = new Date(`${dateStr}T00:00:00Z`);
  return dt.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function adjacentDate(dateStr, offset) {
  const dt = new Date(`${dateStr}T00:00:00Z`);
  dt.setUTCDate(dt.getUTCDate() + offset);
  return dt.toISOString().slice(0, 10);
}
