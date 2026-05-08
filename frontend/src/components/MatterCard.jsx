// Always-expanded card for the matter file page. Identical structure to the
// digest's expanded view, plus a remove button and an editable notes field
// that PATCHes back to Railway after a 600ms debounce.

import { useEffect, useRef, useState } from "react";
import ArgumentBlock from "./ArgumentBlock.jsx";
import StockTag from "./StockTag.jsx";
import { CATEGORIES } from "../lib/constants.js";
import { relativeTime } from "../lib/cards.js";
import * as api from "../lib/api.js";
import { useToast } from "./Toast.jsx";

function CategoryPill({ category }) {
  const c = CATEGORIES[category] || CATEGORIES.IR;
  return (
    <span
      className={`inline-flex items-center rounded-sm border px-1.5 py-0.5 font-mono text-[10.5px] uppercase tracking-wider ${c.borderColor} ${c.bgColor} ${c.textColor}`}
    >
      {c.label}
    </span>
  );
}

export default function MatterCard({ entry, onRemove, onNotesChange }) {
  const card = entry.card_data || {};
  const [notes, setNotes] = useState(entry.notes || "");
  const [savingNotes, setSavingNotes] = useState(false);
  const debounceRef = useRef(null);
  const lastSavedRef = useRef(entry.notes || "");
  const toast = useToast();

  useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
  }, []);

  function handleNotesChange(value) {
    setNotes(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      if (value === lastSavedRef.current) return;
      setSavingNotes(true);
      try {
        await api.updateNotes(entry.id, value);
        lastSavedRef.current = value;
        onNotesChange?.(entry.id, value);
      } catch (e) {
        toast.push(e.message || "Failed to save notes", "error");
      } finally {
        setSavingNotes(false);
      }
    }, 600);
  }

  async function handleRemove() {
    try {
      await api.removeEntry(entry.id);
      onRemove?.(entry.id);
      toast.push("Removed from matter file", "success");
    } catch (e) {
      toast.push(e.message || "Failed to remove", "error");
    }
  }

  return (
    <article className="rounded-sm bg-ink-900 ring-wire shadow-wire">
      <header className="flex items-start justify-between gap-3 px-4 pt-4">
        <div className="flex items-center gap-2 text-[11px] text-ink-400">
          <CategoryPill category={card.category} />
          {card.region && <span className="font-mono">{card.region}</span>}
        </div>
        <div className="text-right text-[11px] text-ink-500 font-mono">
          <div>{card.source}</div>
          {card.published && <div>{relativeTime(card.published)}</div>}
        </div>
      </header>

      <h2 className="px-4 pt-2 text-balance text-[17px] font-semibold leading-snug text-ink-50">
        {card.title}
      </h2>

      {card.background && (
        <p className="px-4 pt-2 text-[14px] leading-relaxed text-ink-200">
          {card.background}
        </p>
      )}

      <div className="space-y-4 px-4 pt-4">
        {(card.prop_args || []).length > 0 && (
          <div>
            <h3 className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-400 pb-2">
              Prop · {card.prop_args.length}
            </h3>
            <ArgumentBlock args={card.prop_args} side="prop" />
          </div>
        )}
        {(card.opp_args || []).length > 0 && (
          <div>
            <h3 className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-400 pb-2">
              Opp · {card.opp_args.length}
            </h3>
            <ArgumentBlock args={card.opp_args} side="opp" />
          </div>
        )}
        {card.weighing && (
          <div className="border-l-2 border-wire-ir/70 pl-3">
            <h3 className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-400 pb-1">
              Weighing
            </h3>
            <p className="font-mono text-[13px] leading-relaxed text-ink-100">
              {card.weighing}
            </p>
          </div>
        )}
        {(card.motion_areas || []).length > 0 && (
          <div>
            <h3 className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-400 pb-1">
              Motion areas
            </h3>
            <ul className="space-y-1.5">
              {card.motion_areas.map((m, i) => (
                <li key={i} className="font-mono text-[13px] text-ink-200">
                  <span className="text-ink-500">·</span> {m}
                </li>
              ))}
            </ul>
          </div>
        )}
        {(card.data_points || []).length > 0 && (
          <div>
            <h3 className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-400 pb-1">
              Data points
            </h3>
            <ul className="space-y-1.5">
              {card.data_points.map((d, i) => (
                <li key={i} className="font-mono text-[12.5px] text-ink-200">
                  <span className="text-ink-500">·</span> {d}
                </li>
              ))}
            </ul>
          </div>
        )}
        {(card.stock_connections || []).length > 0 && (
          <div className="flex flex-wrap items-center gap-1">
            <span className="font-mono text-[10.5px] uppercase tracking-wider text-ink-500">
              Stock:
            </span>
            {card.stock_connections.map((s) => (
              <StockTag key={s} name={s} />
            ))}
          </div>
        )}
      </div>

      <div className="px-4 pt-4">
        <label className="font-mono text-[10.5px] uppercase tracking-wider text-ink-500 flex items-center justify-between">
          <span>Notes</span>
          {savingNotes && <span className="text-ink-600">saving…</span>}
        </label>
        <textarea
          value={notes}
          onChange={(e) => handleNotesChange(e.target.value)}
          rows={2}
          placeholder="Add personal notes (auto-saved)…"
          className="mt-1 w-full resize-y rounded-sm border border-ink-700 bg-ink-950/60 px-2 py-1.5 font-mono text-[12.5px] text-ink-100 placeholder:text-ink-600 focus:border-wire-ir/60 focus:outline-none"
        />
      </div>

      <footer className="mt-3 flex items-center justify-between gap-2 border-t border-ink-800 px-4 py-2">
        <button
          type="button"
          onClick={handleRemove}
          className="rounded-sm border border-ink-700 px-2 py-1 font-mono text-[10.5px] uppercase tracking-wider text-ink-300 hover:border-red-500/40 hover:text-red-300"
        >
          Remove
        </button>
        {card.url && (
          <a
            href={card.url}
            target="_blank"
            rel="noreferrer"
            className="rounded-sm border border-ink-700 px-2 py-1 font-mono text-[10.5px] uppercase tracking-wider text-ink-200 hover:bg-ink-800"
          >
            Source ↗
          </a>
        )}
      </footer>
    </article>
  );
}
