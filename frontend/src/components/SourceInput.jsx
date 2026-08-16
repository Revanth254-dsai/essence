import { useRef, useState } from "react";

const MODES = [
  { id: "bullets", label: "Bullets", hint: "5 key points" },
  { id: "tldr", label: "TL;DR", hint: "One paragraph" },
  { id: "keyfacts", label: "Key facts", hint: "5 numbered facts" },
];

export default function SourceInput({ onSubmit, onStop, running }) {
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState("bullets");
  const [file, setFile] = useState(null);
  const fileInput = useRef(null);

  const submit = () => {
    if (running) return;
    if (file) onSubmit({ file, mode });
    else if (url.trim()) onSubmit({ url: url.trim(), mode });
  };

  const pickFile = (event) => {
    const chosen = event.target.files?.[0];
    if (chosen) {
      setFile(chosen);
      setUrl("");
    }
  };

  const clearFile = () => {
    setFile(null);
    if (fileInput.current) fileInput.current.value = "";
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row gap-2">
        {file ? (
          <div className="field flex items-center justify-between gap-3">
            <span className="truncate">
              <span className="font-mono text-xs text-src-pdf mr-2">PDF</span>
              {file.name}
            </span>
            <button
              onClick={clearFile}
              className="text-muted hover:text-ink text-sm shrink-0"
            >
              Remove
            </button>
          </div>
        ) : (
          <input
            className="field"
            type="url"
            inputMode="url"
            placeholder="Paste an article, PDF, or YouTube link"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
          />
        )}

        <div className="flex gap-2 shrink-0">
          <button
            onClick={() => fileInput.current?.click()}
            className="px-3 py-2.5 border border-rule rounded-md bg-surface text-sm
                       hover:border-accent hover:text-accent transition-colors"
            title="Upload a PDF"
          >
            Upload
          </button>
          <input
            ref={fileInput}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={pickFile}
          />

          {running ? (
            <button
              onClick={onStop}
              className="px-5 py-2.5 rounded-md bg-ink text-paper text-sm font-medium"
            >
              Stop
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={!url.trim() && !file}
              className="px-5 py-2.5 rounded-md bg-accent text-white text-sm font-medium
                         disabled:opacity-35 disabled:cursor-not-allowed
                         hover:brightness-110 transition-all"
            >
              Summarize
            </button>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <span className="eyebrow mr-1">Style</span>
        {MODES.map((m) => (
          <button
            key={m.id}
            onClick={() => setMode(m.id)}
            title={m.hint}
            className={`px-3 py-1 rounded-full text-xs border transition-colors ${
              mode === m.id
                ? "border-accent bg-accent-soft text-accent font-medium"
                : "border-rule text-muted hover:border-muted"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>
    </div>
  );
}
