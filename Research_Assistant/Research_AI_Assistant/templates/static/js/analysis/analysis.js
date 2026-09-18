// ============================================================================
// Scholara — paper analysis page controller
//
// Hydrates entirely from sessionStorage (written by the workspace's
// follow-up box — see handleFollowUpQuestion() in
// static/js/research.js). No paper content ever travels in the URL.
// Key: "scholara:analysisSession" — kept in sync in both files; if you
// change this shape, update both.
//   { researchId: string, sourceQuery: string, question: string,
//     papers: Array<paper>, createdAt: number }
// `paper` is the same shape /api/search/ already returns (see
// services/extract_service.py ExtractionService.extract_metadata):
// openalex_id, title, authors[{name,orcid,institutions[]}], abstract,
// publication_year, doi, cited_by_count, source, is_open_access,
// oa_status, has_pdf_link, pdf_url, oa_url, concepts[], ...
// ============================================================================

import { requestPaperAnalysis } from "./analysis_api.js";

const SESSION_KEY = "scholara:analysisSession";
const MAX_ANALYZABLE_PAPERS = 10; // QARequestSerializer caps paper_ids at 10

function getCsrfToken() {
  const input = document.querySelector('[name=csrfmiddlewaretoken]');
  if (input && input.value) return input.value;
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function escapeHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatAuthors(paper, limit = 3) {
  const authors = Array.isArray(paper && paper.authors) ? paper.authors : [];
  if (!authors.length) return "";
  const names = authors.map((a) => a && a.name).filter(Boolean);
  if (!names.length) return "";
  if (names.length <= limit) return names.join(", ");
  return names.slice(0, limit).join(", ") + ", et al.";
}

// A simple, honest derivation from fields already on the paper object —
// not a fabricated citation. Falls back gracefully as fields go missing.
function buildCitationLine(paper) {
  if (!paper) return "";
  const authors = formatAuthors(paper, 6) || "Unknown authors";
  const year = paper.publication_year ? ` (${paper.publication_year}).` : ".";
  const title = paper.title ? ` ${paper.title}.` : "";
  const source = paper.source ? ` ${paper.source}.` : "";
  const doi = paper.doi ? ` ${paper.doi}` : "";
  return `${authors}${year}${title}${source}${doi}`.trim();
}

function paperBadgeHtml(paper) {
  if (paper.is_open_access && paper.has_pdf_link) {
    return '<span class="an-badge">Open access · PDF</span>';
  }
  if (paper.is_open_access) {
    return '<span class="an-badge">Open access</span>';
  }
  return '<span class="an-badge an-badge--muted">No full text</span>';
}

// ==================== state ====================
const state = {
  session: null,
  selectedIndex: -1,
  analysisAbort: null,
};

// ==================== elements ====================
const els = {};
function cacheElements() {
  els.recover = document.getElementById("anRecover");
  els.recoverMessage = document.getElementById("anRecoverMessage");
  els.shell = document.getElementById("anShell");
  els.sourceQuery = document.getElementById("anSourceQuery");
  els.paperCount = document.getElementById("anPaperCount");
  els.paperList = document.getElementById("anPaperList");
  els.paperDetail = document.getElementById("anPaperDetail");
  els.questionText = document.getElementById("anQuestionText");
  els.analysisBody = document.getElementById("anAnalysisBody");
  els.composer = document.getElementById("anComposer");
  els.questionInput = document.getElementById("anQuestionInput");
  els.questionSend = document.getElementById("anQuestionSend");
}

// ==================== session (sessionStorage) ====================
function loadSession() {
  let raw;
  try {
    raw = sessionStorage.getItem(SESSION_KEY);
  } catch (err) {
    return null; // storage unavailable (private mode, disabled, etc.)
  }
  if (!raw) return null;
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    return null;
  }
  if (!parsed || typeof parsed !== "object") return null;
  if (!Array.isArray(parsed.papers)) return null;
  if (typeof parsed.question !== "string" || !parsed.question.trim()) return null;
  return parsed;
}

function saveSession(session) {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch (err) {
    // Non-fatal: page keeps working from in-memory state for this load;
    // a refresh afterward may lose the latest follow-up question.
    console.warn("Could not persist analysis session:", err);
  }
}

