import { DOMManager } from './core.js';

// Extend DOMManager prototype with research-related methods
DOMManager.prototype.renderReferences = function(papers) {
  if (!this.elements.referencesPanel || !this.elements.referencesList)
    return;

  this.elements.referencesList.innerHTML = "";

  // Always show the panel - display empty state if no papers
  this.elements.referencesPanel.style.display = "flex";

  if (!papers || papers.length === 0) {
    const emptyState = document.createElement("div");
    emptyState.style.cssText =
      "padding: 2rem 1rem; text-align: center; color: #94a3b8; font-size: 0.9rem;";
    emptyState.textContent =
      "No papers retrieved yet. Research results will appear here.";
    this.elements.referencesList.appendChild(emptyState);
    return;
  }

  // Sort papers based on current filter
  const sortedPapers = this.sortPapers(papers);

  sortedPapers.forEach(
    function (paper, i) {
      var card = document.createElement("div");
      card.className = "source-card";

      var linkHtml =
        paper && paper.doi
          ? '<a class="source-link" href="https://doi.org/' +
            paper.doi +
            '" target="_blank" rel="noopener noreferrer">' +
            (paper.title || "Untitled") +
            "</a>"
          : paper && paper.title
            ? paper.title
            : "Untitled";

      var citationCount = paper.cited_by_count || 0;

      card.innerHTML =
        '<div class="source-number">' +
        (i + 1) +
        "</div>" +
        '<div class="source-title">' +
        linkHtml +
        "</div>" +
        '<div class="source-citation-count">' +
        citationCount +
        " citations</div>";

      card.addEventListener("click", (e) => {
           e.preventDefault();
           this.showPaperView(sortedPapers, i);
    });

      this.elements.referencesList.appendChild(card);
    }.bind(this),
  );
};

DOMManager.prototype.setReferencesFilterVisibility = function(visible) {
  const filters = this.elements.referencesPanel?.querySelector(
    ".references-filters",
  );
  if (!filters) return;
  filters.style.display = visible ? "flex" : "none";
};

DOMManager.prototype.sortPapers = function(papers) {
  const activeFilter = window.appState.currentFilter || "relevance";
  const sorted = [...papers];

  if (activeFilter === "cited_by_count") {
    sorted.sort(
      (a, b) => (b.cited_by_count || 0) - (a.cited_by_count || 0),
    );
  } else {
    sorted.sort(
      (a, b) => (b.relevance_score || 0) - (a.relevance_score || 0),
    );
  }

  return sorted;
};

DOMManager.prototype.setupFilterListeners = function() {
  const filterBtns = document.querySelectorAll(".filter-btn");
  filterBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (window.appState.isGeneratingResponse) return;
      filterBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      window.appState.currentFilter = btn.dataset.filter;

      if (window.appState.currentResearchBinder?.papers) {
        this.renderReferences(window.appState.currentResearchBinder.papers);
      }
    });
  });
};

