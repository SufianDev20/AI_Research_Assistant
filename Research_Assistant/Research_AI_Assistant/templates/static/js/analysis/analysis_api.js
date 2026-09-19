// ============================================================================
// Scholara — paper analysis backend integration
//
// This is the ONE function analysis.js calls to get a real answer. It
// talks to the already-implemented POST /api/multi-paper-qa/ endpoint
// (Research_AI_Assistant.views.multi_paper_qa, registered in urls.py as
// "multi_paper_qa" — found already wired into no UI when this page was
// built, so this is its first real caller).
//
// Request body   (QARequestSerializer in serializers.py):
//   { paper_ids: string[1..10], question: string(1..2000), pdf_urls: {id: url} }
// Response body on 200:
//   { answer: string,
//     citations: [{ paper_id, page, quoted_snippet, page_exists, text_verified }],
//     paper_errors: { [paper_id]: string } }
// Error statuses the view explicitly returns: 400, 413, 422, 502; plus
// whatever the network/fetch layer itself can raise (offline, timeout).
//
// See the "Backend handoff" note in the project report for the gap
// between what this endpoint already returns (one shared answer + a
// flat citations list keyed by paper_id) and the ideal shape described
// in the brief (a true per-paper answer) — analysis.js groups citations
// by paper_id client-side to approximate that today.
// ============================================================================

const ENDPOINT = "/api/multi-paper-qa/";

/**
 * @param {Object} params
 * @param {string[]} params.paperIds - OpenAlex work IDs, 1-10 entries.
 * @param {string} params.question - trimmed, non-empty, <=2000 chars.
 * @param {Object<string,string>} params.pdfUrls - paper_id -> direct PDF url,
 *   one entry for every id in paperIds (the backend rejects a mismatch).
 * @param {string} params.csrfToken
 * @param {AbortSignal} [params.signal] - lets analysis.js cancel a
 *   still-in-flight request if the user submits a newer question first.
 * @returns {Promise<{answer:string, citations:Array, paper_errors:Object}>}
 */
export async function requestPaperAnalysis({ paperIds, question, pdfUrls, csrfToken, signal }) {
  let response;
  try {
    response = await fetch(ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify({
        paper_ids: paperIds,
        question,
        pdf_urls: pdfUrls,
      }),
      signal,
    });
  } catch (networkErr) {
    if (networkErr && networkErr.name === "AbortError") throw networkErr;
    const err = new Error("Could not reach the analysis service. Check your connection and try again.");
    err.cause = networkErr;
    throw err;
  }

  let data = null;
  try {
    data = await response.json();
  } catch (parseErr) {
    // Non-JSON body (unexpected). Fall through with data = null so the
    // status-based message below still fires instead of throwing here.
  }

  if (!response.ok) {
    const detail =
      (data && (data.error || (data.details && JSON.stringify(data.details)))) ||
      `Analysis request failed (HTTP ${response.status}).`;
    const err = new Error(detail);
    err.status = response.status;
    err.paperErrors = (data && data.paper_errors) || null;
    throw err;
  }

  return {
    answer: (data && data.answer) || "",
    citations: (data && data.citations) || [],
    paper_errors: (data && data.paper_errors) || {},
  };
}

const SEARCH_ENDPOINT = "/api/search/";

export async function fetchResearchPapers(searchParams) {
  const query = searchParams && searchParams.query;
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
    response = await fetch(`${SEARCH_ENDPOINT}?${params.toString()}`);
  } catch (networkErr) {
    const err = new Error("Could not reach the search service to reload these papers.");
    err.cause = networkErr;
    throw err;
  }

  if (!response.ok) {
    const err = new Error(`Could not reload the papers for this research result (HTTP ${response.status}).`);
    err.status = response.status;
    throw err;
  }

  const data = await response.json().catch(() => null);
  return (data && data.papers) || [];
}
