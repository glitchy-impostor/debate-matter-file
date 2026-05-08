// Renders prop/opp arguments with numbered mechanism chains.
// The model's mechanism strings look like:
//   "First, multilateral climate agreements have failed. This is because
//    (1) free-rider incentives mean nations benefit from..., (2) enforcement
//    mechanisms in agreements like Paris are toothless, (3) consensus..."
//
// We render each mechanism as an outer numbered item (1), 2), 3)) and split
// the inline (1)(2)(3) sub-reasons onto their own lines so the causal chain
// is visually scannable mid-round.

function splitSubReasons(text) {
  // Match either "(1)" / "(2)" / ... or "one, " / "two, " / ... markers used
  // by the model. Returns the lead-in plus an array of sub-reason chunks.
  const numericPattern = /\s*\((\d+)\)\s*/;
  if (numericPattern.test(text)) {
    const parts = text.split(/\s*\((\d+)\)\s*/);
    // parts: [lead, "1", chunk1, "2", chunk2, "3", chunk3, ...]
    const lead = parts[0].trim();
    const chunks = [];
    for (let i = 1; i < parts.length; i += 2) {
      const num = parts[i];
      const chunk = (parts[i + 1] || "").trim().replace(/^,\s*/, "");
      if (chunk) chunks.push({ num, chunk });
    }
    if (chunks.length >= 2) return { lead, chunks };
  }

  const wordPattern = /\b(one|two|three|four|five),\s*/gi;
  if (wordPattern.test(text)) {
    const parts = text.split(/\b(one|two|three|four|five),\s*/gi);
    const lead = parts[0].trim();
    const chunks = [];
    for (let i = 1; i < parts.length; i += 2) {
      const num = parts[i].toLowerCase();
      const chunk = (parts[i + 1] || "").trim();
      if (chunk) chunks.push({ num, chunk });
    }
    if (chunks.length >= 2) return { lead, chunks };
  }

  return { lead: text, chunks: [] };
}

function Mechanism({ index, text }) {
  const { lead, chunks } = splitSubReasons(text);
  return (
    <li className="grid grid-cols-[1.5rem_1fr] gap-x-2">
      <span className="font-mono text-xs text-ink-500 pt-0.5 select-none">
        {index})
      </span>
      <div className="space-y-1.5">
        <p className="font-mono text-[13px] leading-relaxed text-ink-100">{lead}</p>
        {chunks.length > 0 && (
          <ol className="space-y-1 pl-3">
            {chunks.map(({ num, chunk }) => (
              <li
                key={num}
                className="grid grid-cols-[1.75rem_1fr] gap-x-1.5 font-mono text-[12.5px] leading-relaxed text-ink-300"
              >
                <span className="text-ink-500 select-none">({num})</span>
                <span>{chunk}</span>
              </li>
            ))}
          </ol>
        )}
      </div>
    </li>
  );
}

export default function ArgumentBlock({ args, side }) {
  if (!args || args.length === 0) return null;
  const sideColor = side === "prop" ? "text-wire-econ" : "text-wire-business";
  return (
    <div className="space-y-4">
      {args.map((arg, ai) => (
        <div key={ai} className="space-y-2">
          <p className={`text-sm font-medium italic ${sideColor}`}>
            {arg.thesis}
          </p>
          <ol className="space-y-3">
            {(arg.mechanisms || []).map((m, mi) => (
              <Mechanism key={mi} index={mi + 1} text={m} />
            ))}
          </ol>
        </div>
      ))}
    </div>
  );
}
