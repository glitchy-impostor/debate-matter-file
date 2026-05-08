import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CATEGORIES } from "../lib/constants.js";
import { formatDate, loadDay, loadIndex } from "../lib/cards.js";

export default function Archive() {
  const [index, setIndex] = useState(null);
  const [breakdowns, setBreakdowns] = useState({});
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const idx = await loadIndex();
        if (cancelled) return;
        setIndex(idx);
        // Best-effort per-day breakdown — small files, fetched in parallel.
        const dates = (idx.dates || []).slice(0, 60);
        const results = await Promise.all(
          dates.map((d) =>
            loadDay(d)
              .then((day) => [d, day.cards || []])
              .catch(() => [d, []]),
          ),
        );
        if (cancelled) return;
        const out = {};
        for (const [d, cards] of results) {
          const counts = { IR: 0, Econ: 0, Business: 0, total: cards.length };
          cards.forEach((c) => {
            if (counts[c.category] != null) counts[c.category] += 1;
          });
          out[d] = counts;
        }
        setBreakdowns(out);
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) return <p className="font-mono text-sm text-red-400">Failed to load: {error}</p>;
  if (!index) return <p className="font-mono text-sm text-ink-500">Loading…</p>;
  const dates = index.dates || [];
  if (dates.length === 0) {
    return (
      <p className="font-mono text-sm text-ink-300">
        Archive is empty — the pipeline hasn't produced any cards yet.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-500">
          Archive
        </h1>
        <p className="mt-0.5 text-2xl font-semibold text-ink-50">
          {dates.length} days · {index.total_cards} cards total
        </p>
      </div>
      <ul className="divide-y divide-ink-800 rounded-sm bg-ink-900 ring-wire shadow-wire">
        {dates.map((d) => {
          const b = breakdowns[d];
          return (
            <li key={d}>
              <Link
                to={`/d/${d}`}
                className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-ink-800/60"
              >
                <div>
                  <div className="text-sm text-ink-100">{formatDate(d)}</div>
                  <div className="font-mono text-[11px] text-ink-500">{d}</div>
                </div>
                <div className="flex items-center gap-2 font-mono text-[11px]">
                  {b ? (
                    <>
                      {Object.keys(CATEGORIES).map((cat) => {
                        const n = b[cat] || 0;
                        if (!n) return null;
                        const c = CATEGORIES[cat];
                        return (
                          <span
                            key={cat}
                            className={`rounded-sm border px-1.5 py-0.5 text-[10.5px] uppercase tracking-wider ${c.borderColor} ${c.bgColor} ${c.textColor}`}
                          >
                            {c.label} {n}
                          </span>
                        );
                      })}
                      <span className="text-ink-400">{b.total} total</span>
                    </>
                  ) : (
                    <span className="text-ink-500">…</span>
                  )}
                </div>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
