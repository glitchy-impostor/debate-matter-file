import { useState } from "react";
import ArgumentBlock from "./ArgumentBlock.jsx";
import StockTag from "./StockTag.jsx";
import { CATEGORIES } from "../lib/constants.js";
import { relativeTime } from "../lib/cards.js";
import { useMatter } from "../lib/matterContext.jsx";
import { useToast } from "./Toast.jsx";

function Section({ title, children, defaultOpen = false, accent = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const accentCls = accent
    ? "border-l-2 border-wire-ir/70 pl-3"
    : "";
  return (
    <div className={accentCls}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between py-1.5 text-left text-[12px] uppercase tracking-[0.14em] text-ink-300 hover:text-ink-100"
      >
        <span className="font-mono">{title}</span>
        <span className="text-ink-500">{open ? "−" : "+"}</span>
      </button>
      {open && <div className="pb-3 pt-1">{children}</div>}
    </div>
  );
}

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

export default function Card({ card }) {
  const [expanded, setExpanded] = useState(false);
  const matter = useMatter();
  const toast = useToast();

  const stockPreview = (card.stock_connections || []).slice(0, 3);
  const stockExtra = Math.max(0, (card.stock_connections || []).length - stockPreview.length);

  const isSaved = matter.savedIds.has(card.id);
  const isBusy = matter.busy.has(card.id);

  async function onMatterClick() {
    try {
      await matter.toggle(card);
      toast.push(isSaved ? "Removed from matter file" : "Added to matter file", "success");
    } catch (e) {
      toast.push(e.message || "Matter file action failed", "error");
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

      {!expanded && stockPreview.length > 0 && (
        <div className="flex flex-wrap items-center gap-1 px-4 pt-3">
          <span className="font-mono text-[10.5px] uppercase tracking-wider text-ink-500">
            Stock:
          </span>
          {stockPreview.map((s) => (
            <StockTag key={s} name={s} />
          ))}
          {stockExtra > 0 && (
            <span className="font-mono text-[11px] text-ink-500">+{stockExtra} more</span>
          )}
        </div>
      )}

      {expanded && (
        <div className="space-y-1 px-4 pt-3">
          <Section title={`Prop · ${(card.prop_args || []).length}`} defaultOpen>
            <ArgumentBlock args={card.prop_args} side="prop" />
          </Section>
          <Section title={`Opp · ${(card.opp_args || []).length}`} defaultOpen>
            <ArgumentBlock args={card.opp_args} side="opp" />
          </Section>
          {card.weighing && (
            <Section title="Weighing" defaultOpen accent>
              <p className="font-mono text-[13px] leading-relaxed text-ink-100">
                {card.weighing}
              </p>
            </Section>
          )}
          {(card.motion_areas || []).length > 0 && (
            <Section title="Motion areas">
              <ul className="space-y-1.5">
                {card.motion_areas.map((m, i) => (
                  <li key={i} className="font-mono text-[13px] text-ink-200">
                    <span className="text-ink-500">·</span> {m}
                  </li>
                ))}
              </ul>
            </Section>
          )}
          {(card.data_points || []).length > 0 && (
            <Section title="Data points">
              <ul className="space-y-1.5">
                {card.data_points.map((d, i) => (
                  <li key={i} className="font-mono text-[12.5px] text-ink-200">
                    <span className="text-ink-500">·</span> {d}
                  </li>
                ))}
              </ul>
            </Section>
          )}
          {(card.stock_connections || []).length > 0 && (
            <div className="flex flex-wrap items-center gap-1 pt-2">
              <span className="font-mono text-[10.5px] uppercase tracking-wider text-ink-500">
                Stock:
              </span>
              {card.stock_connections.map((s) => (
                <StockTag key={s} name={s} />
              ))}
            </div>
          )}
        </div>
      )}

      <footer className="mt-3 flex items-center justify-between gap-2 border-t border-ink-800 px-4 py-2">
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="font-mono text-[11px] uppercase tracking-wider text-ink-300 hover:text-ink-100"
        >
          {expanded ? "Collapse ▴" : "Expand ▾"}
        </button>
        <div className="flex items-center gap-2">
          {matter.enabled && (
            <button
              type="button"
              onClick={onMatterClick}
              disabled={isBusy}
              title={isSaved ? "Remove from matter file" : "Add to matter file"}
              className={`rounded-sm border px-2 py-1 font-mono text-[10.5px] uppercase tracking-wider transition ${
                isSaved
                  ? "border-wire-econ/50 bg-wire-econ/10 text-wire-econ"
                  : "border-ink-700 text-ink-200 hover:bg-ink-800"
              } ${isBusy ? "opacity-50" : ""}`}
            >
              {isSaved ? "✓ In matter file" : "+ Matter file"}
            </button>
          )}
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
        </div>
      </footer>
    </article>
  );
}
