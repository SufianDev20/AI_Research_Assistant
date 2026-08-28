import { DOMManager } from './core.js';

// Extend DOMManager prototype with paper view-related methods
DOMManager.prototype.showPaperView = function(papers, selectedIndex = 0) {
  window.appState.currentPaperViewPapers = papers;

  if (this.elements.paperView) {
    this.elements.paperView.classList.add("show");
  }

  this._renderPaperSidebar(papers, "relevance");
  this._setupPaperSidebarFilters();

  if (papers.length > 0) {
    this._selectPaper(papers[selectedIndex], selectedIndex);
  }
};

DOMManager.prototype.hidePaperView = function() {
  if (this.elements.paperView) {
    this.elements.paperView.classList.remove("show");
  }
  window.appState.currentPaperViewSelected = null;
  if (this.elements.paperQAChat) {
    this.elements.paperQAChat.innerHTML = "";
  }
};

// Returns a badge for the sidebar list item based on OA / PDF-link state.
// This is the pre-fetch, best-guess state from OpenAlex metadata only.
// It never claims extraction succeeded, only that the paper is marked OA
// by OpenAlex and/or a PDF URL was found in its metadata.
DOMManager.prototype._getSidebarBadgeHtml = function(paper) {
  if (paper.is_open_access && paper.has_pdf_link) {
    return `<span class="paper-sidebar-oa" title="Open access, PDF link found">OA · PDF</span>`;
  }
  if (paper.is_open_access) {
    return `<span class="paper-sidebar-oa" title="Open access, no direct PDF link">OA</span>`;
  }
  return "";
};

DOMManager.prototype._renderPaperSidebar = function(papers, sortMode) {
  if (!this.elements.paperSidebarList) return;

  const sorted = [...papers];
  if (sortMode === "cited_by_count") {
    sorted.sort((a, b) => (b.cited_by_count || 0) - (a.cited_by_count || 0));
  }
  // relevance keeps original order

  this.elements.paperSidebarList.innerHTML = "";

  sorted.forEach((paper, i) => {
    const item = document.createElement("div");
    item.className = "paper-sidebar-item";
    item.dataset.index = i;

    const oaBadge = this._getSidebarBadgeHtml(paper);
    const citations = paper.cited_by_count
      ? `<span class="paper-sidebar-citations">${paper.cited_by_count.toLocaleString()} cit.</span>`
      : "";

    item.innerHTML = `
      <div class="paper-sidebar-item-title">${paper.title || "Untitled"}</div>
      <div class="paper-sidebar-item-meta">
        ${paper.publication_year || ""} ${paper.publication_year && paper.authors?.length ? "·" : ""} ${paper.authors?.slice(0, 2).map(a => a.name).join(", ") || ""}
      </div>
      <div class="paper-sidebar-item-badges">${oaBadge}${citations}</div>
    `;

    item.addEventListener("click", () => {
      // update active state
      this.elements.paperSidebarList.querySelectorAll(".paper-sidebar-item")
        .forEach(el => el.classList.remove("active"));
      item.classList.add("active");
      this._selectPaper(paper, i);
    });

    this.elements.paperSidebarList.appendChild(item);
  });
};

DOMManager.prototype._setupPaperSidebarFilters = function() {
  const btns = document.querySelectorAll("[data-psort]");
  btns.forEach(btn => {
    btn.addEventListener("click", () => {
      btns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      this._renderPaperSidebar(
        window.appState.currentPaperViewPapers,
        btn.dataset.psort
      );
    });
  });
};

// Sets the top-bar badge to one of four states: none, oa, oa-pdf, degraded.
// Always resets classes and text first so stale state from a previous
// paper selection never leaks into the current one.
DOMManager.prototype._setTopBarBadge = function(state, label) {
  const badge = this.elements.paperOABadge;
  if (!badge) return;

  badge.classList.remove("paper-badge-degraded", "paper-badge-oa", "paper-badge-oa-pdf");

  if (state === "none") {
    badge.style.display = "none";
    return;
  }

  badge.style.display = "inline-flex";
  badge.textContent = label;

  if (state === "oa") badge.classList.add("paper-badge-oa");
  if (state === "oa-pdf") badge.classList.add("paper-badge-oa-pdf");
  if (state === "degraded") badge.classList.add("paper-badge-degraded");
};

