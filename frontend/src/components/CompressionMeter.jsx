const format = (n) =>
  n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);

/**
 * The one thing this app does is make long things short, so the interface
 * shows that measurement directly rather than describing it. The lower bar
 * is drawn to true scale against the upper one.
 */
export default function CompressionMeter({ sourceChars, summaryChars }) {
  if (!sourceChars) return null;

  const ratio = summaryChars / sourceChars;
  const factor = summaryChars ? sourceChars / summaryChars : 0;
  // Floor the drawn width so a 0.3% bar is still visible.
  const width = Math.max(ratio * 100, 0.8);

  return (
    <div className="border border-rule rounded-md bg-surface px-4 py-3.5">
      <div className="flex items-baseline justify-between mb-3">
        <span className="eyebrow">Compression</span>
        <span className="font-mono text-sm text-accent">
          {factor >= 1 ? `${factor.toFixed(0)}× shorter` : "—"}
        </span>
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <span className="font-mono text-[11px] text-muted w-14 shrink-0">source</span>
          <div className="h-2 flex-1 rounded-full bg-rule" />
          <span className="font-mono text-[11px] text-muted w-12 text-right shrink-0">
            {format(sourceChars)}
          </span>
        </div>

        <div className="flex items-center gap-3">
          <span className="font-mono text-[11px] text-muted w-14 shrink-0">summary</span>
          <div className="h-2 flex-1 rounded-full bg-rule/40">
            <div
              className="h-2 rounded-full bg-accent transition-[width] duration-500 ease-out"
              style={{ width: `${width}%` }}
            />
          </div>
          <span className="font-mono text-[11px] text-ink w-12 text-right shrink-0">
            {format(summaryChars)}
          </span>
        </div>
      </div>
    </div>
  );
}
