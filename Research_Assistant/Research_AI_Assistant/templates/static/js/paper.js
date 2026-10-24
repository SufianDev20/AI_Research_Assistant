import { DOMManager } from './core.js';

DOMManager.prototype.markdownToHtml = function(text) {
  if (!text) return "";

  // Code blocks and images are swapped for tokens first so the line-based
  // block pass (linesToBlocks) can't split or wrap them.
  const held = [];
  const hold = (html) => `@@HOLD${held.push(html) - 1}@@`;

  let processedText = text
    .replace(/```(?:\s*\w+)?\s*\n([\s\S]*?)\n```/g, (match, p1) => {
      const code = this.escapeHtml(p1.trim());
      return "\n\n" + hold(`<pre class="code-block"><code>${code}</code></pre>`) + "\n\n";
    })
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, src) => {
      const url = src.startsWith("http") || src.startsWith("/")
        ? src
        : `/media/${src}`;
      return hold(`<img src="${url}" alt="${alt}" style="max-width:100%;border-radius:0.5rem;margin:1rem 0;">`);
    })
    .replace(/^\s*[-*+]\s+/gm, "• ")
    .replace(/^### (.+)$/gm, "<h4>$1</h4>")
    .replace(/^## (.+)$/gm, "<h3>$1</h3>")
    .replace(/^# (.+)$/gm, "<h2>$1</h2>")
    .replace(/\*\*([^\r\n*]+?)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^\r\n_]+?)__/g, "<strong>$1</strong>")
    .replace(/\*([^\r\n*]+?)\*/g, "<em>$1</em>")
    .replace(/_([^\r\n_]+?)_/g, "<em>$1</em>")
    .replace(/`([^`\r\n]+)`/g, "<code>$1</code>")
    // Inline citation markers from the summary prompt, e.g. [3] or [1, 4]
    .replace(/\[(\d+(?:\s*[,–-]\s*\d+)*)\]/g, '<span class="cite">[$1]</span>');

  processedText = this.linesToBlocks(processedText);

  held.forEach((tag, i) => {
    processedText = processedText.replace(`@@HOLD${i}@@`, tag);
  });

  return processedText;
};

// Groups the converted lines into cards, and lines into block elements.
//
// Cards: the summary prompt emits one "Paper [N]: Title" block per paper
// (followed by "Authors:", "Year:", "Source:", "DOI:" and "Summary:" lines)
// and a closing "References:" list. Each "Paper [N]" starts an <article
// class="summary-card"> -- number label, title, metadata, then the summary
// below a divider; the references list gets its own card, and any other
// text (an intro, a synthesis, a plain-text reply) goes into a note card.
// Every path that renders a summary -- the first response, Load More, its
// retry and binder restore -- goes through markdownToHtml, so all of them
// get the same cards. The card number is the N the summary itself uses
// for that paper (its own citation numbering), never a sort position.
//
// Blocks inside a card: blank lines separate paragraphs, "• " / "1. "
// lines become lists, "> " lines a blockquote. Text is only wrapped, never
// rewritten.
const PAPER_HEADING = /^(?:<h[2-4]>)?(?:<strong>)?Paper\s*<span class="cite">\[(\d+)\]<\/span>\s*[:.–-]?\s*(.*?)(?:<\/strong>)?(?:<\/h[2-4]>)?$/i;
const REFERENCES_HEADING = /^(?:<h[2-4]>)?(?:<strong>)?References:?(?:<\/strong>)?(?:<\/h[2-4]>)?$/i;
const SUMMARY_FIELD = /^(?:<strong>)?(Authors?|Year|Source|DOI|Summary)(?::<\/strong>|<\/strong>:|:)\s*(.*)$/i;
const EMPTY_FIELD_VALUE = /^(?:|n\/?a|none|unknown|not available|-)\.?$/i;
// Only values that are unambiguously a DOI become links (the character
// classes also keep quotes and angle brackets out of the href); anything
// else stays plain text.
const BARE_DOI = /^10\.\d{4,9}\/[^\s"'<>]+$/;
const DOI_URL = /^https?:\/\/(?:dx\.)?doi\.org\/10\.\d{4,9}\/[^\s"'<>]+$/i;
const BLOCK_TAGS = {
  p: ["<p>", "</p>"],
  ul: ["<ul>", "</ul>"],
  ol: ["<ol>", "</ol>"],
  quote: ["<blockquote>", "</blockquote>"],
  meta: ['<dl class="summary-card__meta">', "</dl>"],
  refs: ['<ul class="summary-references">', "</ul>"],
};

// A DOI value as a doi.org link -- never prefixing a value that is already
// a doi.org URL -- or the value unchanged when it isn't a recognisable DOI.
DOMManager.prototype.doiLinkHtml = function(value) {
  const href = DOI_URL.test(value)
    ? value
    : BARE_DOI.test(value)
      ? `https://doi.org/${value}`
      : "";
  return href
    ? `<a href="${href}" target="_blank" rel="noopener noreferrer">${value}</a>`
    : value;
};

