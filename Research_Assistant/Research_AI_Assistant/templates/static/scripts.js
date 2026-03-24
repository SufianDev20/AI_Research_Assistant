document.addEventListener("DOMContentLoaded", function() {
  // ==================== BRAIN AI RESEARCH ASSISTANT ====================
  // DOM-oriented JavaScript Architecture

  // ==================== GLOBAL STATE ====================
  class AppState {
    constructor() {
      this.isThinking = false;
      this.binders = [];
      this.currentOpenBinderId = null;
      this.currentResearchBinder = null;
      this.isResearchView = false;
      this.nextCursor = null;
      this.totalCount = 0;
      this.isLoadingMore = false;
      this.lastLLMCall = 0; // Rate limiting for OpenRouter
      this.searchParams = {
        query: "",
        mode: "open_access",
        maxYear: "2026",
        perPage: 5,
      };
    }
  }

  // ==================== DOM MANAGER ====================
  class DOMManager {
    constructor() {
      this.elements = this.cacheElements();
      this.setupEventListeners();
    }

    cacheElements() {
      return {
        // Search elements
        queryInput: document.getElementById("queryInput"),
        searchButton: document.querySelector(".search-button"),

        // Filter elements
        yearFilter: document.getElementById("yearFilter"),
        yearValue: document.getElementById("yearValue"),
        sliderTooltip: document.getElementById("sliderTooltip"),
        searchBy: document.getElementById("searchBy"),
        quota: document.getElementById("quota"),

        // Binder elements
        bindersContainer: document.getElementById("bindersContainer"),
        binderCount: document.getElementById("binderCount"),

        // Research view elements
        researchView: document.getElementById("researchView"),
        researchQuery: document.getElementById("researchQuery"),
        researchChatContainer: document.getElementById("researchChatContainer"),
        researchInput: document.getElementById("research-input"),
        researchSendBtn: document.getElementById("research-send-btn"),
        researchBackBtn: document.getElementById("researchBackBtn"),
        saveToBinderBtn: document.getElementById("saveToBinderBtn"),

        // Load more elements
        loadMoreContainer: document.getElementById("loadMoreContainer"),
        loadMoreBtn: document.getElementById("loadMoreBtn"),
        loadMoreStatus: document.getElementById("loadMoreStatus"),

        // Modal elements (backwards compatibility)
        modalOverlay: document.getElementById("modalOverlay"),
        modalChatContainer: document.getElementById("modalChatContainer"),
        modalInput: document.getElementById("modal-input"),
        modalSendBtn: document.getElementById("modal-send-btn"),

        // Profile elements
        profileDropdown: document.getElementById("profileDropdown"),

        // Section elements
        heroSection: document.querySelector(".hero-section"),
        bindersSection: document.querySelector(".binders-section"),
      };
    }

    setupEventListeners() {
      var elements = this.elements; 

      // Search functionality - button uses onclick="performSearch()" in HTML
      // No additional event listener needed to avoid conflicts

      if (elements.queryInput) {
        elements.queryInput.addEventListener("keydown", function(e) {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            this.handleSearch();
          }
        }.bind(this));
      }

      // Filter listeners
      if (elements.yearFilter) {
        elements.yearFilter.addEventListener("input", function() {
          this.updateYearLabel();
        }.bind(this));
        elements.yearFilter.addEventListener("mousedown", function() {
          this.showTooltip();
        }.bind(this));
        elements.yearFilter.addEventListener("mouseup", function() {
          this.hideTooltip();
        }.bind(this));
        elements.yearFilter.addEventListener("touchstart", function() {
          this.showTooltip();
        }.bind(this));
        elements.yearFilter.addEventListener("touchend", function() {
          this.hideTooltip();
        }.bind(this));
      }

      // Research view listeners
      if (elements.researchSendBtn) {
        elements.researchSendBtn.addEventListener("click", function() {
          this.handleResearchMessage();
        }.bind(this));
      }

      if (elements.researchInput) {
        elements.researchInput.addEventListener("keydown", function(e) {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            this.handleResearchMessage();
          }
        }.bind(this));
      }

      if (elements.researchBackBtn) {
        elements.researchBackBtn.addEventListener("click", function() {
          this.hideResearchView();
        }.bind(this));
      }

      if (elements.saveToBinderBtn) {
        elements.saveToBinderBtn.addEventListener("click", function() {
          this.saveToBinder();
        }.bind(this));
      }

      // Load more button listener
      if (elements.loadMoreBtn) {
        elements.loadMoreBtn.addEventListener("click", function() {
          this.loadMorePapers();
        }.bind(this));
      }

      // Modal listeners (backwards compatibility)
      if (elements.modalSendBtn) {
        elements.modalSendBtn.addEventListener("click", function() {
          this.handleModalMessage();
        }.bind(this));
      }

      if (elements.modalInput) {
        elements.modalInput.addEventListener("keydown", function(e) {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            this.handleModalMessage();
          }
        }.bind(this));
      }

      // Global keyboard shortcuts
      document.addEventListener("keydown", function(e) {
        if (e.metaKey && e.key === "k") {
          e.preventDefault();
          if (!appState.isResearchView && elements.queryInput) {
            elements.queryInput.focus();
          } else if (appState.isResearchView && elements.researchInput) {
            elements.researchInput.focus();
          }
        }
      });

      // Outside click for dropdown
      document.addEventListener("click", function(e) {
        if (
          elements.profileDropdown &&
          !e.target.closest("#profileDropdown") &&
          !e.target.closest('button[onclick="toggleProfileDropdown()"]')
        ) {
          elements.profileDropdown.classList.add("hidden");
        }
      });
    }

    // ==================== EVENT HANDLERS ====================
    handleSearch() {
      var query = this.elements.queryInput ? this.elements.queryInput.value.trim() : "";
      console.log("handleSearch called with query:", query);
      
      if (!query) {
        console.log("Empty query - showing alert");
        alert("Type a research question!");
        return;
      }

      console.log("Elements available:", {
        queryInput: !!this.elements.queryInput,
        researchView: !!this.elements.researchView,
        heroSection: !!this.elements.heroSection,
        bindersSection: !!this.elements.bindersSection
      });

      try {
        console.log("Calling showResearchView with query:", query);
        this.showResearchView(query);
        this.elements.queryInput.value = "";
      } catch (error) {
        console.error("Error in handleSearch:", error);
        alert("Failed to start research. Please try again.");
      }
    }

    handleResearchMessage() {
      var input = this.elements.researchInput;
      var text = input ? input.value.trim() : "";
      if (!text || appState.isThinking || !appState.currentResearchBinder)
        return;

      appState.currentResearchBinder.messages.push({
        role: "user",
        content: text,
      });
      this.addMessage(text, true, this.elements.researchChatContainer);
      input.value = "";
      this.generateResearchResponse();
    }

    handleModalMessage() {
      var input = this.elements.modalInput;
      var text = input ? input.value.trim() : "";
      if (!text || appState.isThinking || !appState.currentOpenBinderId) return;

      var binder = appState.binders.find(function(b) { return b.id === appState.currentOpenBinderId; });
      if (!binder) return;

      binder.messages.push({ role: "user", content: text });
      this.addMessage(text, true, this.elements.modalChatContainer);
      input.value = "";
      this.generateAssistantResponse(binder, this.elements.modalChatContainer);
    }

    // ==================== DOM MANIPULATION ====================
    showResearchView(query) {
      console.log("showResearchView called with query:", query);
      
      // Hide hero and binders
      if (this.elements.heroSection) {
        console.log("Hiding hero section");
        this.elements.heroSection.style.display = "none";
      } else {
        console.warn("Hero section element not found");
      }
      
      if (this.elements.bindersSection) {
        console.log("Hiding binders section");
        this.elements.bindersSection.style.display = "none";
      } else {
        console.warn("Binders section element not found");
      }

      // Show research view
      if (this.elements.researchView) {
        console.log("Showing research view");
        this.elements.researchView.classList.add("show");
      } else {
        console.warn("Research view element not found");
        return;
      }

      // Set query top of bar 
      if (this.elements.researchQuery) {
        console.log("Setting research query text:", query);
        this.elements.researchQuery.textContent = query;
      } else {
        console.warn("Research query element not found");
      }

      // Hide save button only till first AI response appears
      if (this.elements.saveToBinderBtn) {
        console.log("Hiding save button initially");
        this.elements.saveToBinderBtn.style.display = "none";
      } else {
        console.warn("Save button element not found");
      }

      // Clear chat
      if (this.elements.researchChatContainer) {
        console.log("Clearing research chat container");
        this.elements.researchChatContainer.innerHTML = "";
      } else {
        console.warn("Research chat container element not found");
        return;
      }

      // Add user message
      if (query) {
        console.log("Adding user message to chat:", query);
        this.addMessage(query, true, this.elements.researchChatContainer);
      } else {
        console.warn("No query provided, skipping user message");
      }

      appState.isResearchView = true;

      // Create temporary binder
      if (query) {
        console.log("Creating temporary binder with query:", query);
        appState.currentResearchBinder = {
          id: "temp-" + Date.now(),
          name: query.length > 35 ? query.substring(0, 32) + "..." : query,
          color: "#" + Math.floor(Math.random() * 16777215).toString(16),
          messages: [{ role: "user", content: query }],
          papers: [],
        };
        console.log("Temporary binder created:", appState.currentResearchBinder);
      } else {
        console.warn("No query provided, skipping binder creation");
      }

      try {
        console.log("Calling generateResearchResponse");
        this.generateResearchResponse();
      } catch (error) {
        console.error("Error in showResearchView:", error);
        alert("Failed to start research. Please try again.");
        // Reset state on error
        appState.isResearchView = false;
        appState.currentResearchBinder = null;
      }
    }

    hideResearchView() {
      if (this.elements.researchView) {
        this.elements.researchView.classList.remove("show");
      }

      if (this.elements.heroSection) {
        this.elements.heroSection.style.display = "flex";
      }

      if (this.elements.bindersSection) {
        this.elements.bindersSection.style.display = "block";
      }

      this.renderBinders();

      appState.isResearchView = false;
      appState.currentResearchBinder = null;

      if (this.elements.researchInput) {
        this.elements.researchInput.value = "";
      }
    }

    addMessage(content, isUser = false, container) {
      if (!container) return null;

      var div = document.createElement("div");
      div.className = "message " + (isUser ? "user" : "assistant");

      if (isUser) {
        div.textContent = content;
      } else {
        div.innerHTML = 
                '<div class="thinking-indicator">' +
                    '<i class="fa-solid fa-brain thinking-icon"></i>' +
                    '<span>Generating response...</span>' +
                '</div>';
      }

      container.appendChild(div);
      container.scrollTop = container.scrollHeight;
      return div;
    }

    renderBinders() {
      if (!this.elements.bindersContainer) return;

      this.elements.bindersContainer.innerHTML = "";

      if (this.elements.binderCount) {
        this.elements.binderCount.textContent = appState.binders.length + " active";
      }

      appState.binders.forEach(function(binder) {
        var binderElement = this.createBinderElement(binder);
        this.elements.bindersContainer.appendChild(binderElement);
      }.bind(this));
    }

    createBinderElement(binder) {
      var lastMessage =
        binder.messages && binder.messages.length > 0
          ? binder.messages[binder.messages.length - 1].content
          : "No messages yet";
      var paperCount = binder.papers ? binder.papers.length : 0;
      var messageCount = binder.messages ? binder.messages.length : 0;
      var firstPaper =
        binder.papers && binder.papers.length > 0 ? binder.papers[0].title : null;

      var card = document.createElement("div");
      card.className = "binder-card";
      var self = this;
      card.onclick = function() {
        return self.openBinder(binder.id);
      };

      // Build HTML string with compatible syntax
      var html = '<div style="background: ' + binder.color + '" class="binder-color-bar"></div>' +
                 '<div class="binder-content">' +
                     '<div class="binder-header">' +
                         '<div onclick="event.stopImmediatePropagation(); domManager.editBinderColor(' + binder.id + ');" ' +
                              'style="background: ' + binder.color + '" class="binder-color-dot"></div>' +
                         '<div contenteditable="true" spellcheck="false" ' +
                              'onblur="domManager.saveBinderName(' + binder.id + ', this.innerText)" ' +
                              'class="binder-title">' + binder.name + '</div>' +
                     '</div>';

      // Add paper preview if exists
      if (firstPaper) {
        html += '<div class="binder-paper-preview">' +
                '<div class="binder-paper-label">Latest Paper</div>' +
                '<div class="binder-paper-title">' +
                    (firstPaper.substring(0, 80) + (firstPaper.length > 80 ? "..." : "")) +
                '</div>' +
                '</div>';
      }

      // Add stats
      html += '<div class="binder-stats">' +
                  '<div class="binder-stats-left">' +
                      '<div class="binder-stat">' +
                          '<i class="fa-solid fa-comment-dots"></i>' +
                          '<span>' + messageCount + ' messages</span>' +
                      '</div>';

      if (paperCount > 0) {
        html += '<div class="binder-stat">' +
                    '<i class="fa-solid fa-file-alt"></i>' +
                    '<span>' + paperCount + ' papers</span>' +
                '</div>';
      }

      html += '</div>' +
                  '<div class="binder-status">Live</div>' +
              '</div>';

      // Add last message if exists
      if (lastMessage && lastMessage !== "No messages yet") {
        html += '<div class="binder-last-message">' +
                    '<div class="binder-last-message-text">' +
                        '"' + (lastMessage.substring(0, 60) + (lastMessage.length > 60 ? "..." : "")) + '"' +
                    '</div>' +
                '</div>';
      }

      html += '</div>';
      card.innerHTML = html;

      return card;
    }
    // Opens Binder that is after saving
    openBinder(id) {
      var binder = appState.binders.find(function(b) { return b.id === id; });
      if (!binder) return;

      // Hide hero and binders
      if (this.elements.heroSection)
        this.elements.heroSection.style.display = "none";
      if (this.elements.bindersSection)
        this.elements.bindersSection.style.display = "none";

      // Show research view
      if (this.elements.researchView) {
        this.elements.researchView.classList.add("show");
      }

      // Set query
      var firstUserMessage = binder.messages.find(function(m) { return m.role === "user"; });
      if (this.elements.researchQuery) {
        this.elements.researchQuery.textContent = firstUserMessage
          ? firstUserMessage.content
          : binder.name;
      }

      // Hide save button for existing binders
      if (this.elements.saveToBinderBtn) {
        this.elements.saveToBinderBtn.style.display = "none";
      }

      // Clear and populate chat
      if (this.elements.researchChatContainer) {
        this.elements.researchChatContainer.innerHTML = "";
        // Clears container then replays full message history. addMessage handles both user and assistant messages. For assistant messages, thinking indicator placeholder is immediately replaced with actual content via markdownToHtml. opacity: "1" is set explicitly because new assistant messages animate in, but restored messages should appear instantly without animation.
        binder.messages.forEach(function(msg) {
          var div = this.addMessage(
            msg.content,
            msg.role === "user",
            this.elements.researchChatContainer,
          );
          if (msg.role === "assistant") {
            div.innerHTML = this.markdownToHtml(msg.content);
            div.style.opacity = "1";
          }
        }.bind(this));

        if (binder.papers?.length > 0) {
          this.renderPaperCards(
            binder.papers,
            this.elements.researchChatContainer,
          );
        }
      }

      appState.isResearchView = true;
      appState.currentResearchBinder = binder; // Brings the temporary saved binder into the frontend based on previous query
    }

    updateYearLabel() {
      if (!this.elements.yearFilter) return;

      var year = parseInt(this.elements.yearFilter.value);
      if (this.elements.yearValue) {
        this.elements.yearValue.textContent = year;
      }
      if (this.elements.sliderTooltip) {
        this.elements.sliderTooltip.textContent = year;
      }

      this.updateTooltipPosition();
    }

    // Adds .show class which sets opacity: 1 in CSS, fading in the tooltip. Immediately repositions it above the current thumb position before user starts dragging.
    showTooltip() {
      if (this.elements.sliderTooltip) {
        this.elements.sliderTooltip.classList.add("show");
        this.updateTooltipPosition();
      }
    }
    // Removes .show class, setting opacity back to 0, fading out the tooltip when dragging stops on year slider.
    hideTooltip() {
      if (this.elements.sliderTooltip) {
        this.elements.sliderTooltip.classList.remove("show");
      }
    }

    updateTooltipPosition() {
      if (!this.elements.yearFilter || !this.elements.sliderTooltip) return;

      var slider = this.elements.yearFilter;
      var tooltip = this.elements.sliderTooltip;
      var percent = (slider.value - slider.min) / (slider.max - slider.min); // Calculates how far along the slider's thumb is as a value between 0 and 1. For example if value is 2008, min is 1990, max is 2026: (2008 - 1990) / (2026 - 1990) = 18/36 = 0.5, meaning that thumb is at 50%. Converts into pixel values for slider width to be visible.
      var offset = percent * slider.offsetWidth;

      tooltip.style.left = offset + "px";
    }

    async retrieveFromBackend(
      query,
      minYear,
      maxYear,
      sortPref,
      maxPapers,
      randomSeed = null,
      cursor = null,
    ) {
      // Use cursor pagination if provided, otherwise start from beginning
      var cursorParam = cursor ? "&cursor=" + encodeURIComponent(cursor) : "";
      var seedParam = randomSeed ? "&random_seed=" + randomSeed : "";

      // Handle single year filter: if minYear is null, only use max_year
      let yearParams;
      if (minYear === null || minYear === undefined) {
        yearParams = "&max_year=" + maxYear;
      } else {
        yearParams = "&min_year=" + minYear + "&max_year=" + maxYear;
      }

      var url = "/api/search/?q=" + encodeURIComponent(query) + "&mode=" + sortPref + "&per_page=" + Math.min(maxPapers, 50) + yearParams + cursorParam + seedParam;

      var response = await fetch(url);
      if (!response.ok)
        throw new Error(`Backend search error ${response.status}`);

      const data = await response.json();
      return data; // Return full data object including pagination info
    }

    // ==================== API CALLS ====================
    async generateResearchResponse() {
      if (!appState.currentResearchBinder || appState.isThinking) return;

      const container = this.elements.researchChatContainer;
      const sendBtn = this.elements.researchSendBtn;

      appState.isThinking = true;
      if (sendBtn) sendBtn.disabled = true;

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
          appState.currentResearchBinder.messages[
            appState.currentResearchBinder.messages.length - 1
          ].content;

        // Always search for papers with a new random seed for each query
        const maxYear = this.elements.yearFilter?.value || "2026";
        const sortPref = this.elements.searchBy?.value || "best_match";
        const maxPapers = parseInt(this.elements.quota?.value || "5");

        // Store search parameters for load more functionality
        appState.searchParams = {
          query: lastUserQuery,
          mode: sortPref,
          maxYear: maxYear,
          perPage: maxPapers,
        };

        const searchData = await this.retrieveFromBackend(
          lastUserQuery,
          null, // minYear - not needed for single filter
          maxYear,
          sortPref,
          maxPapers,
        );

        // Store pagination info
        appState.nextCursor = searchData.next_cursor;
        appState.totalCount = searchData.total_count;

        // Replace papers with new search results
        appState.currentResearchBinder.papers = searchData.papers;
        const papersToUse = searchData.papers;

        // Apply rate limiting before LLM call
        await this.waitForRateLimit();

        const response = await fetch("/api/summarise/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
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

        // Render papers BELOW the assistant response
        if (searchData.papers.length > 0) {
          this.renderPaperCards(searchData.papers, this.elements.researchChatContainer);
        }

        // Update UI with pagination info after response + papers are rendered
        this.updatePaginationInfo();

        appState.currentResearchBinder.messages.push({
          role: "assistant",
          content: summary,
        });

        // Ensure load more visibility is refreshed after assistant response renders
        this.updatePaginationInfo();

        // Show save button for temporary binders
        if (this.elements.saveToBinderBtn && appState.currentResearchBinder?.id?.startsWith("temp-")) {
          console.log("Showing save button for temporary binder");
          this.elements.saveToBinderBtn.style.display = "block";
        }

      } catch (err) {
        console.error("Error in generateResearchResponse:", err);
        // Replace the "Generating response..." placeholder with the error
        if (assistantDiv) {
          assistantDiv.innerHTML = "Error: " + (err && err.message ? err.message : "Unknown error");
          assistantDiv.style.opacity = "1";
        }
        
        // Show user-friendly error message but continue flow
        if (this.elements.loadMoreStatus) {
          this.elements.loadMoreStatus.textContent = `Error: ${err.message}`;
        }
        
        // Still update pagination info even on error to show correct state
        this.updatePaginationInfo();
      } finally {
        console.log("generateResearchResponse completed, setting isThinking to false");
        appState.isThinking = false;
      }
    }

    async loadMorePapers() {
      if (!appState.nextCursor || appState.isLoadingMore) return;

      appState.isLoadingMore = true;
      const btn = this.elements.loadMoreBtn;
      const status = this.elements.loadMoreStatus;

      if (btn) btn.disabled = true;
      if (status) status.textContent = "Loading more papers...";

      // Ensure button remains visible during loading
      if (this.elements.loadMoreContainer) {
        this.elements.loadMoreContainer.style.display = "flex";
      }

      try {
        const perPage = appState.searchParams?.perPage || 25;
        const response = await fetch(
          `/api/search/?q=${encodeURIComponent(appState.searchParams.query)}&mode=${appState.searchParams.mode}&cursor=${encodeURIComponent(appState.nextCursor)}&load_more=true&per_page=${perPage}&max_year=${appState.searchParams.maxYear}`,
        );

        if (!response.ok) {
          throw new Error(`Load more error ${response.status}`);
        }

        const data = await response.json();

        // Update cursor for next load
        appState.nextCursor = data.next_cursor;

        // Append new papers to the main papers array
        appState.currentResearchBinder.papers.push(...data.papers);

        // Update the binder in the binders array if it's an existing binder
        if (!appState.currentResearchBinder.id.startsWith("temp-")) {
          const binderIndex = appState.binders.findIndex(
            (b) => b.id === appState.currentResearchBinder.id,
          );
          if (binderIndex !== -1) {
            // Update the binder in the array with current state
            appState.binders[binderIndex] = JSON.parse(
              JSON.stringify(appState.currentResearchBinder),
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
              "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify({
              query: appState.searchParams.query,
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

          // Render additional papers BELOW the additional summary
          this.renderAdditionalPapers(data.papers);

          // Also add summary to messages array for persistence
          if (appState.currentResearchBinder) {
            appState.currentResearchBinder.messages.push({
              role: "assistant",
              content: summary,
            });

            // Update binder in array if it's an existing binder
            if (!appState.currentResearchBinder.id.startsWith("temp-")) {
              const binderIndex = appState.binders.findIndex(
                (b) => b.id === appState.currentResearchBinder.id,
              );
              if (binderIndex !== -1) {
                appState.binders[binderIndex] = JSON.parse(
                  JSON.stringify(appState.currentResearchBinder),
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
            <div style="display: flex; align-items: center; justify-content: center; gap: 0.5rem; margin-bottom: 0.5rem;">
              <span>⚠️</span>
              <span>Summary temporarily unavailable - papers loaded successfully</span>
            </div>
            <button id="retry-summary-${Date.now()}" style="
              background: rgba(239, 68, 68, 0.2);
              border: 1px solid rgba(239, 68, 68, 0.3);
              color: #fca5a5;
              padding: 0.25rem 0.75rem;
              border-radius: 0.25rem;
              font-size: 0.75rem;
              cursor: pointer;
              margin-top: 0.5rem;
            ">Retry Summary</button>
          `;
          this.elements.researchChatContainer.appendChild(errorDiv);

          // Render additional papers BELOW the summary error message
          this.renderAdditionalPapers(data.papers);

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
                    "X-CSRFToken": csrfToken,
                  },
                  body: JSON.stringify({
                    query: appState.searchParams.query,
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

                  // Render additional papers BELOW the retried summary
                  this.renderAdditionalPapers(data.papers);
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
        appState.isLoadingMore = false;
        if (btn) btn.disabled = false;
        if (status) status.textContent = "";

        // Final pagination update to ensure button visibility is correct
        this.updatePaginationInfo();
      }
    }

    async waitForRateLimit() {
      const MIN_INTERVAL = 3000; // 3 seconds between LLM calls
      const now = Date.now();
      const timeSinceLastCall = now - appState.lastLLMCall;

      if (timeSinceLastCall < MIN_INTERVAL) {
        const waitTime = MIN_INTERVAL - timeSinceLastCall;
        await new Promise((resolve) => setTimeout(resolve, waitTime));
      }

      appState.lastLLMCall = Date.now();
    }

    ensureElements() {
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
    }

    updatePaginationInfo() {
      // Ensure elements are available
      this.ensureElements();

      const totalLoaded = appState.currentResearchBinder.papers?.length || 0;
      const totalCount = appState.totalCount;

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
            ${appState.nextCursor ? `(more available)` : "(all loaded)"}
          </div>
        `;
      }

      // Show or hide load more button based on nextCursor and loading state
      // Keep button visible as long as there are more papers to load
      if (this.elements.loadMoreContainer) {
        const hasMore = appState.nextCursor && !appState.isLoadingMore;

        if (hasMore) {
          this.elements.loadMoreContainer.style.display = "flex";
          // Ensure button has click handler
          const loadBtn = document.getElementById("loadMoreBtn");
          if (loadBtn && !loadBtn.onclick) {
            loadBtn.onclick = () => this.loadMorePapers();
          }
        } else if (appState.isLoadingMore) {
          // Keep button visible during loading
          this.elements.loadMoreContainer.style.display = "flex";
        } else {
          // Only hide when we know there are no more papers AND not loading
          this.elements.loadMoreContainer.style.display = "none";
        }
      }
    }

    renderAdditionalPapers(papers) {
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
    }

    // ==================== UTILITY METHODS ====================
    markdownToHtml(text) {
      if (!text) return "";

      // Handle References section with proper formatting
      let processedText = text.replace(
        /^(References:\s*\n?)([\s\S]*?)/gm,
        (match, header, references) => {
          if (references && references.trim()) {
            const refLines = references.trim().split('\n');
            let refHtml = '';
            for (let i = 0; i < refLines.length; i++) {
              const line = refLines[i].trim();
              if (line) {
                refHtml += `<div style="margin-bottom: 0.5rem; line-height: 1.6;">${this.escapeHtml(line)}</div>`;
              }
            }
            return `<div class="references-section">
              <h4 style="color: #0f172a; font-size: 1.1rem; font-weight: 600; margin: 1.5rem 0 1rem; border-bottom: 2px solid #2563eb; padding-bottom: 0.5rem;">
                📚 References
              </h4>
              <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 0.75rem; padding: 1rem; margin-bottom: 1rem;">
                ${refHtml}
              </div>
            </div>`;
          }
          return match;
        }
      );

      return processedText
        .replace(/```(?:\s*\w+)?\s*\n([\s\S]*?)\n```/g, (match, p1) => {
          const code = this.escapeHtml(p1.trim());
          return `<pre class="code-block"><code>${code}</code></pre>`;
        })
        .replace(/\*\*([^\r\n*]+?)\*\*/g, "<strong>$1</strong>")
        .replace(/__([^\r\n_]+?)__/g, "<strong>$1</strong>")
        .replace(/\*([^\r\n*]+?)\*/g, "<em>$1</em>")
        .replace(/_([^\r\n_]+?)_/g, "<em>$1</em>")
        .replace(/`([^`\r\n]+)`/g, "<code>$1</code>")
        .replace(/^\s*[-*+]\s+/gm, "• ")
        .replace(/\n/g, "<br>");
    }

    escapeHtml(unsafe) {
      return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }

    renderPaperCards(papers, container) {
      if (!papers?.length || !container) return;

      const papersContainer = document.createElement("div");
      papersContainer.className = "papers-grid mt-4 mb-4";
      papersContainer.innerHTML =
        '<div class="papers-grid-title mb-3">RELEVANT PAPERS</div>';

      papers.forEach((paper, i) => {
        const paperCard = this.createPaperCard(paper, i);
        papersContainer.appendChild(paperCard);
      });

      container.appendChild(papersContainer);
    }

    createPaperCard(paper, index) {
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
    }

    // ==================== BINDER MANAGEMENT ====================
    saveToBinder() {
      if (!appState.currentResearchBinder) return;

      // Migrate additionalPapers to main papers array for compatibility
      if (
        appState.currentResearchBinder.additionalPapers &&
        appState.currentResearchBinder.additionalPapers.length > 0
      ) {
        appState.currentResearchBinder.papers.push(
          ...appState.currentResearchBinder.additionalPapers,
        );
        delete appState.currentResearchBinder.additionalPapers; // Remove old array
      }

      appState.binders.push({ ...appState.currentResearchBinder });
      this.renderBinders();
      this.generateTitle(appState.currentResearchBinder);
      this.hideResearchView();
    }

    async generateTitle(binder) {
      if (!binder) return;

      try {
        const response = await fetch("/api/generate_title/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
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
          console.log(`✅ Auto-titled: ${suggestedTitle}`);
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
    }

    // ==================== BINDER MANAGEMENT ====================
    saveBinderName(binderId, newName) {
      const binder = appState.binders.find((b) => b.id === binderId);
      if (binder && newName.trim() !== "") {
        binder.name = newName.trim();
        this.renderBinders();
      }
    }

    editBinderColor(binderId) {
      event.stopImmediatePropagation();
      const binder = appState.binders.find((b) => b.id === binderId);
      if (!binder) return;

      const colorPicker = document.createElement("input");
      colorPicker.type = "color";
      colorPicker.value = binder.color;
      colorPicker.style.position = "absolute";
      colorPicker.style.opacity = "0";
      document.body.appendChild(colorPicker);

      colorPicker.onchange = function () {
        binder.color = this.value;
        domManager.renderBinders();
        document.body.removeChild(colorPicker);
      };

      colorPicker.click();
    }

    // ==================== BACKWARDS COMPATIBILITY ====================
    generateAssistantResponse(binder, container) {
      // This method is kept for backwards compatibility with modal system
      if (appState.isThinking || !binder) return;

      const sendBtn = this.elements.modalSendBtn;
      appState.isThinking = true;
      if (sendBtn) sendBtn.disabled = true;

      const assistantDiv = this.addMessage("", false, container);

      // Similar implementation to generateResearchResponse but for modal
      async function generateResponse() {
        try {
          const maxYear = domManager.elements.yearFilter?.value || "2026";
          const sortPref = domManager.elements.searchBy?.value || "most-cited";
          const maxPapers = parseInt(domManager.elements.quota?.value || "5");

          const lastUserQuery =
            binder.messages[binder.messages.length - 1].content;
          const papers = await domManager.retrieveFromBackend(
            lastUserQuery,
            null, // minYear - not needed for single filter
            maxYear,
            sortPref,
            maxPapers,
          );

          binder.papers = papers;

          if (papers.length > 0) {
            domManager.renderPaperCards(papers, container);
          }

          const response = await fetch("/api/summarise/", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify({
              query: lastUserQuery,
              papers: papers,
            }),
          });

          if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || `Summarise error ${response.status}`);
          }

          const data = await response.json();
          const summary = data.summary || "No summary returned.";

          assistantDiv.innerHTML = domManager.markdownToHtml(summary);
          binder.messages.push({ role: "assistant", content: summary });

          if (binder.messages.length === 2) {
            domManager.generateTitle(binder);
          }
        } catch (err) {
          assistantDiv.innerHTML = `Error: ${err.message}`;
        } finally {
          appState.isThinking = false;
          if (sendBtn) sendBtn.disabled = false;
          if (domManager.elements.modalInput) {
            domManager.modalInput.focus();
          }
        }
      }

      generateResponse();
    }
  }

  // ==================== GLOBAL STATE ====================
  let appState;
  let domManager;

  // ==================== GLOBAL FUNCTIONS (for backwards compatibility) ====================
  // Global functions that can be called from HTML onclick attributes
  function toggleProfileDropdown() {
    const dropdown = document.getElementById("profileDropdown");
    if (dropdown) {
      dropdown.classList.toggle("hidden");
    }
  }

  function logout() {
    if (confirm("Log out of BRAIN?")) {
      alert("👋 Logged out (demo)");
    }
  }

  function resetFilters() {
    if (domManager) {
      // Reset year filter to default (2026)
      if (domManager.elements.yearFilter) {
        domManager.elements.yearFilter.value = "2026";
      }

      // Reset search by to default (best_match)
      if (domManager.elements.searchBy) {
        domManager.elements.searchBy.value = "best_match";
      }

      // Reset quota to default (5 papers)
      if (domManager.elements.quota) {
        domManager.elements.quota.value = "5";
      }

      // Update year label display
      domManager.updateYearLabel();
    }
  }

  function performSearch() {
    console.log("performSearch called");
    if (domManager) {
      console.log("domManager exists, calling handleSearch");
      domManager.handleSearch();
    } else {
      console.error("domManager not initialized yet");
      alert("Application still loading. Please try again in a moment.");
    }
  }

  window.toggleProfileDropdown = toggleProfileDropdown;
  window.logout = logout;
  window.resetFilters = resetFilters;
  window.performSearch = performSearch;

  function openBinder(id) {
    if (domManager) domManager.openBinder(id);
  }

  function closeModal() {
    if (domManager && domManager.elements.modalOverlay) {
      domManager.elements.modalOverlay.classList.add("hidden");
      domManager.elements.modalOverlay.classList.remove("flex");
      appState.currentOpenBinderId = null;
    }
  }

  function saveBinderName(binderId, newName) {
    if (domManager) domManager.saveBinderName(binderId, newName);
  }

  function editBinderColor(binderId) {
    if (domManager) domManager.editBinderColor(binderId);
  }

  window.openBinder = openBinder;
  window.closeModal = closeModal;
  window.saveBinderName = saveBinderName;
  window.editBinderColor = editBinderColor;

  // ==================== INITIALIZATION ====================
  function init() {
    appState = new AppState();
    domManager = new DOMManager();

    // Migrate existing binders with additionalPapers to new format
    migrateExistingBinders();

    // Initial render
    domManager.renderBinders();
    domManager.updateYearLabel();

    console.log("BRAIN AI Research Assistant initialized");
  }

  function migrateExistingBinders() {
    // Fix any existing binders that have separate additionalPapers arrays
    appState.binders.forEach((binder) => {
      if (binder.additionalPapers && binder.additionalPapers.length > 0) {
        // Move additional papers to main array
        binder.papers = binder.papers || [];
        binder.papers.push(...binder.additionalPapers);
        delete binder.additionalPapers; // Remove old array
        console.log(
          `Migrated binder "${binder.name}": ${binder.papers.length} total papers`,
        );
      }
    });
  }

  // Initialize the application
  init();
}); // End of DOMContentLoaded
