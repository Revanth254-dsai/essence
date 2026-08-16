import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "./api";
import ArchiveSidebar from "./components/ArchiveSidebar";
import SourceInput from "./components/SourceInput";
import SummaryPanel from "./components/SummaryPanel";

export default function App() {
  const [meta, setMeta] = useState(null);
  const [text, setText] = useState("");
  const [done, setDone] = useState(null);
  const [error, setError] = useState(null);
  const [running, setRunning] = useState(false);

  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [stats, setStats] = useState(null);

  const abortRef = useRef(null);

  const refreshArchive = useCallback(async () => {
    try {
      if (query.trim()) {
        const result = await api.searchSummaries(query.trim());
        setItems(result.hits);
        setTotal(result.total);
      } else {
        const result = await api.listSummaries({ limit: 50 });
        setItems(result.items);
        setTotal(result.total);
      }
      setStats(await api.getStats());
    } catch (err) {
      console.error(err);
    }
  }, [query]);

  useEffect(() => {
    refreshArchive();
  }, [refreshArchive]);

  const run = async ({ url, file, mode }) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setMeta(null);
    setText("");
    setDone(null);
    setError(null);
    setSelectedId(null);
    setRunning(true);

    try {
      await api.streamSummary(
        { url, file, mode, signal: controller.signal },
        {
          onMeta: setMeta,
          onToken: (token) => setText((prev) => prev + token),
          onDone: (payload) => {
            setDone(payload);
            setSelectedId(payload.id);
            refreshArchive();
          },
          onError: (err) => setError(err.message),
        }
      );
    } catch (err) {
      if (err.name !== "AbortError") setError(err.message);
    } finally {
      setRunning(false);
    }
  };

  const stop = () => {
    abortRef.current?.abort();
    setRunning(false);
  };

  const open = async (id) => {
    setSelectedId(id);
    setRunning(false);
    setError(null);
    try {
      const record = await api.getSummary(id);
      setMeta({
        title: record.title,
        source_type: record.source_type,
        source_url: record.source_url,
        model: record.model,
        chunks: 1,
      });
      setText(record.summary_text);
      setDone({
        source_chars: record.source_chars,
        summary_chars: record.summary_chars,
        latency_ms: record.latency_ms,
      });
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="h-screen flex flex-col lg:flex-row">
      <div className="lg:w-80 xl:w-96 shrink-0 h-64 lg:h-screen">
        <ArchiveSidebar
          items={items}
          total={total}
          query={query}
          onQueryChange={setQuery}
          selectedId={selectedId}
          onSelect={open}
          stats={stats}
        />
      </div>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 lg:px-10 py-8 lg:py-12 space-y-8">
          <header className="space-y-1">
          <h1 className="font-display text-4xl tracking-[0.2em] uppercase">
              Essence
            </h1>
            <p className="text-muted text-sm">
              {stats && stats.source_chars > 0
                ? `${(stats.source_chars / 1000).toFixed(0)}k characters read, ` +
                  `${(stats.summary_chars / 1000).toFixed(1)}k kept.`
                : "Summarize a page, paper, or talk. Keep every one."}
            </p>
          </header>

          <SourceInput onSubmit={run} onStop={stop} running={running} />

          <SummaryPanel
            meta={meta}
            text={text}
            done={done}
            error={error}
            running={running}
          />
        </div>
      </main>
    </div>
  );
}