DOMManager.prototype.linesToBlocks = function(text) {
  const out = [];
  let open = null; // block currently open inside a card (BLOCK_TAGS key)
  let card = null; // closing tag of the card currently open
  let inSummary = false;
  const close = () => {
    if (open) out.push(BLOCK_TAGS[open][1]);
    open = null;
  };
  // Opens a block of this kind unless one is already open; returns
  // whether a new block was started.
  const start = (kind) => {
    if (open === kind) return false;
    close();
    out.push(BLOCK_TAGS[kind][0]);
    open = kind;
    return true;
  };
  const closeCard = () => {
    close();
    if (inSummary) out.push("</div>");
    inSummary = false;
    if (card) out.push(card);
    card = null;
  };
  const openCard = (openTag, closeTag) => {
    closeCard();
    out.push(openTag);
    card = closeTag;
  };
  const ensureCard = () => {
    if (!card) openCard('<div class="summary-card summary-card--note">', "</div>");
  };

  text.split("\n").forEach((raw) => {
    const line = raw.trim();
    let m;
    if (!line) {
      close();
      return;
    }
    if ((m = line.match(PAPER_HEADING))) {
      const n = m[1];
      openCard(`<article class="summary-card" data-paper-number="${n}">`, "</article>");
      out.push(`<p class="summary-card__number">Paper ${n.padStart(2, "0")}</p>`);
      out.push(`<h3 class="summary-card__title">${m[2] || "Paper " + n}</h3>`);
      return;
    }
    if (REFERENCES_HEADING.test(line)) {
      openCard('<section class="summary-card summary-card--references">', "</section>");
      out.push('<h3 class="summary-card__title">References</h3>');
      return;
    }
    if (/^<h[2-4]>/.test(line)) {
      // Any other heading starts its own note card instead of joining a paper.
      openCard('<div class="summary-card summary-card--note">', "</div>");
      out.push(line);
      return;
    }
    ensureCard();
    if (/^@@HOLD\d+@@$/.test(line)) {
      close();
      out.push(line);
    } else if ((m = line.match(SUMMARY_FIELD))) {
      const field = m[1].toLowerCase();
      const value = m[2].trim();
      if (field === "summary") {
        close();
        if (!inSummary) {
          out.push('<div class="summary-card__summary"><p class="summary-card__label">Summary</p>');
          inSummary = true;
        }
        if (value) {
          start("p");
          out.push(value);
        }
      } else if (!EMPTY_FIELD_VALUE.test(value)) {
        start("meta");
        const label = field === "doi" ? "DOI" : m[1].charAt(0).toUpperCase() + field.slice(1);
        const shown = field === "doi" ? this.doiLinkHtml(value) : value;
        out.push(`<div><dt>${label}</dt><dd>${shown}</dd></div>`);
      }
    } else if (/^<span class="cite">\[\d+\]<\/span>\s/.test(line)) {
      start("refs");
      out.push(`<li>${line}</li>`);
    } else if ((m = line.match(/^•\s+(.*)$/))) {
      start("ul");
      out.push(`<li>${m[1]}</li>`);
    } else if ((m = line.match(/^\d+[.)]\s+(.*)$/))) {
      start("ol");
      out.push(`<li>${m[1]}</li>`);
    } else if ((m = line.match(/^>\s?(.*)$/))) {
      if (!start("quote")) out.push("<br>");
      out.push(m[1]);
    } else {
      if (!start("p")) out.push("<br>");
      out.push(line);
    }
  });
  closeCard();

  return out.join("");
};

DOMManager.prototype.escapeHtml = function(unsafe) {
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
};

