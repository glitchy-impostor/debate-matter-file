import { useEffect, useMemo, useState } from "react";
import MatterCard from "../components/MatterCard.jsx";
import { CATEGORIES } from "../lib/constants.js";
import * as api from "../lib/api.js";
import { useMatter } from "../lib/matterContext.jsx";

const CATEGORY_ORDER = ["IR", "Econ", "Business"];
const CATEGORY_HEADERS = {
  IR: "International Relations",
  Econ: "Economics",
  Business: "Business",
  _other: "Other",
};

export default function MatterFile() {
  const matter = useMatter();
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [activeCats, setActiveCats] = useState(() => new Set(Object.keys(CATEGORIES)));

  useEffect(() => {
    if (!api.enabled()) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.listEntries();
        if (!cancelled) setEntries(data || []);
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  function handleRemove(id) {
    setEntries((prev) => prev.filter((e) => e.id !== id));
    matter.savedIds.delete(id);
  }

  function handleNotesChange(id, notes) {
    setEntries((prev) =>
      prev.map((e) => (e.id === id ? { ...e, notes } : e)),
    );
  }

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return entries.filter((e) => {
      const cat = e.card_data?.category;
      if (cat && CATEGORIES[cat] && !activeCats.has(cat)) return false;
      if (!q) return true;
      const haystack = (JSON.stringify(e.card_data) + " " + (e.notes || "")).toLowerCase();
      return haystack.includes(q);
    });
  }, [entries, search, activeCats]);

  const grouped = useMemo(() => {
    const out = { IR: [], Econ: [], Business: [], _other: [] };
    for (const e of visible) {
      const cat = e.card_data?.category;
      if (cat in out) out[cat].push(e);
      else out._other.push(e);
    }
    return out;
  }, [visible]);

  function toggleCat(cat) {
    setActiveCats((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  }

  if (!api.enabled()) {
    return (
      <div className="rounded-sm bg-ink-900 p-6 ring-wire">
        <h1 className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-500">
          Matter file
        </h1>
        <p className="mt-2 text-ink-200">
          Matter file persistence is disabled in this build.
        </p>
        <p className="mt-1 font-mono text-xs text-ink-500">
          Set <code className="text-ink-300">VITE_API_URL</code> to your Railway URL and rebuild to enable.
        </p>
      </div>
    );
  }

  const totalCount = entries.length;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-500">
            Matter file
          </h1>
          <p className="mt-0.5 text-2xl font-semibold text-ink-50">
            {totalCount} saved {totalCount === 1 ? "entry" : "entries"}
          </p>
          <p className="font-mono text-[11px] text-ink-500">
            Synced from Railway · auto-saves notes per card
          </p>
        </div>
        <div className="flex items-center gap-1 font-mono text-[11px]">
          <a
            href={api.exportMatterFileUrl()}
            target="_blank"
            rel="noreferrer"
            className="rounded-sm border border-wire-ir/50 bg-wire-ir/10 px-3 py-1.5 text-wire-ir hover:bg-wire-ir/20"
          >
            ⬇ Export .md
          </a>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-sm bg-ink-900 p-2 ring-wire">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search saved cards & notes…"
          className="min-w-[220px] flex-1 rounded-sm border border-ink-700 bg-ink-950/60 px-2 py-1 font-mono text-[12.5px] text-ink-100 placeholder:text-ink-600 focus:border-wire-ir/60 focus:outline-none"
        />
        <div className="flex items-center gap-1">
          {CATEGORY_ORDER.map((cat) => {
            const c = CATEGORIES[cat];
            const on = activeCats.has(cat);
            return (
              <button
                key={cat}
                type="button"
                onClick={() => toggleCat(cat)}
                className={`rounded-sm border px-2 py-1 font-mono text-[10.5px] uppercase tracking-wider transition ${
                  on
                    ? `${c.borderColor} ${c.bgColor} ${c.textColor}`
                    : "border-ink-700 text-ink-500 hover:text-ink-300"
                }`}
              >
                {c.label}
              </button>
            );
          })}
        </div>
      </div>

      {loading && <p className="font-mono text-sm text-ink-500">Loading…</p>}
      {error && <p className="font-mono text-sm text-red-400">Failed to load: {error}</p>}

      {!loading && !error && totalCount === 0 && (
        <div className="rounded-sm bg-ink-900 p-6 ring-wire">
          <p className="font-mono text-sm text-ink-300">No saved cards yet.</p>
          <p className="mt-2 font-mono text-xs text-ink-500">
            Click <span className="text-ink-200">+ Matter file</span> on any digest card to add it here.
          </p>
        </div>
      )}

      {!loading && !error && totalCount > 0 && visible.length === 0 && (
        <p className="font-mono text-sm text-ink-500">No entries match these filters.</p>
      )}

      {[...CATEGORY_ORDER, "_other"].map((cat) => {
        const items = grouped[cat] || [];
        if (!items.length) return null;
        return (
          <section key={cat} className="space-y-3">
            <h2 className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-400">
              {CATEGORY_HEADERS[cat]} · {items.length}
            </h2>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {items.map((entry) => (
                <MatterCard
                  key={entry.id}
                  entry={entry}
                  onRemove={handleRemove}
                  onNotesChange={handleNotesChange}
                />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
