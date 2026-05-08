import { CATEGORIES } from "../lib/constants.js";

export default function FilterBar({
  categories,
  toggleCategory,
  query,
  setQuery,
  region,
  setRegion,
  regions,
  counts,
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-sm bg-ink-900 px-3 py-2 ring-wire shadow-wire">
      <div className="flex items-center gap-1">
        {Object.keys(CATEGORIES).map((cat) => {
          const active = categories.has(cat);
          const c = CATEGORIES[cat];
          const cls = active
            ? `${c.bgColor} ${c.textColor} ${c.borderColor}`
            : "border-ink-700 bg-ink-800 text-ink-400 hover:text-ink-200";
          return (
            <button
              key={cat}
              type="button"
              onClick={() => toggleCategory(cat)}
              className={`rounded-sm border px-2 py-1 font-mono text-[10.5px] uppercase tracking-wider ${cls}`}
            >
              {c.label} {counts?.[cat] != null && (
                <span className="ml-1 text-ink-500">{counts[cat]}</span>
              )}
            </button>
          );
        })}
      </div>

      <div className="h-5 w-px bg-ink-700" />

      <select
        value={region}
        onChange={(e) => setRegion(e.target.value)}
        className="rounded-sm border border-ink-700 bg-ink-800 px-2 py-1 font-mono text-[11px] text-ink-200 focus:border-ink-500 focus:outline-none"
      >
        <option value="">All regions</option>
        {regions.map((r) => (
          <option key={r} value={r}>
            {r}
          </option>
        ))}
      </select>

      <div className="h-5 w-px bg-ink-700" />

      <input
        type="text"
        placeholder="Search title, background, mechanisms…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="min-w-[18rem] flex-1 rounded-sm border border-ink-700 bg-ink-800 px-2 py-1 font-mono text-[12px] text-ink-100 placeholder:text-ink-500 focus:border-ink-500 focus:outline-none"
      />
    </div>
  );
}
