import CompressionMeter from "./CompressionMeter";

export const SOURCE_STYLES = {
  html: { label: "Web", className: "text-src-html" },
  pdf: { label: "PDF", className: "text-src-pdf" },
  youtube: { label: "Video", className: "text-src-youtube" },
};

export function SourceBadge({ type }) {
  const style = SOURCE_STYLES[type] ?? SOURCE_STYLES.html;
  return (
    <span className={`font-mono text-[11px] tracking-wide ${style.className}`}>
      {style.label.toUpperCase()}
    </span>
  );
}

function EmptyState() {
  return (
    <div className="border border-dashed border-rule rounded-lg px-6 py-16 text-center">
      <p className="font-display text-2xl mb-2">Start with a link.</p>
      <p className="text-muted text-sm max-w-sm mx-auto">
        Articles, research PDFs, and YouTube talks all go through the same
        pipeline. Everything you summarize is saved and searchable.
      </p>
    </div>
  );
}

export default function SummaryPanel({ meta, text, done, error, running }) {
  if (error) {
    return (
      <div className="border border-src-youtube/30 bg-src-youtube/5 rounded-lg px-5 py-4">
        <p className="eyebrow mb-1.5" style={{ color: "var(--color-src-youtube)" }}>
          Could not summarize
        </p>
        <p className="text-sm">{error}</p>
      </div>
    );
  }

  if (!meta && !text) return <EmptyState />;

  return (
    <div className="space-y-5">
      {meta && (
        <div>
          <div className="flex items-center gap-2.5 mb-1.5">
            <SourceBadge type={meta.source_type} />
            <span className="font-mono text-[11px] text-muted">
              {meta.model}
              {meta.chunks > 1 && ` · ${meta.chunks} chunks`}
            </span>
          </div>
          <h2 className="font-display text-3xl leading-tight tracking-tight">
            {meta.title}
          </h2>
          {meta.source_url && (
            <a
              href={meta.source_url}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-muted hover:text-accent break-all"
            >
              {meta.source_url}
            </a>
          )}
        </div>
      )}

      {done && (
        <CompressionMeter
          sourceChars={done.source_chars}
          summaryChars={done.summary_chars}
        />
      )}

      <article
        className={`font-display text-[1.0625rem] leading-[1.75] whitespace-pre-wrap ${
          running ? "caret" : ""
        }`}
      >
        {text}
      </article>

      {done && (
        <p className="font-mono text-[11px] text-muted pt-1">
          {(done.latency_ms / 1000).toFixed(1)}s · saved to archive
        </p>
      )}
    </div>
  );
}
