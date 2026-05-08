import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Card from "../components/Card.jsx";
import FilterBar from "../components/FilterBar.jsx";
import { CATEGORIES } from "../lib/constants.js";
import { adjacentDate, formatDate, loadDay, loadIndex, relativeTime } from "../lib/cards.js";

export default function Digest() {
  const { date } = useParams();
  const navigate = useNavigate();

  const [index, setIndex] = useState(null);
  const [resolvedDate, setResolvedDate] = useState(date || null);
  const [day, setDay] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const [categories, setCategories] = useState(() => new Set(Object.keys(CATEGORIES)));
  const [query, setQuery] = useState("");
  const [region, setRegion] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const idx = await loadIndex();
        if (cancelled) return;
        setIndex(idx);
        const target = date || idx.dates?.[0] || new Date().toISOString().slice(0, 10);
        setResolvedDate(target);
        const data = await loadDay(target);
        if (!cancelled) setDay(data);
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [date]);

  const cards = day?.cards || [];

  const counts = useMemo(() => {
    const c = { IR: 0, Econ: 0, Business: 0 };
    cards.forEach((card) => {
      if (c[card.category] != null) c[card.category] += 1;
    });
    return c;
  }, [cards]);

  const regions = useMemo(() => {
    const set = new Set();
    cards.forEach((c) => c.region && set.add(c.region));
    return Array.from(set).sort();
  }, [cards]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return cards.filter((c) => {
      if (!categories.has(c.category)) return false;
      if (region && c.region !== region) return false;
      if (!q) return true;
      const haystack = JSON.stringify(c).toLowerCase();
      return haystack.includes(q);
    });
  }, [cards, categories, region, query]);

  const toggleCategory = (cat) => {
    setCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  const goPrev = () => navigate(`/d/${adjacentDate(resolvedDate, -1)}`);
  const goNext = () => navigate(`/d/${adjacentDate(resolvedDate, 1)}`);
  const goToday = () => navigate("/");

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-500">
            Daily digest
          </h1>
          <p className="mt-0.5 text-2xl font-semibold text-ink-50">
            {resolvedDate ? formatDate(resolvedDate) : "…"}
          </p>
          {index?.last_updated && (
            <p className="font-mono text-[11px] text-ink-500">
              Index updated {relativeTime(index.last_updated)} · {cards.length} cards on this day
            </p>
          )}
        </div>
        <div className="flex items-center gap-1 font-mono text-[11px]">
          <button onClick={goPrev} className="rounded-sm border border-ink-700 px-2 py-1 text-ink-300 hover:bg-ink-800">
            ← Prev
          </button>
          <button onClick={goToday} className="rounded-sm border border-ink-700 px-2 py-1 text-ink-300 hover:bg-ink-800">
            Today
          </button>
          <button onClick={goNext} className="rounded-sm border border-ink-700 px-2 py-1 text-ink-300 hover:bg-ink-800">
            Next →
          </button>
        </div>
      </div>

      <FilterBar
        categories={categories}
        toggleCategory={toggleCategory}
        query={query}
        setQuery={setQuery}
        region={region}
        setRegion={setRegion}
        regions={regions}
        counts={counts}
      />

      {loading && (
        <p className="font-mono text-sm text-ink-500">Loading…</p>
      )}
      {error && (
        <p className="font-mono text-sm text-red-400">Failed to load: {error}</p>
      )}
      {!loading && !error && visible.length === 0 && (
        <div className="rounded-sm bg-ink-900 p-6 ring-wire">
          <p className="font-mono text-sm text-ink-300">
            No cards match these filters{cards.length === 0 ? " (no cards on this day yet)" : ""}.
          </p>
          {cards.length === 0 && (
            <p className="mt-2 font-mono text-xs text-ink-500">
              Try the <Link className="text-wire-ir hover:underline" to="/archive">archive</Link> for an earlier day.
            </p>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {visible.map((c) => (
          <Card key={c.id} card={c} />
        ))}
      </div>
    </div>
  );
}
