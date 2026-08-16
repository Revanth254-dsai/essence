const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function readJson(response) {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed with ${response.status}`);
  }
  return response.json();
}

export const listSummaries = (params = {}) => {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== "")
  );
  return fetch(`${BASE}/summaries?${query}`).then(readJson);
};

export const searchSummaries = (q) =>
  fetch(`${BASE}/summaries/search?q=${encodeURIComponent(q)}`).then(readJson);

export const getSummary = (id) => fetch(`${BASE}/summaries/${id}`).then(readJson);

export const getStats = () => fetch(`${BASE}/summaries/stats`).then(readJson);

export const deleteSummary = (id) =>
  fetch(`${BASE}/summaries/${id}`, { method: "DELETE" }).then((r) => {
    if (!r.ok) throw new Error("Could not delete that summary.");
  });

/**
 * Streams a summary over SSE.
 *
 * EventSource can't be used here because the request is a POST (and can carry
 * a file), so we read the response body ourselves and parse the SSE frames.
 * Handlers: onMeta, onToken, onDone, onError.
 */
export async function streamSummary({ url, mode, file, signal }, handlers) {
  const endpoint = file ? `${BASE}/summarize/upload` : `${BASE}/summarize/stream`;

  const init = { method: "POST", signal };
  if (file) {
    const form = new FormData();
    form.append("file", file);
    form.append("mode", mode);
    init.body = form;
  } else {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify({ url, mode });
  }

  const response = await fetch(endpoint, init);

  // Ingestion errors fail before the stream opens, so they arrive as JSON.
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed with ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line. Keep the trailing partial.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      let event = "message";
      const dataLines = [];

      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (!dataLines.length) continue;

      let payload;
      try {
        payload = JSON.parse(dataLines.join("\n"));
      } catch {
        continue;
      }

      if (event === "meta") handlers.onMeta?.(payload);
      else if (event === "token") handlers.onToken?.(payload.t);
      else if (event === "done") handlers.onDone?.(payload);
      else if (event === "error") handlers.onError?.(new Error(payload.message));
    }
  }
}