DOMManager.prototype._selectPaper = function(paper, index) {
  window.appState.currentPaperViewSelected = paper;

  // Update top bar
  if (this.elements.paperViewTitle) {
    this.elements.paperViewTitle.textContent = paper.title || "Untitled";
  }
  if (this.elements.paperViewMeta) {
    const authors = paper.authors?.slice(0, 2).map(a => a.name).join(", ") || "";
    const year = paper.publication_year || "";
    this.elements.paperViewMeta.textContent =
      [authors, year].filter(Boolean).join(" · ");
  }

  // Reset badge to the pre-fetch state before any extraction attempt.
  // This clears any "Abstract only" / degraded state left over from a
  // previously selected paper.
  if (paper.is_open_access && paper.has_pdf_link) {
    this._setTopBarBadge("oa-pdf", "OA · PDF");
  } else if (paper.is_open_access) {
    this._setTopBarBadge("oa", "Open Access");
  } else {
    this._setTopBarBadge("none");
  }

  if (this.elements.paperDOILink) {
    const pdfUrl = paper.pdf_url || (paper.doi ? `https://doi.org/${paper.doi}` : null);
    if (pdfUrl) {
      this.elements.paperDOILink.href = pdfUrl;
      this.elements.paperDOILink.style.display = "inline-flex";
    } else {
      this.elements.paperDOILink.style.display = "none";
    }
  }

  // Clear QA chat for new paper
  if (this.elements.paperQAChat) {
    this.elements.paperQAChat.innerHTML = "";
  }
  if (this.elements.paperQAStatus) {
    this.elements.paperQAStatus.textContent = "";
  }

  // Reset unavailable-state copy to generic defaults before any attempt.
  if (this.elements.paperUnavailableTitle) {
    this.elements.paperUnavailableTitle.textContent = "Full text not available.";
  }
  if (this.elements.paperUnavailableSub) {
    this.elements.paperUnavailableSub.textContent =
      "You can still ask general questions using the summary below.";
  }

  // Only attempt extraction if a PDF link actually exists.
  // is_open_access alone is not enough: a green-OA paper can have
  // only a landing_page_url and no fetchable PDF.
  if (paper.has_pdf_link && (paper.pdf_url || paper.oa_url)) {
    this._loadPaperPDF(paper);
  } else if (paper.is_open_access) {
    // Open access per OpenAlex, but no direct PDF link to fetch.
    this._showPaperState("unavailable");
    if (this.elements.paperUnavailableSub) {
      this.elements.paperUnavailableSub.textContent =
        "This paper is open access, but no direct PDF link was found. Using abstract.";
    }
    if (this.elements.paperQAStatus) {
      this.elements.paperQAStatus.textContent = "Using abstract";
    }
  } else {
    this._showPaperState("unavailable");
    if (this.elements.paperQAStatus) {
      this.elements.paperQAStatus.textContent = "Using abstract";
    }
  }

  // Mark active in sidebar
  const items = this.elements.paperSidebarList?.querySelectorAll(".paper-sidebar-item");
  if (items) {
    items.forEach((el, i) => {
      el.classList.toggle("active", i === index);
    });
  }
};

DOMManager.prototype._showPaperState = function(state) {
  // state: "idle" | "loading" | "extracted" | "unavailable"
  const map = {
    idle: this.elements.paperIdleState,
    loading: this.elements.paperLoadingState,
    extracted: this.elements.paperExtractedState,
    unavailable: this.elements.paperUnavailableState,
  };
  Object.entries(map).forEach(([key, el]) => {
    if (el) el.style.display = key === state ? (key === "extracted" ? "block" : "flex") : "none";
  });
};

DOMManager.prototype._loadPaperPDF = async function(paper) {
  this._showPaperState("loading");

  const openalex_id = paper.id || paper.openalex_id || "";
  const pdf_url = paper.pdf_url || paper.oa_url || "";
  const is_open_access = paper.is_open_access || false;

  try {
    const response = await fetch("/api/extract-pdf/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": window.csrfToken,
      },
      body: JSON.stringify({ openalex_id, pdf_url, is_open_access }),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.error || `HTTP ${response.status}`);
    }

    const data = await response.json();
    if (!data.success || !data.markdown) {
      this._showPaperState("unavailable");
      if (this.elements.paperUnavailableSub) {
        this.elements.paperUnavailableSub.textContent =
          data.error || "This publisher blocks automated access.";
      }
      this._setTopBarBadge("degraded", "Abstract only");
      if (this.elements.paperQAStatus) {
        this.elements.paperQAStatus.textContent = `Using abstract (${data.error || "extraction failed"})`;
      }
      return;
    }

    // Instead of rendering full text, show a clean readiness card
    if (this.elements.paperMarkdown) {
      this.elements.paperMarkdown.innerHTML = `
        <div style="padding: 2rem; background: rgba(30, 41, 59, 0.5); border: 1px solid rgba(255,255,255,0.1); border-radius: 0.75rem; text-align: center;">
          <i class="fa-solid fa-circle-check" style="font-size: 2.5rem; color: #22c55e; margin-bottom: 1rem;"></i>
          <h3 style="font-size: 1.25rem; font-weight: 600; color: #f8fafc; margin-bottom: 0.5rem;">Paper Processed Successfully</h3>
          <p style="color: #94a3b8; font-size: 0.9rem; max-width: 400px; margin: 0 auto 1rem;">
            Full text (${data.page_count || "?"} pages) indexed and cached in the database.
          </p>
          <div style="font-size: 0.85rem; color: #64748b; background: rgba(0,0,0,0.2); padding: 0.5rem 1rem; border-radius: 0.375rem; display: inline-block;">
            💡 Use the side panel to chat or ask questions about this paper.
          </div>
        </div>
      `;
    }
    this._showPaperState("extracted");

    // Extraction verified: upgrade badge to reflect confirmed full text.
    this._setTopBarBadge("oa-pdf", "Full Text");

    if (this.elements.paperQAStatus) {
      this.elements.paperQAStatus.textContent =
        `${data.page_count || "?"} pages · ${data.cached ? "cached" : "just extracted"}`;
    }

  } catch (err) {
    this._showPaperState("unavailable");
    if (this.elements.paperUnavailableSub) {
      this.elements.paperUnavailableSub.textContent = err.message || "Extraction failed.";
    }
    this._setTopBarBadge("degraded", "Abstract only");
    if (this.elements.paperQAStatus) {
      this.elements.paperQAStatus.textContent = `Using abstract (${err.message || "extraction failed"})`;
    }
  }
};