DOMManager.prototype.renderPaperCards = function(papers, container) {
  if (!papers?.length || !container) return;

  const papersContainer = document.createElement("div");
  papersContainer.className = "papers-grid mt-4 mb-4";

  // Create sort bar
  const sortBar = document.createElement("div");
  sortBar.className = "paper-sort-bar";
  sortBar.innerHTML = `
    <span class="sort-label">Sort by:</span>
    <button class="sort-btn active" data-sort="default">Relevance</button>
    <button class="sort-btn" data-sort="citations">Most Cited</button>
    <button class="sort-btn" data-sort="recency">Most Recent</button>
  `;

  // Sort functionality using closure over papers
  sortBar.addEventListener("click", (e) => {
    const btn = e.target.closest(".sort-btn");
    if (!btn) return;

    sortBar
      .querySelectorAll(".sort-btn")
      .forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");

    const mode = btn.dataset.sort;
    let sorted = [...papers];

    if (mode === "citations") {
      sorted.sort(
        (a, b) => (b.cited_by_count || 0) - (a.cited_by_count || 0),
      );
    } else if (mode === "recency") {
      sorted.sort(
        (a, b) => (b.publication_year || 0) - (a.publication_year || 0),
      );
    }
    // else default keeps original order

    // Remove existing cards
    const existingCards = papersContainer.querySelectorAll(".paper-card");
    existingCards.forEach((c) => c.remove());

    // Re-add title and render sorted cards
    sorted.forEach((paper, i) => {
      const paperCard = this.createPaperCard(paper, i);
      papersContainer.appendChild(paperCard);
    });
  });

  papersContainer.appendChild(sortBar);

  // Add paper cards
  papers.forEach((paper, i) => {
    const paperCard = this.createPaperCard(paper, i);
    papersContainer.appendChild(paperCard);
  });

  container.appendChild(papersContainer);
};

DOMManager.prototype.createPaperCard = function(paper, index) {
  const authors = paper.authors
    ? paper.authors
        .slice(0, 2)
        .map((a) => a.name)
        .join(", ")
    : "Unknown authors";
  const abstract = paper.abstract
    ? paper.abstract.substring(0, 150) +
      (paper.abstract.length > 150 ? "..." : "")
    : "No abstract available";

  const card = document.createElement("div");
  card.className =
    "paper-card hover:bg-zinc-800/70 transition-colors cursor-pointer";
  card.innerHTML = `
        <div class="paper-card-content">
            <div class="paper-number">${index + 1}.</div>
            <div class="paper-details">
                <div class="paper-title">
                    ${paper.doi ? `<a href="https://doi.org/${paper.doi}" target="_blank" class="paper-link">${paper.title}</a>` : paper.title}
                </div>
                <div class="paper-meta">${authors} • ${paper.publication_year || "N/A"}</div>
                <div class="paper-abstract">${abstract}</div>
            </div>
        </div>
    `;

  card.onclick = (e) => {
    if (!e.target.closest("a") && paper.doi) {
      window.open(`https://doi.org/${paper.doi}`, "_blank");
    }
  };

  return card;
};

DOMManager.prototype.saveToBinder = function() {
  if (!window.appState.currentResearchBinder) return;

  // Migrate additionalPapers to main papers array for compatibility
  if (
    window.appState.currentResearchBinder.additionalPapers &&
    window.appState.currentResearchBinder.additionalPapers.length > 0
  ) {
    window.appState.currentResearchBinder.papers.push(
      ...window.appState.currentResearchBinder.additionalPapers,
    );
    delete window.appState.currentResearchBinder.additionalPapers; // Remove old array
  }

  window.appState.binders.push({ ...window.appState.currentResearchBinder });
  this.renderBinders();
  this.generateTitle(window.appState.currentResearchBinder);
  this.hideResearchView();
};

DOMManager.prototype.generateTitle = async function(binder) {
  if (!binder) return;

  try {
    const response = await fetch("/api/generate_title/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": window.csrfToken,
      },
      body: JSON.stringify({
        messages: binder.messages,
      }),
    });

    if (!response.ok) {
      throw new Error(`Title API error: ${response.status}`);
    }

    const data = await response.json();
    const suggestedTitle = data.title || "Research Conversation";

    if (suggestedTitle.length > 5 && suggestedTitle.length < 60) {
      binder.name = suggestedTitle;
      this.renderBinders();
      console.log(`Auto-titled: ${suggestedTitle}`);
    }
  } catch (err) {
    console.warn("Auto-title failed:", err);
    if (binder.messages[0] && binder.messages[0].role === "user") {
      let fallback = binder.messages[0].content.substring(0, 38);
      if (binder.messages[0].content.length > 38) fallback += "...";
      binder.name = fallback;
      this.renderBinders();
    }
  }
};