DOMManager.prototype.generateResearchResponse = async function() {
  if (!window.appState.currentResearchBinder || window.appState.isThinking) return;

  const container = this.elements.researchChatContainer;
  const sendBtn = this.elements.researchSendBtn;

  window.appState.isThinking = true;
  window.appState.isGeneratingResponse = true;
  if (sendBtn) sendBtn.disabled = true;

  // Hide reference filters during generation
  this.setReferencesFilterVisibility(false);

  const assistantDiv = this.addMessage("", false, container);

  // Shows brain and generating response till LLM provides the response
  assistantDiv.innerHTML = `
        <div class="research-loading">
            <i class="fa-solid fa-brain"></i>
            <span>Generating response...</span>
        </div>
    `;

  try {
    const lastUserQuery =
      window.appState.currentResearchBinder.messages[
        window.appState.currentResearchBinder.messages.length - 1
      ].content;

    // Always search for papers with a new random seed for each query
    const minYear = this.elements.yearMin?.value || null;
    const maxYear =
      this.elements.yearMax?.value ||
      this.elements.yearFilter?.value ||
      "2026";
    const sortPref = this.elements.searchBy?.value || "best_match";
    const maxPapers = parseInt(this.elements.quota?.value || "5");

    // Store search parameters for load more functionality
    window.appState.searchParams = {
      query: lastUserQuery,
      mode: sortPref,
      minYear: minYear,
      maxYear: maxYear,
      perPage: maxPapers,
    };

    const searchData = await this.retrieveFromBackend(
      lastUserQuery,
      minYear,
      maxYear,
      sortPref,
      maxPapers,
    );

    // Store pagination info
    window.appState.nextCursor = searchData.next_cursor;
    window.appState.totalCount = searchData.total_count;

    // Replace papers with new search results
    window.appState.currentResearchBinder.papers = searchData.papers;
    const papersToUse = searchData.papers;

    this.renderReferences(papersToUse);

    // Apply rate limiting before LLM call
    await this.waitForRateLimit();

    const response = await fetch("/api/summarise/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
          "X-CSRFToken": window.csrfToken,
      },
      body: JSON.stringify({
        query: lastUserQuery,
        papers: papersToUse,
      }),
    });

    console.log("API response status:", response.status);

    if (!response.ok) {
      const err = await response.json();
      console.error("API error response:", err);
      throw new Error(err.error || `Summarise error ${response.status}`);
    }

    const data = await response.json();
    console.log("API response data:", data);
    const summary = data.summary || "No summary returned.";
    console.log("Generated summary length:", summary.length);

    // Replace the "Generating response..." placeholder with the actual response
    assistantDiv.innerHTML = this.markdownToHtml(summary);
    assistantDiv.style.opacity = "1";

    // Update UI with pagination info after response + papers are rendered
    this.updatePaginationInfo();

    window.appState.currentResearchBinder.messages.push({
      role: "assistant",
      content: summary,
    });

    // Ensure load more visibility is refreshed after assistant response renders
    this.updatePaginationInfo();

    // Show save button for temporary binders
    if (
      this.elements.saveToBinderBtn &&
      window.appState.currentResearchBinder?.id?.startsWith("temp-")
    ) {
      console.log("Showing save button for temporary binder");
      this.elements.saveToBinderBtn.style.display = "block";
    }
  } catch (err) {
    console.error("Error in generateResearchResponse:", err);
    // Replace the "Generating response..." placeholder with the error
    if (assistantDiv) {
      assistantDiv.innerHTML =
        "Error: " + (err && err.message ? err.message : "Unknown error");
      assistantDiv.style.opacity = "1";
    }

    // Show user-friendly error message but continue flow
    if (this.elements.loadMoreStatus) {
      this.elements.loadMoreStatus.textContent = `Error: ${err.message}`;
    }

    // Still update pagination info even on error to show correct state
    this.updatePaginationInfo();
  } finally {
    console.log(
      "generateResearchResponse completed, setting isThinking to false",
    );
    window.appState.isThinking = false;
    window.appState.isGeneratingResponse = false;
    // Show reference filters only after generation completes
    this.setReferencesFilterVisibility(true);
  }
};