DOMManager.prototype.handlePaperQA = async function() {
  const input = this.elements.paperQAInput;
  const question = input?.value.trim();
  const paper = window.appState.currentPaperViewSelected;

  if (!question || !paper) return;

  input.value = "";
  input.disabled = true;
  if (this.elements.paperQASendBtn) this.elements.paperQASendBtn.disabled = true;

  // Add user bubble
  const userBubble = document.createElement("div");
  userBubble.className = "paper-qa-bubble-user";
  userBubble.textContent = question;
  this.elements.paperQAChat.appendChild(userBubble);

  // Add thinking bubble
  const thinkingBubble = document.createElement("div");
  thinkingBubble.className = "paper-qa-bubble-ai";
  thinkingBubble.textContent = "Thinking...";
  this.elements.paperQAChat.appendChild(thinkingBubble);
  this.elements.paperQAChat.scrollTop = this.elements.paperQAChat.scrollHeight;

  try {
    const openalex_id = paper.id || paper.openalex_id || "";

    const response = await fetch("/api/ask-paper/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": window.csrfToken,
      },
      body: JSON.stringify({ openalex_id, question }),
    });

    const data = await response.json();
    thinkingBubble.remove();

    const aiBubble = document.createElement("div");
    aiBubble.className = "paper-qa-bubble-ai";
    aiBubble.innerHTML = this.markdownToHtml(data.answer || data.error || "No answer returned.");
    this.elements.paperQAChat.appendChild(aiBubble);

  } catch (err) {
    thinkingBubble.remove();
    const errBubble = document.createElement("div");
    errBubble.className = "paper-qa-bubble-ai";
    errBubble.textContent = "Error: " + err.message;
    this.elements.paperQAChat.appendChild(errBubble);
  } finally {
    input.disabled = false;
    if (this.elements.paperQASendBtn) this.elements.paperQASendBtn.disabled = false;
    input.focus();
    this.elements.paperQAChat.scrollTop = this.elements.paperQAChat.scrollHeight;
  }
};

// Utility methods
DOMManager.prototype.markdownToHtml = function(text) {
  if (!text) return "";

  const imagePlaceholders = [];

  let processedText = text
    .replace(/```(?:\s*\w+)?\s*\n([\s\S]*?)\n```/g, (match, p1) => {
      const code = this.escapeHtml(p1.trim());
      return `<pre class="code-block"><code>${code}</code></pre>`;
    })
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, src) => {
      const url = src.startsWith("http") || src.startsWith("/")
        ? src
        : `/media/${src}`;
      const imgTag = `<img src="${url}" alt="${alt}" style="max-width:100%;border-radius:0.5rem;margin:1rem 0;">`;
      const token = `@@IMG${imagePlaceholders.length}@@`;
      imagePlaceholders.push(imgTag);
      return token;
    })
    .replace(/^### (.+)$/gm, "<h4>$1</h4>")
    .replace(/^## (.+)$/gm, "<h3>$1</h3>")
    .replace(/^# (.+)$/gm, "<h2>$1</h2>")
    .replace(/\*\*([^\r\n*]+?)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^\r\n_]+?)__/g, "<strong>$1</strong>")
    .replace(/\*([^\r\n*]+?)\*/g, "<em>$1</em>")
    .replace(/_([^\r\n_]+?)_/g, "<em>$1</em>")
    .replace(/`([^`\r\n]+)`/g, "<code>$1</code>")
    .replace(/^\s*[-*+]\s+/gm, "• ")
    .replace(/\n/g, "<br>");

  imagePlaceholders.forEach((tag, i) => {
    processedText = processedText.replace(`@@IMG${i}@@`, tag);
  });

  return processedText;
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