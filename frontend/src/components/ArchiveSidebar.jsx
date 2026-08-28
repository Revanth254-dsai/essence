import { useEffect, useState } from "react";

import { SourceBadge } from "./SummaryPanel";

function Highlighted({ text }) {
  const parts = String(text ?? "").split(/\[\[HL\]\]|\[\[\/HL\]\]/);
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <mark key={i} className="bg-accent-soft text-accent px-0.5 rounded-sm">
            {part}
          </mark>
        ) : (
          part
        )
      )}
    </>
  );
}

const relativeDate = (iso) => {
  const days = Math.floor((Date.now() - new Date(iso)) / 86_400_000);
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
};

function Entry({ item, active, onSelect }) {
  return (
    <button
      onClick={() => onSelect(item.id)}
      className={`w-full text-left px-3 py-2.5 rounded-md border transition-colors ${
        active
          ? "border-accent bg-accent-soft/50"
          : "border-transparent hover:bg-surface hover:border-rule"
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        <SourceBadge type={item.source_type} />
        <span className="font-mono text-[10px] text-muted">
          {relativeDate(item.created_at)}
        </span>
      </div>
      <p className="text-sm leading-snug line-clamp-2">{item.title}</p>
      {item.snippet && (
        <p className="text-xs text-muted mt-1.5 leading-relaxed line-clamp-3">
          <Highlighted text={item.snippet} />
        </p>
      )}
    </button>
  );
}

export default function ArchiveSidebar({
  items,
  total,
  query,
  onQueryChange,
  selectedId,
  onSelect,
  stats,
}) {
  const [draft, setDraft] = useState(query);

  useEffect(() => {
    const timer = setTimeout(() => onQueryChange(draft), 250);
    return () => clearTimeout(timer);
  }, [draft]);

  return (
    <aside className="flex flex-col h-full border-r border-rule bg-paper">
      <div className="px-4 pt-5 pb-3 space-y-3">
        <div className="flex items-baseline justify-between">
          <span className="eyebrow">Archive</span>
          {stats && (
            <span className="font-mono text-[11px] text-muted">
              {stats.total} saved
            </span>
          )}
        </div>
        <input
          className="field text-sm"
          type="search"
          placeholder="Search summaries"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        {query && (
          <p className="font-mono text-[11px] text-muted">
            {total} match{total === 1 ? "" : "es"} for “{query}”
          </p>
        )}
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-1">
        {items.length === 0 ? (
          <p className="text-sm text-muted px-3 py-6 leading-relaxed">
            {query
              ? "Nothing matched. Try fewer words, or put a phrase in quotes."
              : "Summaries you create will collect here."}
          </p>
        ) : (
          items.map((item) => (
            <Entry
              key={item.id}
              item={item}
              active={item.id === selectedId}
              onSelect={onSelect}
            />
          ))
        )}
      </div>
      {query && (
        <div className="px-4 py-2.5 border-t border-rule">
          <p className="font-mono text-[10px] text-muted leading-relaxed">
            "exact phrase" · term OR term · -exclude
          </p>
        </div>
      )}
    </aside>
  );
}