DOMManager.prototype.loadMorePapers = async function() {
  if (!window.appState.nextCursor || window.appState.isLoadingMore) return;

  window.appState.isLoadingMore = true;
  const btn = this.elements.loadMoreBtn;
  const status = this.elements.loadMoreStatus;

  if (btn) btn.disabled = true;
  if (status) status.textContent = "Loading more papers...";

  // Ensure button remains visible during loading
  if (this.elements.loadMoreContainer) {
    this.elements.loadMoreContainer.style.display = "flex";
  }

  try {
    const perPage = window.appState.searchParams?.perPage || 25;
    let yearParams = "";
    if (window.appState.searchParams && window.appState.searchParams.minYear) {
      yearParams += `&min_year=${encodeURIComponent(window.appState.searchParams.minYear)}`;
    }
    if (window.appState.searchParams && window.appState.searchParams.maxYear) {
      yearParams += `&max_year=${encodeURIComponent(window.appState.searchParams.maxYear)}`;
    }

    const response = await fetch(
      `/api/search/?q=${encodeURIComponent(window.appState.searchParams.query)}&mode=${window.appState.searchParams.mode}&cursor=${encodeURIComponent(window.appState.nextCursor)}&load_more=true&per_page=${perPage}${yearParams}`,
    );

    if (!response.ok) {
      throw new Error(`Load more error ${response.status}`);
    }

    const data = await response.json();

    // Update cursor for next load
    window.appState.nextCursor = data.next_cursor;

    // Append new papers to the main papers array
    window.appState.currentResearchBinder.papers.push(...data.papers);

    this.renderReferences(window.appState.currentResearchBinder.papers);

    // Update the binder in the binders array if it's an existing binder
    if (!window.appState.currentResearchBinder.id.startsWith("temp-")) {
      const binderIndex = window.appState.binders.findIndex(
        (b) => b.id === window.appState.currentResearchBinder.id,
      );
      if (binderIndex !== -1) {
        // Update the binder in the array with current state
        window.appState.binders[binderIndex] = JSON.parse(
          JSON.stringify(window.appState.currentResearchBinder),
        );
        this.renderBinders(); // Update binder display
      }
    }

    // Summarize additional papers
    try {
      await this.waitForRateLimit();

      const summariseResponse = await fetch("/api/summarise/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
            "X-CSRFToken": window.csrfToken,
        },
        body: JSON.stringify({
          query: window.appState.searchParams.query,
          papers: data.papers,
        }),
      });

      if (!summariseResponse.ok) {
        const err = await summariseResponse.json();
        throw new Error(
          err.error || `Summarise error ${summariseResponse.status}`,
        );
      }

      const summariseData = await summariseResponse.json();
      const summary = summariseData.summary || "No summary returned.";

      // Add label for summary
      const labelDiv = document.createElement("div");
      labelDiv.textContent = "Summary of Additional Papers";
      labelDiv.className = "summary-label";
      this.elements.researchChatContainer.appendChild(labelDiv);

      // Add summary as assistant message
      const summaryDiv = this.addMessage(
        "",
        false,
        this.elements.researchChatContainer,
      );
      summaryDiv.innerHTML = this.markdownToHtml(summary);
      summaryDiv.style.opacity = "1";

      // Also add summary to messages array for persistence
      if (window.appState.currentResearchBinder) {
        window.appState.currentResearchBinder.messages.push({
          role: "assistant",
          content: summary,
        });

        // Update binder in array if it's an existing binder
        if (!window.appState.currentResearchBinder.id.startsWith("temp-")) {
          const binderIndex = window.appState.binders.findIndex(
            (b) => b.id === window.appState.currentResearchBinder.id,
          );
          if (binderIndex !== -1) {
            window.appState.binders[binderIndex] = JSON.parse(
              JSON.stringify(window.appState.currentResearchBinder),
            );
            this.renderBinders(); // Update binder display
          }
        }
      }
    } catch (err) {
      console.warn("Summary of additional papers failed:", err);

      // Show user-friendly error message but continue the flow
      const errorDiv = document.createElement("div");
      errorDiv.className = "summary-error-message";
      errorDiv.style.cssText = `
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.2);
        border-radius: 0.5rem;
        padding: 0.75rem;
        margin: 1rem 0;
        color: #fca5a5;
        font-size: 0.875rem;
        text-align: center;
      `;
      errorDiv.innerHTML = `
        <div style="margin-bottom: 0.5rem; font-weight: 600;">⚠️ Could not summarize additional papers</div>
        <div style="font-size: 0.9rem; color: #64748b; margin-bottom: 1rem;">${err.message}</div>
        <button style="background: #2563eb; color: white; border: none; padding: 0.5rem 1rem; border-radius: 0.5rem; cursor: pointer;">Try Again</button>
      `;
      this.elements.researchChatContainer.appendChild(errorDiv);

      // Add retry functionality
      const retryBtn = errorDiv.querySelector("button");
      if (retryBtn) {
        retryBtn.onclick = async () => {
          retryBtn.textContent = "Retrying...";
          retryBtn.disabled = true;
          try {
            await this.waitForRateLimit();

            const retryResponse = await fetch("/api/summarise/", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": window.csrfToken,
              },
              body: JSON.stringify({
                query: window.appState.searchParams.query,
                papers: data.papers,
              }),
            });

            if (retryResponse.ok) {
              const retryData = await retryResponse.json();
              const summary = retryData.summary || "No summary returned.";

              // Replace error message with successful summary
              errorDiv.remove();

              // Add label for summary
              const labelDiv = document.createElement("div");
              labelDiv.textContent = "Summary of Additional Papers";
              labelDiv.className = "summary-label";
              this.elements.researchChatContainer.appendChild(labelDiv);

              // Add summary as assistant message
              const summaryDiv = this.addMessage(
                "",
                false,
                this.elements.researchChatContainer,
              );
              summaryDiv.innerHTML = this.markdownToHtml(summary);
              summaryDiv.style.opacity = "1";
            } else {
              throw new Error("Retry failed");
            }
          } catch (retryErr) {
            retryBtn.textContent = "Retry Failed";
            retryBtn.disabled = false;
            console.warn("Summary retry failed:", retryErr);
          }
        };
      }

      // Continue without breaking the load more flow
      console.log("Load more flow continuing despite summary failure");
    }

    // Update pagination info after successful load
    this.updatePaginationInfo();

    // Show message if available (e.g., "No more papers available")
    if (data.message) {
      const messageDiv = document.createElement("div");
      messageDiv.textContent = data.message;
      messageDiv.className = "load-more-message";
      messageDiv.style.textAlign = "center";
      messageDiv.style.color = "#9ca3af";
      messageDiv.style.marginTop = "1rem";
      messageDiv.style.fontSize = "0.875rem";
      this.elements.researchChatContainer.appendChild(messageDiv);
    }
  } catch (err) {
    if (status) status.textContent = `Error: ${err.message}`;
    // Still update pagination info even on error to show correct state
    this.updatePaginationInfo();
  } finally {
    window.appState.isLoadingMore = false;
    if (btn) btn.disabled = false;
    if (status) status.textContent = "";

    // Final pagination update to ensure button visibility is correct
    this.updatePaginationInfo();
  }
};

