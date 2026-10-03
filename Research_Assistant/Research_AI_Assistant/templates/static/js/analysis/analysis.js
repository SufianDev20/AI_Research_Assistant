// Paper analysis page controller. Reads session state written by research.js
// under sessionStorage key "scholara:analysisSession" — keep both files in sync
// if that shape changes: { researchId, sourceQuery, question, papers, createdAt }.
//
// The Q&A panel is a transcript: every question becomes a "turn" appended to
// state.session.turns and rendered in its own node. Turns are never replaced
// wholesale, so a slow answer cannot overwrite a newer one.

import { fetchResearchPapers, requestPaperAnalysis, isPublisherBlock } from "./analysis_api.js";

const SESSION_KEY = "scholara:analysisSession";
const MAX_ANALYZABLE_PAPERS = 10; // matches QARequestSerializer cap
const MAX_TURNS = 20; // sessionStorage is ~5MB and a transcript grows without bound

function getCsrfToken() {
  const input = document.querySelector('[name=csrfmiddlewaretoken]');
  if (input?.value) return input.value;
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function escapeHtml(str) {
  if (str == null) return "";
  return String(str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function formatAuthors(paper, limit = 3) {
  const names = (paper?.authors ?? []).map((a) => a?.name).filter(Boolean);
  if (!names.length) return "";
  return names.length <= limit ? names.join(", ") : `${names.slice(0, limit).join(", ")}, et al.`;
}

// Derived only from fields already on the paper object; never fabricated.
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
  if (paper.is_open_access && paper.has_pdf_link) return '<span class="an-badge">Open access · PDF</span>';
  if (paper.is_open_access) return '<span class="an-badge">Open access</span>';
  return '<span class="an-badge an-badge--muted">No full text</span>';
}

const state = {
  session: null,
  selectedIds: new Set(),
  analysisAbort: null,
  busy: false, // a turn is in flight; the composer stays locked until it resolves
};

const isSelected = (paper) => !!paper && state.selectedIds.has(paper.openalex_id);
const selectedPapers = () => state.session.papers.filter(isSelected);

const els = {};
function cacheElements() {
  els.recover = document.getElementById("anRecover");
  els.recoverMessage = document.getElementById("anRecoverMessage");
  els.shell = document.getElementById("anShell");
  els.sourceQuery = document.getElementById("anSourceQuery");
  els.paperCount = document.getElementById("anPaperCount");
  els.paperList = document.getElementById("anPaperList");
  els.paperDetail = document.getElementById("anPaperDetail");
  els.transcript = document.getElementById("anTranscript");
  els.composer = document.getElementById("anComposer");
  els.questionInput = document.getElementById("anQuestionInput");
  els.questionSend = document.getElementById("anQuestionSend");
}

// ---------------------------------------------------------------------------
// Session
// ---------------------------------------------------------------------------

function loadSession() {
  let raw;
  try {
    raw = sessionStorage.getItem(SESSION_KEY);
  } catch {
    return null; // storage unavailable (private mode etc.)
  }
  if (!raw) return null;

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!parsed || typeof parsed !== "object" || !Array.isArray(parsed.papers)) return null;

  parsed.question = typeof parsed.question === "string" ? parsed.question : "";
  if (!Array.isArray(parsed.selectedIds)) parsed.selectedIds = [];
  // Records written before the transcript existed carry no turns; research.js
  // still writes none, and init() seeds the first one from `question`.
  parsed.turns = Array.isArray(parsed.turns) ? parsed.turns.filter((t) => t && t.id && t.question) : [];
  return parsed;
}

function saveSession(session) {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch (err) {
    console.warn("Could not persist analysis session:", err); // non-fatal, page keeps working in-memory
  }
}

function showRecovery(message) {
  if (message && els.recoverMessage) els.recoverMessage.textContent = message;
  if (els.recover) els.recover.hidden = false;
  if (els.shell) els.shell.hidden = true;
}

function renderTopBar() {
  if (els.sourceQuery) els.sourceQuery.textContent = state.session.sourceQuery || state.session.question;
}

// ---------------------------------------------------------------------------
// Paper list and selection
// ---------------------------------------------------------------------------

function renderPaperListMessage(html) {
  if (els.paperCount) els.paperCount.textContent = "";
  if (els.paperList) els.paperList.innerHTML = html;
}

function renderPaperList() {
  const papers = state.session.papers;
  if (els.paperCount) {
    els.paperCount.textContent = papers.length ? `${state.selectedIds.size} of ${papers.length} selected` : "";
  }
  if (!els.paperList) return;

  if (!papers.length) {
    els.paperList.innerHTML = '<div class="an-paper-list__empty">No papers were retrieved for this research result.</div>';
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
    card.setAttribute("aria-pressed", String(selected));

    if (!selected && atCap) {
      card.disabled = true;
      card.title = `You can analyse up to ${MAX_ANALYZABLE_PAPERS} papers at once. Remove one to add another.`;
    }

    const metaParts = [paper.publication_year, formatAuthors(paper, 2), paper.source].filter(Boolean);
    const cited = paper.cited_by_count ? `<span class="an-paper-card__cited">${paper.cited_by_count.toLocaleString()} citations</span>` : "";

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

function togglePaper(paper) {
  if (!paper?.openalex_id) return;
  if (state.selectedIds.has(paper.openalex_id)) {
    state.selectedIds.delete(paper.openalex_id);
  } else {
    if (state.selectedIds.size >= MAX_ANALYZABLE_PAPERS) return;
    state.selectedIds.add(paper.openalex_id);
  }
  persistSelection();
  renderPaperList();
  renderSelectedPapers();
  if (!state.session.turns.length) renderIdleNote();
}

function persistSelection() {
  state.session.selectedIds = [...state.selectedIds];
  saveSession(state.session);
}

function renderSelectedPapers() {
  if (!els.paperDetail) return;
  const chosen = selectedPapers();

  if (!chosen.length) {
    els.paperDetail.innerHTML = `<div class="an-detail__idle"><p>Select papers from the list to analyse them together.</p></div>`;
    return;
  }

  els.paperDetail.innerHTML = "";
  chosen.forEach((paper) => {
    const card = document.createElement("article");
    card.className = "an-detail__card";
    card.innerHTML = renderSelectedCard(paper);
    card.querySelector(".an-detail__remove")?.addEventListener("click", () => togglePaper(paper));
    els.paperDetail.appendChild(card);
  });
}

// Coverage reflects the most recent answered turn, so the bars keep meaning
// something once the panel holds several answers.
function latestCoverage() {
  const turns = state.session?.turns ?? [];
  for (let i = turns.length - 1; i >= 0; i -= 1) {
    if (turns[i].status === "done" && turns[i].coverage) return turns[i].coverage;
  }
  return null;
}

function coverageHtml(paper) {
  const c = latestCoverage()?.[paper.openalex_id];
  if (!c) return "";
  const pct = Math.round((c.used / c.total) * 100);
  return `<div class="an-detail__coverage" title="Excerpts of this paper sent to the model for the most recent answer">
    Used ${c.used} of ${c.total} excerpts in the latest answer
    <span class="an-detail__bar"><i style="width:${pct}%"></i></span>
  </div>`;
}

function renderSelectedCard(paper) {
  const authors = formatAuthors(paper, 8);
  const metaParts = [paper.publication_year, paper.source].filter(Boolean);
  if (typeof paper.cited_by_count === "number") metaParts.push(`${paper.cited_by_count.toLocaleString()} citations`);

  const linkUrl = paper.pdf_url || paper.oa_url || (paper.doi ? `https://doi.org/${paper.doi}` : null);
  const linkHtml = linkUrl ? `<a class="an-detail__link" href="${escapeHtml(linkUrl)}" target="_blank" rel="noopener noreferrer">View source ↗</a>` : "";

  // Only rendered if the backend attaches these fields later; never fabricated here.
  const optionalSections = ["summary", "methodology", "findings"]
    .filter((key) => paper[key]?.trim?.())
    .map((key) => `<div class="an-detail__section"><h4>${key}</h4><p>${escapeHtml(paper[key])}</p></div>`)
    .join("");

  return `
    <button type="button" class="an-detail__remove" aria-label="Remove ${escapeHtml(paper.title || "this paper")} from the selection">&times;</button>
    <h3 class="an-detail__title">${escapeHtml(paper.title || "Untitled")}</h3>
    ${authors ? `<p class="an-detail__authors">${escapeHtml(authors)}</p>` : ""}
    <div class="an-detail__meta">${metaParts.map((p) => `<span>${escapeHtml(p)}</span>`).join("")}${paperBadgeHtml(paper)}</div>
    <div class="an-detail__section"><h4>Abstract</h4><p>${paper.abstract ? escapeHtml(paper.abstract) : "No abstract available for this paper."}</p></div>
    ${optionalSections}
    ${coverageHtml(paper)}
    <div class="an-detail__section">
      <h4>Citation</h4>
      <p class="an-detail__citation">${escapeHtml(buildCitationLine(paper))}</p>
      ${linkHtml}
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Transcript
// ---------------------------------------------------------------------------

let turnCounter = 0;
function makeTurn(question, selectedIds) {
  turnCounter += 1;
  return {
    id: `t${Date.now()}-${turnCounter}`,
    question,
    askedAt: Date.now(),
    status: "pending",
    selectedIds: [...selectedIds],
    answer: "",
    citations: [],
    papers: {},
    paperErrors: {},
    contextTrimmed: false,
    coverage: null,
    excludedTitles: [],
    error: "",
    errorStatus: null,
    retryable: true,
  };
}

const turnNode = (id) => els.transcript?.querySelector(`[data-turn-id="${id}"]`);

// Never falls back to the raw id: an OpenAlex URL means nothing to the reader.
function findPaperTitle(paperId, turnPapers) {
  return (
    state.session.papers.find((p) => p.openalex_id === paperId)?.title ||
    turnPapers?.[paperId]?.title ||
    "Unknown paper"
  );
}

function excludedPapersNote(titles) {
  if (!titles?.length) return "";
  const list = titles.map((t) => escapeHtml(t || "Untitled")).join("; ");
  return `<div class="an-note">
    <strong>${titles.length} paper${titles.length === 1 ? "" : "s"} not analyzed</strong> —
    no fetchable full text was found, so ${titles.length === 1 ? "it was" : "they were"} skipped: ${list}
  </div>`;
}

// A publisher-blocked paper (403/405) will fail the same way for every user;
// flag it distinctly from a transient error so the note reads as "pick another
// paper", not "retry".
function paperErrorNote(reason, title) {
  const label = isPublisherBlock(reason) ? "Blocked by publisher" : "Failed";
  return `<div class="an-note an-note--error"><strong>${escapeHtml(title)}: ${label}.</strong> ${escapeHtml(reason)}</div>`;
}

function evidenceHtml(citations, turnPapers) {
  const byPaper = new Map();
  (citations ?? []).forEach((c) => {
    const key = c.paper_id || "unknown";
    if (!byPaper.has(key)) byPaper.set(key, []);
    byPaper.get(key).push(c);
  });
  if (!byPaper.size) return "";

  let html = '<div class="an-evidence__head">Evidence by paper</div>';
  byPaper.forEach((cites, paperId) => {
    const rows = cites
      .map((c) => {
        const page = c.page_exists && c.page ? `p.${c.page}` : "page unverified";
        const verified = c.text_verified ? '<span class="an-citation__verified">verified</span>' : "";
        return `<div class="an-citation">
          <span class="an-citation__page">${escapeHtml(page)}</span>
          <span class="an-citation__snippet">"${escapeHtml(c.quoted_snippet || "")}"${verified}</span>
        </div>`;
      })
      .join("");
    html += `<div class="an-evidence-group">
      <div class="an-evidence-group__paper">${escapeHtml(findPaperTitle(paperId, turnPapers))}</div>
      ${rows}
    </div>`;
  });
  return html;
}

function turnBodyHtml(turn) {
  if (turn.status === "pending") {
    return `
      ${excludedPapersNote(turn.excludedTitles)}
      <div class="an-pending an-pending--active">
        <svg class="an-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><use href="#i-eye"></use></svg>
        <p>Analyzing across your papers…</p>
      </div>
    `;
  }

  if (turn.status === "error") {
    // The backend already trims to relevant excerpts, so a 413 means deselect
    // papers, not retry.
    const isTooLarge = turn.errorStatus === 413;
    const isLLMFailure = turn.errorStatus === 502;
    const message = isTooLarge
      ? "<strong>These papers are too large to analyze together.</strong> Deselect one or more papers in the list, then ask again."
      : isLLMFailure
        ? "<strong>We couldn&#39;t get a reliable answer right now.</strong> The AI service is temporarily having trouble — try again in a moment."
        : `<strong>Analysis failed.</strong> ${escapeHtml(turn.error || "Unknown error.")}`;

    return `
      ${excludedPapersNote(turn.excludedTitles)}
      <div class="an-note an-note--error">${message}</div>
      ${turn.retryable && !isTooLarge ? '<button type="button" class="an-retry" data-retry>Try again</button>' : ""}
    `;
  }

  const answerHtml = turn.answer
    ? turn.answer.split(/\n{2,}/).map((p) => `<p>${escapeHtml(p.trim())}</p>`).join("")
    : "";
  const evidence = evidenceHtml(turn.citations, turn.papers);
  const errorEntries = Object.entries(turn.paperErrors ?? {});
  const errorsHtml = errorEntries.map(([paperId, reason]) => paperErrorNote(reason, findPaperTitle(paperId, turn.papers))).join("");
  const nothingReturned = !turn.answer && !evidence && !errorEntries.length;

  return `
    ${answerHtml ? `<div class="an-answer">${answerHtml}</div>` : ""}
    ${nothingReturned ? '<div class="an-note">No grounded evidence was returned for this question.</div>' : ""}
    ${evidence}
    ${errorsHtml}
    ${turn.contextTrimmed ? '<div class="an-note"><strong>Long papers were trimmed</strong> — this answer uses only the excerpts most relevant to your question. Select fewer papers or ask something more specific for fuller coverage.</div>' : ""}
    ${excludedPapersNote(turn.excludedTitles)}
  `;
}

function turnHtml(turn) {
  return `
    <div class="an-turn__question">
      <p class="an-turn__question-label">Your question</p>
      <p class="an-turn__question-text">${escapeHtml(turn.question)}</p>
    </div>
    <div class="an-turn__body">${turnBodyHtml(turn)}</div>
  `;
}

function paintTurn(node, turn) {
  node.className = `an-turn an-turn--${turn.status}`;
  node.innerHTML = turnHtml(turn);
  node.querySelector("[data-retry]")?.addEventListener("click", () => {
    if (state.busy) return;
    turn.status = "pending";
    turn.error = "";
    turn.errorStatus = null;
    updateTurn(turn);
    runAnalysis(turn);
  });
}

// Only the changed turn's node is repainted — never the whole panel — so a
// resolving turn cannot clobber a newer one.
function updateTurn(turn) {
  const node = turnNode(turn.id);
  if (node) paintTurn(node, turn);
  saveSession(state.session);
}

function buildTurnNode(turn) {
  const node = document.createElement("article");
  node.dataset.turnId = turn.id;
  paintTurn(node, turn);
  return node;
}

function appendTurn(turn) {
  const turns = state.session.turns;
  turns.push(turn);
  while (turns.length > MAX_TURNS) {
    const dropped = turns.shift();
    turnNode(dropped.id)?.remove();
  }
  els.transcript?.querySelector(".an-transcript__idle")?.remove();
  els.transcript?.appendChild(buildTurnNode(turn));
  saveSession(state.session);
  scrollTranscriptToEnd();
}

function scrollTranscriptToEnd() {
  if (els.transcript) els.transcript.scrollTop = els.transcript.scrollHeight;
}

function renderIdleNote() {
  if (!els.transcript || state.session.turns.length) return;
  const count = state.selectedIds.size;
  const message = !state.session.papers.length
    ? "This research result has no papers to analyze yet."
    : count
      ? `Ask a question below to analyse the ${count} selected paper${count === 1 ? "" : "s"} together.`
      : "Select one or more papers, then ask a question about them.";
  els.transcript.innerHTML = `<div class="an-note an-transcript__idle">${message}</div>`;
}

function renderTranscript() {
  if (!els.transcript) return;
  els.transcript.innerHTML = "";
  if (!state.session.turns.length) return renderIdleNote();

  state.session.turns.forEach((turn) => {
    // A turn left pending by a reload can never resolve; show it as failed
    // rather than spinning forever.
    if (turn.status === "pending") {
      turn.status = "error";
      turn.error = "This question was interrupted before an answer came back.";
      turn.retryable = true;
    }
    els.transcript.appendChild(buildTurnNode(turn));
  });
  scrollTranscriptToEnd();
}

// ---------------------------------------------------------------------------
// Asking
// ---------------------------------------------------------------------------

function setBusy(busy) {
  state.busy = busy;
  if (els.questionInput) els.questionInput.disabled = busy;
  if (els.questionSend) els.questionSend.disabled = busy;
  els.composer?.classList.toggle("an-qa__composer--busy", busy);
}

function failTurn(turn, message, { retryable = false, status = null } = {}) {
  turn.status = "error";
  turn.error = message;
  turn.errorStatus = status;
  turn.retryable = retryable;
  updateTurn(turn);
}

async function runAnalysis(turn) {
  if (!state.session.papers.length) {
    return failTurn(turn, "This research result has no papers to analyze yet.");
  }

  // Scoped to the selection this turn was asked with, so a retry reproduces
  // the original request even if the selection has changed since.
  const ids = new Set(turn.selectedIds);
  const chosen = state.session.papers.filter((p) => ids.has(p.openalex_id));
  if (!chosen.length) {
    return failTurn(turn, "Select at least one paper from the list before asking a question.");
  }

  const eligible = chosen.filter((p) => p.pdf_url || p.oa_url);
  const excluded = chosen.filter((p) => !(p.pdf_url || p.oa_url));
  turn.excludedTitles = excluded.map((p) => p.title || "Untitled");

  if (!eligible.length) {
    return failTurn(
      turn,
      `None of the ${chosen.length} selected paper${chosen.length === 1 ? "" : "s"} have a fetchable full-text link, ` +
        `so paper-grounded analysis isn't possible for ${chosen.length === 1 ? "it" : "them"}. ` +
        "Select a paper marked Open access · PDF and try again.",
    );
  }

  const controller = new AbortController();
  state.analysisAbort = controller; // aborted on page unload only
  turn.status = "pending";
  updateTurn(turn);
  setBusy(true);

  const paperIds = eligible.map((p) => p.openalex_id);
  // pdf_candidates is absent on papers saved before it existed; fall back to the single URL.
  const pdfUrls = Object.fromEntries(
    eligible.map((p) => [p.openalex_id, p.pdf_candidates?.length ? p.pdf_candidates : p.pdf_url || p.oa_url]),
  );

  const paperMeta = Object.fromEntries(
    eligible.map((p) => [
      p.openalex_id,
      {
        title: p.title || "",
        authors: (p.authors ?? []).map((a) => a?.name).filter(Boolean).slice(0, 10),
        year: Number.isInteger(p.publication_year) ? p.publication_year : null,
      },
    ]),
  );

  try {
    const result = await requestPaperAnalysis({
      paperIds,
      question: turn.question,
      pdfUrls,
      paperMeta,
      csrfToken: getCsrfToken(),
      signal: controller.signal,
    });
    turn.status = "done";
    turn.answer = result.answer;
    turn.citations = result.citations;
    turn.papers = result.papers;
    turn.paperErrors = result.paper_errors;
    turn.contextTrimmed = result.context_trimmed;
    turn.coverage = result.context_papers;
    updateTurn(turn);
    renderSelectedPapers(); // coverage bars follow the newest answer
  } catch (err) {
    if (err?.name === "AbortError") return; // page is going away
    failTurn(turn, err?.message || "Unknown error.", { retryable: true, status: err?.status ?? null });
  } finally {
    setBusy(false);
    scrollTranscriptToEnd();
  }
}

function handleComposerSubmit(e) {
  e.preventDefault();
  if (state.busy) return; // one turn at a time; free models rate-limit each other
  const question = (els.questionInput?.value ?? "").trim();
  if (!question) return;

  state.session.question = question; // "last asked", kept for older readers
  state.session.createdAt = Date.now();
  if (els.questionInput) els.questionInput.value = "";

  const turn = makeTurn(question, state.selectedIds);
  appendTurn(turn);
  runAnalysis(turn);
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

function seedSelection() {
  const available = new Set(state.session.papers.map((p) => p.openalex_id));
  state.selectedIds = new Set((state.session.selectedIds ?? []).filter((id) => available.has(id)).slice(0, MAX_ANALYZABLE_PAPERS));
}

async function ensurePapers() {
  if (state.session.papers.length) return;

  const params = state.session.searchParams || (state.session.sourceQuery ? { query: state.session.sourceQuery } : null);
  if (!params?.query) return;

  renderPaperListMessage('<div class="an-paper-list__empty">Loading the papers for this research result…</div>');

  try {
    const papers = await fetchResearchPapers(params);
    state.session.papers = Array.isArray(papers) ? papers : [];
    saveSession(state.session);
  } catch (err) {
    console.error("Could not reload papers for the analysis page:", err);
  }
}

async function init() {
  cacheElements();

  const session = loadSession();
  if (!session) return showRecovery();
  state.session = session;

  if (els.recover) els.recover.hidden = true;
  if (els.shell) els.shell.hidden = false;

  renderTopBar();
  els.composer?.addEventListener("submit", handleComposerSubmit);
  window.addEventListener("pagehide", () => state.analysisAbort?.abort());

  await ensurePapers();
  seedSelection();
  renderPaperList();
  renderSelectedPapers();
  renderTranscript();

  // A question arriving from the workspace has no turn yet; a reload already
  // has one and must not re-ask it.
  if (session.question && !session.turns.length) {
    const turn = makeTurn(session.question, state.selectedIds);
    appendTurn(turn);
    runAnalysis(turn);
  }
}

document.addEventListener("DOMContentLoaded", init);