function showRecovery(message) {
  if (message && els.recoverMessage) els.recoverMessage.textContent = message;
  if (els.recover) els.recover.hidden = false;
  if (els.shell) els.shell.hidden = true;
}

// ==================== rendering: top bar ====================
function renderTopBar() {
  if (els.sourceQuery) {
    els.sourceQuery.textContent = state.session.sourceQuery || state.session.question;
  }
}

// ==================== rendering: middle (paper list) ====================
function renderPaperList() {
  const papers = state.session.papers;
  if (els.paperCount) {
    els.paperCount.textContent = papers.length
      ? `${papers.length} paper${papers.length === 1 ? "" : "s"}`
      : "";
  }
  if (!els.paperList) return;

  if (!papers.length) {
    els.paperList.innerHTML =
      '<div class="an-paper-list__empty">No papers were retrieved for this research result.</div>';
    return;
  }

  els.paperList.innerHTML = "";
  papers.forEach((paper, i) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "an-paper-card";
    card.setAttribute("role", "listitem");
    card.setAttribute("aria-current", i === state.selectedIndex ? "true" : "false");

    const metaParts = [];
    if (paper.publication_year) metaParts.push(paper.publication_year);
    const authors = formatAuthors(paper, 2);
    if (authors) metaParts.push(authors);
    if (paper.source) metaParts.push(paper.source);

    const cited = paper.cited_by_count
      ? `<span class="an-paper-card__cited">${paper.cited_by_count.toLocaleString()} citations</span>`
      : "";

    card.innerHTML = `
      <div class="an-paper-card__title">${escapeHtml(paper.title || "Untitled")}</div>
      <div class="an-paper-card__meta">${escapeHtml(metaParts.join(" · "))}</div>
      <div class="an-paper-card__foot">${paperBadgeHtml(paper)}${cited}</div>
    `;
    card.addEventListener("click", () => selectPaper(i));
    els.paperList.appendChild(card);
  });
}

function updateActiveCard() {
  if (!els.paperList) return;
  const cards = els.paperList.querySelectorAll(".an-paper-card");
  cards.forEach((card, i) => {
    card.setAttribute("aria-current", i === state.selectedIndex ? "true" : "false");
  });
}

// ==================== rendering: left (refined paper) ====================
function selectPaper(index) {
  state.selectedIndex = index;
  updateActiveCard();
  renderPaperDetail(state.session.papers[index]);
}

function renderPaperDetail(paper) {
  if (!els.paperDetail) return;
  if (!paper) {
    els.paperDetail.innerHTML = `
      <div class="an-detail__idle">
        <p>Select a paper from the list to see its details here.</p>
      </div>`;
    return;
  }

  const authors = formatAuthors(paper, 8);
  const metaParts = [];
  if (paper.publication_year) metaParts.push(String(paper.publication_year));
  if (paper.source) metaParts.push(paper.source);
  if (typeof paper.cited_by_count === "number") {
    metaParts.push(`${paper.cited_by_count.toLocaleString()} citations`);
  }

  const linkUrl = paper.pdf_url || paper.oa_url || (paper.doi ? `https://doi.org/${paper.doi}` : null);
  const linkHtml = linkUrl
    ? `<a class="an-detail__link" href="${escapeHtml(linkUrl)}" target="_blank" rel="noopener noreferrer">View source ↗</a>`
    : "";

  // Fields the base search metadata doesn't carry today (a written
  // summary / methodology / findings breakdown). Only rendered if the
  // backend later attaches them to the paper object — never fabricated
  // here. See the "Backend handoff" note for the proposed field names.
  const optionalSections = ["summary", "methodology", "findings"]
    .filter((key) => paper[key] && String(paper[key]).trim())
    .map(
      (key) => `
      <div class="an-detail__section">
        <h4>${key}</h4>
        <p>${escapeHtml(paper[key])}</p>
      </div>`
    )
    .join("");

  els.paperDetail.innerHTML = `
    <h3 class="an-detail__title">${escapeHtml(paper.title || "Untitled")}</h3>
    ${authors ? `<p class="an-detail__authors">${escapeHtml(authors)}</p>` : ""}
    <div class="an-detail__meta">
      ${metaParts.map((p) => `<span>${escapeHtml(p)}</span>`).join("")}
      ${paperBadgeHtml(paper)}
    </div>
    <div class="an-detail__section">
      <h4>Abstract</h4>
      <p>${paper.abstract ? escapeHtml(paper.abstract) : "No abstract available for this paper."}</p>
    </div>
    ${optionalSections}
    <div class="an-detail__section">
      <h4>Citation</h4>
      <p class="an-detail__citation">${escapeHtml(buildCitationLine(paper))}</p>
      ${linkHtml}
    </div>
  `;
}

