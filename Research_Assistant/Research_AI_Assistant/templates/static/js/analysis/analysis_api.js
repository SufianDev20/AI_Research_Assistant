// Calls the multi-paper Q&A backend and the paper search backend.

const ENDPOINT = "/api/multi-paper-qa/";

// Publisher-block substrings seen in paper_errors reasons (see pdf_service.py fetch_pdf_bytes).
const PUBLISHER_BLOCK_PATTERN = /\b(403|405)\b.*(Forbidden|Not Allowed)/i;

export function isPublisherBlock(reason) {
  return typeof reason === "string" && PUBLISHER_BLOCK_PATTERN.test(reason);
}

export async function requestPaperAnalysis({ paperIds, question, pdfUrls, paperMeta, csrfToken, signal }) {
  let response;
  try {
    response = await fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: JSON.stringify({ paper_ids: paperIds, question, pdf_urls: pdfUrls, paper_meta: paperMeta }),
      signal,
    });
  } catch (networkErr) {
    if (networkErr?.name === "AbortError") throw networkErr;
    throw new Error("Could not reach the analysis service. Check your connection and try again.", { cause: networkErr });
  }

  // Body may be non-JSON on an unexpected error; treat that as an empty payload.
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = data?.error ?? (data?.details && JSON.stringify(data.details)) ?? `Analysis request failed (HTTP ${response.status}).`;
    const err = new Error(detail);
    err.status = response.status;
    err.paperErrors = data?.paper_errors ?? null;
    throw err;
  }

  return {
    answer: data?.answer ?? "",
    citations: data?.citations ?? [],
    papers: data?.papers ?? {},
    paper_errors: data?.paper_errors ?? {},
    context_trimmed: !!data?.context_trimmed,
    context_papers: data?.context_papers ?? {},
  };
}

/**
 * Streaming variant: sends the same POST but with ?stream=1.
 * Calls onToken(text), onProgress(data), onDone(result), onError(msg), and
 * onReset() when the server moved to another model mid-answer: every token
 * received before it belongs to a failed answer and must be discarded.
 */
export async function requestPaperAnalysisStream({
  paperIds, question, pdfUrls, paperMeta, csrfToken, signal,
  onToken, onProgress, onDone, onError, onReset,
}) {
  let response;
  try {
    response = await fetch(ENDPOINT + "?stream=1", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: JSON.stringify({ paper_ids: paperIds, question, pdf_urls: pdfUrls, paper_meta: paperMeta }),
      signal,
    });
  } catch (networkErr) {
    if (networkErr?.name === "AbortError") return;
    onError?.("Could not reach the analysis service. Check your connection and try again.");
    return;
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const detail = data?.error ?? `Analysis request failed (HTTP ${response.status}).`;
    onError?.(detail);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Parse complete SSE messages from the buffer.
      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);

        let eventType = "message";
        let dataLines = [];
        for (const line of block.split("\n")) {
          if (line.startsWith("event: ")) eventType = line.slice(7);
          else if (line.startsWith("data: ")) dataLines.push(line.slice(6));
        }
        if (!dataLines.length) continue;

        let parsed;
        try { parsed = JSON.parse(dataLines.join("\n")); } catch { continue; }

        if (eventType === "token") onToken?.(parsed.t ?? "");
        else if (eventType === "reset") onReset?.();
        else if (eventType === "progress") onProgress?.(parsed);
        else if (eventType === "done") onDone?.(parsed);
        else if (eventType === "error") onError?.(parsed.error ?? "Unknown streaming error");
      }
    }
  } catch (err) {
    if (err?.name === "AbortError") return;
    onError?.(err?.message || "Stream read error");
  }
}

const SEARCH_ENDPOINT = "/api/search/";

export async function fetchResearchPapers(searchParams) {
  const query = searchParams?.query;
  if (!query) throw new Error("No search query is available to reload the papers.");

  const params = new URLSearchParams({
    q: query,
    mode: searchParams.mode || "best_match",
    per_page: String(Math.min(Number(searchParams.perPage) || 25, 50)),
  });
  if (searchParams.minYear) params.set("min_year", searchParams.minYear);
  if (searchParams.maxYear) params.set("max_year", searchParams.maxYear);

  let response;
  try {
    response = await fetch(`${SEARCH_ENDPOINT}?${params}`);
  } catch (networkErr) {
    throw new Error("Could not reach the search service to reload these papers.", { cause: networkErr });
  }

  if (!response.ok) {
    const err = new Error(`Could not reload the papers for this research result (HTTP ${response.status}).`);
    err.status = response.status;
    throw err;
  }

  const data = await response.json().catch(() => null);
  return data?.papers ?? [];
}