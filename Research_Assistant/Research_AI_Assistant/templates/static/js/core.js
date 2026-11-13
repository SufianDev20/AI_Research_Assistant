import { getCsrfToken } from './utils.js';

window.csrfToken = getCsrfToken();

// ==================== DOM MANAGER ====================
export class DOMManager {
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
      yearMin: document.getElementById("yearMin"),
      yearMax: document.getElementById("yearMax"),
      yearError: document.getElementById("wsYearError"),
      searchBy: document.getElementById("searchBy"),
      quota: document.getElementById("quota"),

      // Advanced options panel (attached below the search input)
      advancedToggle: document.getElementById("wsAdvancedToggle"),
      advancedPanel: document.getElementById("wsAdvancedPanel"),
      filtersContainer: document.getElementById("wsFiltersContainer"),

      // Binder elements
      bindersContainer: document.getElementById("bindersContainer"),
      binderCount: document.getElementById("binderCount"),

      // Research view elements
      researchView: document.getElementById("researchView"),
      researchQuery: document.getElementById("researchQuery"),
      researchChatContainer: document.getElementById("researchChatContainer"),
      researchChatArea: document.querySelector(".research-chat-area"),
      researchInput: document.getElementById("research-input"),
      researchSendBtn: document.getElementById("research-send-btn"),
      researchBackBtn: document.getElementById("researchBackBtn"),
      saveToBinderBtn: document.getElementById("saveToBinderBtn"),

      // References panel elements
      sourcesPanel: document.getElementById("sourcesPanel"),
      sourcesList: document.getElementById("sourcesList"),
      referencesPanel: document.getElementById("referencesPanel"),
      referencesList: document.getElementById("referencesList"),

      // Load more elements
      loadMoreContainer: document.getElementById("loadMoreContainer"),
      loadMoreBtn: document.getElementById("loadMoreBtn"),
      loadMoreStatus: document.getElementById("loadMoreStatus"),

      // Profile elements: the account menu (#profileMenu) is entirely
      // owned by profile.js, including its own outside-click/Escape
      // close handling — nothing cached or wired here.

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
      elements.queryInput.addEventListener(
        "keydown",
        function (e) {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            this.handleSearch();
          }
        }.bind(this),
      );
    }

    // Filter listeners
    if (elements.yearFilter) {
      elements.yearFilter.addEventListener(
        "input",
        function () {
          this.updateYearLabel();
        }.bind(this),
      );
      elements.yearFilter.addEventListener(
        "mousedown",
        function () {
          this.showTooltip();
        }.bind(this),
      );
      elements.yearFilter.addEventListener(
        "mouseup",
        function () {
          this.hideTooltip();
        }.bind(this),
      );
      elements.yearFilter.addEventListener(
        "touchstart",
        function () {
          this.showTooltip();
        }.bind(this),
      );
      elements.yearFilter.addEventListener(
        "touchend",
        function () {
          this.hideTooltip();
        }.bind(this),
      );
    }

    // Years: two typeable/steppable number inputs (min=1900, max=2026).
    // Validated on blur/change rather than every keystroke, so a user
    // can freely type "19" while still building "1990" without it
    // being clamped mid-entry.
    if (elements.yearMin && elements.yearMax) {
      const onYearChange = function () {
        this.validateYearRange();
      }.bind(this);
      elements.yearMin.addEventListener("change", onYearChange);
      elements.yearMax.addEventListener("change", onYearChange);
      elements.yearMin.addEventListener(
        "blur",
        function () {
          this.validateYearRange();
        }.bind(this),
      );
      elements.yearMax.addEventListener(
        "blur",
        function () {
          this.validateYearRange();
        }.bind(this),
      );

      // Clears a stale correction message once the user starts editing
      // a year field again, rather than leaving it up until the next
      // blur (which may be on the other, unrelated field).
      const clearYearError = function () {
        if (elements.yearError) elements.yearError.hidden = true;
      };
      elements.yearMin.addEventListener("input", clearYearError);
      elements.yearMax.addEventListener("input", clearYearError);
    }

    this.setupAdvancedOptionsToggle();

    // Research view listeners. Follow-up submissions open the paper
    // analysis page (see handleFollowUpQuestion in research.js) instead
    // of continuing an in-page chat.
    if (elements.researchSendBtn) {
      elements.researchSendBtn.addEventListener(
        "click",
        function () {
          this.handleFollowUpQuestion();
        }.bind(this),
      );
    }

    if (elements.researchInput) {
      elements.researchInput.addEventListener(
        "keydown",
        function (e) {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            this.handleFollowUpQuestion();
          }
        }.bind(this),
      );
    }

    if (elements.researchBackBtn) {
      elements.researchBackBtn.addEventListener(
        "click",
        function () {
          this.hideResearchView();
        }.bind(this),
      );
    }

    if (elements.saveToBinderBtn) {
      elements.saveToBinderBtn.addEventListener(
        "click",
        function () {
          this.saveToBinder();
        }.bind(this),
      );
    }

    // Load more button listener
    if (elements.loadMoreBtn) {
      elements.loadMoreBtn.addEventListener(
        "click",
        function () {
          this.loadMorePapers();
        }.bind(this),
      );
    }

    // Global keyboard shortcuts
    document.addEventListener("keydown", function (e) {
      if (e.metaKey && e.key === "k") {
        e.preventDefault();
        if (!window.appState.isResearchView && elements.queryInput) {
          elements.queryInput.focus();
        } else if (window.appState.isResearchView && elements.researchInput) {
          elements.researchInput.focus();
        }
      }
    });
  }

  // ==================== EVENT HANDLERS ====================
  handleSearch() {
    var query = this.elements.queryInput
      ? this.elements.queryInput.value.trim()
      : "";
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
      bindersSection: !!this.elements.bindersSection,
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

    // Initialize references panel to be visible with empty state
    if (this.elements.referencesPanel) {
      console.log("Initializing references panel");
      this.elements.referencesPanel.style.display = "flex";
      if (this.elements.referencesList) {
        this.elements.referencesList.innerHTML =
          '<div class="references-empty">No papers retrieved yet. Research results will appear here.</div>';
      }
    } else {
      console.warn("References panel element not found");
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

    window.appState.isResearchView = true;

    // Create temporary binder
    if (query) {
      console.log("Creating temporary binder with query:", query);
      window.appState.currentResearchBinder = {
        id: "temp-" + Date.now(),
        name: query.length > 35 ? query.substring(0, 32) + "..." : query,
        color: "#" + Math.floor(Math.random() * 16777215).toString(16),
        messages: [{ role: "user", content: query }],
        papers: [],
      };
      console.log(
        "Temporary binder created:",
        window.appState.currentResearchBinder,
      );
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
      window.appState.isResearchView = false;
      window.appState.currentResearchBinder = null;
    }
  }

  hideResearchView() {
    // Hide research view
    if (this.elements.researchView) {
      this.elements.researchView.classList.remove("show");
    }

    // Show hero and binders
    if (this.elements.heroSection)
      this.elements.heroSection.style.display = "flex";
    if (this.elements.bindersSection)
      this.elements.bindersSection.style.display = "block";

    this.renderBinders();

    window.appState.isResearchView = false;
    window.appState.currentResearchBinder = null;

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
        "<span>Generating response...</span>" +
        "</div>";
    }

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
  }
}
