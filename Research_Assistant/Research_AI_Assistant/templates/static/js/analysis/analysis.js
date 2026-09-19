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

import { fetchResearchPapers, requestPaperAnalysis } from "./analysis_api.js";

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
  selectedIds: new Set(),
  analysisAbort: null,
};

function isSelected(paper) {
  return !!paper && state.selectedIds.has(paper.openalex_id);
}

function selectedPapers() {
  return state.session.papers.filter(isSelected);
}

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
  parsed.question = typeof parsed.question === "string" ? parsed.question : "";
  if (!Array.isArray(parsed.selectedIds)) parsed.selectedIds = [];
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
function renderPaperListMessage(html) {
  if (els.paperCount) els.paperCount.textContent = "";
  if (els.paperList) els.paperList.innerHTML = html;
}

function renderPaperList() {
  const papers = state.session.papers;
  if (els.paperCount) {
    els.paperCount.textContent = papers.length
      ? `${state.selectedIds.size} of ${papers.length} selected`
      : "";
  }
  if (!els.paperList) return;

  if (!papers.length) {
    els.paperList.innerHTML =
      '<div class="an-paper-list__empty">No papers were retrieved for this research result.</div>';
    return;
  }

  const atCap = state.selectedIds.size >= MAX_ANALYZABLE_PAPERS;

  els.paperList.innerHTML = "";
  papers.forEach((paper) => {
    const selected = isSelected(paper);
    const card = document.createElement("button");
    card.type = "button";
    card.className = `an-paper-card${selected ? " an-paper-card--selected" : ""}`;
    card.setAttribute("role", "listitem");
    card.setAttribute("aria-pressed", selected ? "true" : "false");

    if (!selected && atCap) {
      card.disabled = true;
      card.title = `You can analyse up to ${MAX_ANALYZABLE_PAPERS} papers at once. Remove one to add another.`;
    }

    const metaParts = [];
    if (paper.publication_year) metaParts.push(paper.publication_year);
    const authors = formatAuthors(paper, 2);
    if (authors) metaParts.push(authors);
    if (paper.source) metaParts.push(paper.source);

    const cited = paper.cited_by_count
      ? `<span class="an-paper-card__cited">${paper.cited_by_count.toLocaleString()} citations</span>`
      : "";

    card.innerHTML = `
      <span class="an-paper-card__check" aria-hidden="true">${selected ? "✓" : ""}</span>
      <div class="an-paper-card__title">${escapeHtml(paper.title || "Untitled")}</div>
      <div class="an-paper-card__meta">${escapeHtml(metaParts.join(" · "))}</div>
      <div class="an-paper-card__foot">${paperBadgeHtml(paper)}${cited}</div>
    `;
    card.addEventListener("click", () => togglePaper(paper));
    els.paperList.appendChild(card);
  });
}

// ==================== selection ====================
function togglePaper(paper) {
  if (!paper || !paper.openalex_id) return;
  if (state.selectedIds.has(paper.openalex_id)) {
    state.selectedIds.delete(paper.openalex_id);
  } else {
    if (state.selectedIds.size >= MAX_ANALYZABLE_PAPERS) return;
    state.selectedIds.add(paper.openalex_id);
  }
  persistSelection();
  renderPaperList();
  renderSelectedPapers();
  if (!state.session.question) renderIdleAnalysis();
}

function persistSelection() {
  state.session.selectedIds = Array.from(state.selectedIds);
  saveSession(state.session);
}

// ==================== rendering: left (selected papers) ====================
function renderSelectedPapers() {
  if (!els.paperDetail) return;
  const chosen = selectedPapers();

  if (!chosen.length) {
    els.paperDetail.innerHTML = `
      <div class="an-detail__idle">
        <p>Select papers from the list to analyse them together.</p>
      </div>`;
    return;
  }

  els.paperDetail.innerHTML = "";
  chosen.forEach((paper) => {
    const card = document.createElement("article");
    card.className = "an-detail__card";
    card.innerHTML = renderSelectedCard(paper);

    const remove = card.querySelector(".an-detail__remove");
    if (remove) remove.addEventListener("click", () => togglePaper(paper));

    els.paperDetail.appendChild(card);
  });
}

function renderSelectedCard(paper) {
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

  return `
    <button type="button" class="an-detail__remove" aria-label="Remove ${escapeHtml(
      paper.title || "this paper"
    )} from the selection">&times;</button>
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
  const question = state.session.question || "";
  const wrap = document.querySelector(".an-qa__question");
  if (wrap) wrap.hidden = !question;
  if (els.questionText) els.questionText.textContent = question;
}

function renderIdleAnalysis() {
  if (!els.analysisBody) return;
  const count = state.selectedIds.size;
  els.analysisBody.innerHTML = count
    ? `<div class="an-note">Ask a question below to analyse the ${count} selected paper${
        count === 1 ? "" : "s"
      } together.</div>`
    : '<div class="an-note">Select one or more papers, then ask a question about them.</div>';
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

  const chosen = selectedPapers();

  if (!chosen.length) {
    if (els.analysisBody) {
      els.analysisBody.innerHTML =
        '<div class="an-note">Select at least one paper from the list before asking a question.</div>';
    }
    return;
  }

  const eligible = chosen.filter((p) => p.pdf_url || p.oa_url);
  const excluded = chosen.filter((p) => !(p.pdf_url || p.oa_url));

  if (!eligible.length) {
    if (els.analysisBody) {
      els.analysisBody.innerHTML = `
        <div class="an-note">
          None of the ${chosen.length} selected paper${chosen.length === 1 ? "" : "s"} have a
          fetchable full-text link, so paper-grounded analysis isn't possible
          for ${chosen.length === 1 ? "it" : "them"}. Select a paper marked
          <strong>Open access · PDF</strong> and try again.
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

function seedSelection() {
  const available = new Set(state.session.papers.map((p) => p.openalex_id));
  state.selectedIds = new Set(
    (state.session.selectedIds || [])
      .filter((id) => available.has(id))
      .slice(0, MAX_ANALYZABLE_PAPERS)
  );
}

async function ensurePapers() {
  if (state.session.papers.length) return;

  const params = state.session.searchParams ||
    (state.session.sourceQuery ? { query: state.session.sourceQuery } : null);
  if (!params || !params.query) return;

  renderPaperListMessage(
    '<div class="an-paper-list__empty">Loading the papers for this research result…</div>'
  );

  try {
    const papers = await fetchResearchPapers(params);
    state.session.papers = Array.isArray(papers) ? papers : [];
    saveSession(state.session);
  } catch (err) {
    console.error("Could not reload papers for the analysis page:", err);
  }
}

// ==================== init ====================
async function init() {
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
  renderQuestion();

  if (els.composer) {
    els.composer.addEventListener("submit", handleComposerSubmit);
  }

  await ensurePapers();
  seedSelection();
  renderPaperList();
  renderSelectedPapers();

  if (session.question) {
    runAnalysis(session.question);
  } else {
    renderIdleAnalysis();
  }
}

document.addEventListener("DOMContentLoaded", init);
