import { DOMManager } from './core.js';

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