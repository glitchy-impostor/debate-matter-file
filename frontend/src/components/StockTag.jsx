import { CANONICAL_STOCK_ARGS } from "../lib/constants.js";

export default function StockTag({ name }) {
  const canonical = CANONICAL_STOCK_ARGS.has(name);
  const cls = canonical
    ? "border-ink-500/60 bg-ink-700/40 text-ink-200"
    : "border-ink-600/40 bg-ink-800/40 text-ink-400";
  return (
    <span
      className={`inline-flex items-center rounded-sm border px-1.5 py-0.5 font-mono text-[10.5px] uppercase tracking-wider ${cls}`}
    >
      {name}
    </span>
  );
}