// ==================== rendering: right (question + analysis) ====================
function renderQuestion() {
  if (els.questionText) els.questionText.textContent = state.session.question;
}

function renderAnalysisPending(active, excluded) {
  if (!els.analysisBody) return;
  els.analysisBody.innerHTML = `
    ${excludedPapersNote(excluded || [])}
    <div class="an-pending${active ? " an-pending--active" : ""}">
      <svg class="an-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><use href="#i-eye"></use></svg>
      <p>${active ? "Analyzing across your papers…" : "Analysis will appear here."}</p>
    </div>
  `;
}

function excludedPapersNote(excluded) {
  if (!excluded.length) return "";
  const list = excluded.map((p) => escapeHtml(p.title || "Untitled")).join("; ");
  return `<div class="an-note">
    <strong>${excluded.length} paper${excluded.length === 1 ? "" : "s"} not analyzed</strong> —
    no fetchable full text was found, so ${excluded.length === 1 ? "it was" : "they were"} skipped: ${list}
  </div>`;
}

function renderAnalysisResult(result, excluded) {
  if (!els.analysisBody) return;
  const { answer, citations, paper_errors } = result;

  const byPaper = new Map();
  (citations || []).forEach((c) => {
    const key = c.paper_id || "unknown";
    if (!byPaper.has(key)) byPaper.set(key, []);
    byPaper.get(key).push(c);
  });

  const findPaperTitle = (paperId) => {
    const found = state.session.papers.find((p) => p.openalex_id === paperId);
    return found ? found.title || "Untitled" : paperId;
  };

  let evidenceHtml = "";
  if (byPaper.size) {
    evidenceHtml += '<div class="an-evidence__head">Evidence by paper</div>';
    byPaper.forEach((cites, paperId) => {
      const rows = cites
        .map((c) => {
          const page = c.page_exists && c.page ? `p.${c.page}` : "page unverified";
          const verified = c.text_verified
            ? '<span class="an-citation__verified">verified</span>'
            : "";
          return `<div class="an-citation">
            <span class="an-citation__page">${escapeHtml(page)}</span>
            <span class="an-citation__snippet">“${escapeHtml(c.quoted_snippet || "")}”${verified}</span>
          </div>`;
        })
        .join("");
      evidenceHtml += `<div class="an-evidence-group">
        <div class="an-evidence-group__paper">${escapeHtml(findPaperTitle(paperId))}</div>
        ${rows}
      </div>`;
    });
  }

  const errorEntries = Object.entries(paper_errors || {});
  const errorsHtml = errorEntries.length
    ? errorEntries
        .map(
          ([paperId, reason]) =>
            `<div class="an-note an-note--error"><strong>${escapeHtml(findPaperTitle(paperId))}:</strong> ${escapeHtml(reason)}</div>`
        )
        .join("")
    : "";

  const answerHtml = answer
    ? answer
        .split(/\n{2,}/)
        .map((p) => `<p>${escapeHtml(p.trim())}</p>`)
        .join("")
    : "";

  const nothingReturned = !answer && !byPaper.size && !errorEntries.length;

  els.analysisBody.innerHTML = `
    ${answerHtml ? `<div class="an-answer">${answerHtml}</div>` : ""}
    ${nothingReturned ? '<div class="an-note">No grounded evidence was returned for this question.</div>' : ""}
    ${evidenceHtml}
    ${errorsHtml}
    ${excludedPapersNote(excluded)}
  `;
}