DOMManager.prototype.waitForRateLimit = async function() {
  const MIN_INTERVAL = 3000; // 3 seconds between LLM calls
  const now = Date.now();
  const timeSinceLastCall = now - window.appState.lastLLMCall;

  if (timeSinceLastCall < MIN_INTERVAL) {
    const waitTime = MIN_INTERVAL - timeSinceLastCall;
    await new Promise((resolve) => setTimeout(resolve, waitTime));
  }

  window.appState.lastLLMCall = Date.now();
};

DOMManager.prototype.ensureElements = function() {
  // Re-cache elements if they're missing
  if (!this.elements.loadMoreContainer) {
    this.elements.loadMoreContainer =
      document.getElementById("loadMoreContainer");
  }
  if (!this.elements.loadMoreBtn) {
    this.elements.loadMoreBtn = document.getElementById("loadMoreBtn");
  }
  if (!this.elements.researchChatContainer) {
    this.elements.researchChatContainer = document.getElementById(
      "researchChatContainer",
    );
  }
};

DOMManager.prototype.updatePaginationInfo = function() {
  // Ensure elements are available
  this.ensureElements();

  const totalLoaded = window.appState.currentResearchBinder.papers?.length || 0;
  const totalCount = window.appState.totalCount || 0;;

  // Find or create pagination info element
  let infoElement = document.querySelector(".pagination-info");
  if (!infoElement) {
    infoElement = document.createElement("div");
    infoElement.className = "pagination-info";
    if (this.elements.researchChatContainer) {
      this.elements.researchChatContainer.appendChild(infoElement);
    }
  }

  if (infoElement) {
    infoElement.innerHTML = `
      <div class="pagination-text">
        Showing ${totalLoaded} of ${totalCount.toLocaleString()} papers
        ${window.appState.nextCursor ? `(more available)` : "(all loaded)"}
      </div>
    `;
  }

  // Show or hide load more button based on nextCursor and loading state
  // Keep button visible as long as there are more papers to load
  if (this.elements.loadMoreContainer) {
    const hasMore = window.appState.nextCursor && !window.appState.isLoadingMore;

    if (hasMore) {
      this.elements.loadMoreContainer.style.display = "flex";
      // Ensure button has click handler
      const loadBtn = document.getElementById("loadMoreBtn");
      if (loadBtn && !loadBtn.onclick) {
        loadBtn.onclick = () => this.loadMorePapers();
      }
    } else if (window.appState.isLoadingMore) {
      // Keep button visible during loading
      this.elements.loadMoreContainer.style.display = "flex";
    } else {
      // Only hide when we know there are no more papers AND not loading
      this.elements.loadMoreContainer.style.display = "none";
    }
  }
};

DOMManager.prototype.renderAdditionalPapers = function(papers) {
  if (!papers?.length) return;

  // Create a new separate papers section for loaded more papers
  const papersContainer = document.createElement("div");
  papersContainer.className = "papers-grid mt-4 mb-4";
  papersContainer.innerHTML =
    '<div class="papers-grid-title mb-3">ADDITIONAL PAPERS</div>';

  papers.forEach((paper, i) => {
    const paperCard = this.createPaperCard(paper, i);
    papersContainer.appendChild(paperCard);
  });

  // Add the new section to the chat container
  this.elements.researchChatContainer.appendChild(papersContainer);
};