function renderAnalysisError(err, onRetry, excluded) {
  if (!els.analysisBody) return;

  // A 413 means this exact request (these papers, at their current size)
  // cannot fit the model's context budget — the backend token-budget
  // that decides this is fixed server-side (see the project notes: this
  // needs a real redesign, tracked separately). Retrying with the same
  // papers and question will hit the identical limit again, so offering
  // "Try again" here would be a false promise. The only thing that can
  // actually change the outcome today is picking a different, smaller
  // set of papers, and the only way to do that from this page is to go
  // back and start a new search.
  const isTooLarge = err && err.status === 413;

  els.analysisBody.innerHTML = `
    ${excludedPapersNote(excluded || [])}
    <div class="an-note an-note--error">
      ${
        isTooLarge
          ? `<strong>These papers are too large to analyze together.</strong> The combined text of the selected papers is more than this analysis can process in one request. Go back and start a narrower search — fewer or shorter papers are more likely to fit.`
          : `<strong>Analysis failed.</strong> ${escapeHtml(err && err.message ? err.message : "Unknown error.")}`
      }
    </div>
  `;

  if (isTooLarge) {
    const backBtn = document.createElement("a");
    backBtn.className = "an-retry";
    backBtn.href = "/workspace/";
    backBtn.textContent = "Back to research";
    els.analysisBody.appendChild(backBtn);
    return;
  }

  const retryBtn = document.createElement("button");
  retryBtn.type = "button";
  retryBtn.className = "an-retry";
  retryBtn.textContent = "Try again";
  retryBtn.addEventListener("click", onRetry);
  els.analysisBody.appendChild(retryBtn);
}

function renderNoPapersState() {
  if (!els.analysisBody) return;
  els.analysisBody.innerHTML =
    '<div class="an-note">This research result has no papers to analyze yet.</div>';
}

// ==================== analysis run ====================
async function runAnalysis(question) {
  const papers = state.session.papers;

  if (!papers.length) {
    renderNoPapersState();
    return;
  }

  const eligible = papers.filter((p) => p.pdf_url || p.oa_url).slice(0, MAX_ANALYZABLE_PAPERS);
  const excluded = papers.filter((p) => !(p.pdf_url || p.oa_url));

  if (!eligible.length) {
    if (els.analysisBody) {
      els.analysisBody.innerHTML = `
        <div class="an-note">
          None of the ${papers.length} paper${papers.length === 1 ? "" : "s"} in this research
          result have a fetchable full-text link, so paper-grounded analysis isn't possible
          for ${papers.length === 1 ? "it" : "them"} yet.
        </div>`;
    }
    return;
  }

  if (state.analysisAbort) state.analysisAbort.abort();
  const controller = new AbortController();
  state.analysisAbort = controller;

  renderAnalysisPending(true, excluded);

  const paperIds = eligible.map((p) => p.openalex_id);
  const pdfUrls = {};
  eligible.forEach((p) => {
    pdfUrls[p.openalex_id] = p.pdf_url || p.oa_url;
  });

  try {
    const result = await requestPaperAnalysis({
      paperIds,
      question,
      pdfUrls,
      csrfToken: getCsrfToken(),
      signal: controller.signal,
    });
    if (controller.signal.aborted) return; // superseded by a newer question
    renderAnalysisResult(result, excluded);
  } catch (err) {
    if (err && err.name === "AbortError") return;
    renderAnalysisError(err, () => runAnalysis(question), excluded);
  }
}

// ==================== composer ====================
function handleComposerSubmit(e) {
  e.preventDefault();
  const raw = els.questionInput ? els.questionInput.value : "";
  const question = raw.trim();
  if (!question) return;

  state.session.question = question;
  state.session.createdAt = Date.now();
  saveSession(state.session);

  if (els.questionInput) els.questionInput.value = "";
  renderQuestion();
  runAnalysis(question);
}

// ==================== init ====================
function init() {
  cacheElements();

  const session = loadSession();
  if (!session) {
    showRecovery();
    return;
  }
  state.session = session;

  if (els.recover) els.recover.hidden = true;
  if (els.shell) els.shell.hidden = false;

  renderTopBar();
  renderPaperList();
  renderQuestion();

  if (session.papers.length) {
    selectPaper(0);
  } else {
    renderPaperDetail(null);
  }

  if (els.composer) {
    els.composer.addEventListener("submit", handleComposerSubmit);
  }

  runAnalysis(session.question);
}

document.addEventListener("DOMContentLoaded", init);
