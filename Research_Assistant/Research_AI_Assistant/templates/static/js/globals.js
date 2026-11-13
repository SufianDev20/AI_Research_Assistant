import { AppState } from './state.js';
import { DOMManager } from './core.js';
import { YEAR_MIN, YEAR_MAX } from './constants.js';
import './search.js';
import './binders.js';
import './research.js';
import './paper.js';

// core.js (imported above via DOMManager) already sets window.csrfToken.

// ==================== GLOBAL VARIABLES ====================
let appState = new AppState(); // Initialize immediately
window.appState = appState;
let domManager;

// ==================== GLOBAL FUNCTIONS (for backwards compatibility) ====================
// Account menu (open/close, real Clerk sign-out) now lives entirely in
// profile.js — no global toggle/logout functions needed here anymore.

function resetFilters() {
  if (!domManager) {
    console.log("Reset requested before DOM Manager was ready");
    return;
  }

  // Values reset synchronously first -- the transition below is purely
  // decorative on top of this, so reset still fully works even if the
  // animation is skipped (reduced motion) or CSS/JS animation support
  // is unavailable for any reason.
  if (domManager.elements.yearMin && domManager.elements.yearMax) {
    domManager.elements.yearMin.value = String(YEAR_MIN);
    domManager.elements.yearMax.value = String(YEAR_MAX);
    if (domManager.elements.yearError) domManager.elements.yearError.hidden = true;
  }
  if (domManager.elements.searchBy) {
    domManager.elements.searchBy.value = "best_match";
  }
  if (domManager.elements.quota) {
    domManager.elements.quota.value = "5";
    // Setting .value directly does not fire "change" -- the ambient
    // background (js/workspace-bg.js) listens for it to resize its node
    // count to match, so Reset needs to dispatch one explicitly or the
    // background would silently keep showing the pre-reset count.
    domManager.elements.quota.dispatchEvent(new Event("change", { bubbles: true }));
  }

  domManager.playResetTransition();
}

function performSearch() {
  if (!domManager || !domManager.elements) {
    if (!performSearch.retryCount) performSearch.retryCount = 0;
    if (performSearch.retryCount < 50) {
      // Max 5 seconds
      performSearch.retryCount++;
      setTimeout(performSearch, 100);
      return;
    }
    alert("Application failed to load. Please refresh the page.");
    return;
  }
  performSearch.retryCount = 0; // Reset on success
  domManager.handleSearch();
}

// ==================== INITIALIZATION ====================
function init() {
  domManager = new DOMManager();

  // Initial render
  domManager.renderBinders();
  domManager.setupFilterListeners();

  // Expose domManager to global scope AFTER initialization. Binder
  // card actions (open/delete/rename/recolor) are wired by delegated
  // listeners in binders.js, not window-attached functions.
  window.domManager = domManager;

  console.log("BRAIN AI Research Assistant initialized");
}

// Attach functions to window for HTML onclick attributes
window.resetFilters = resetFilters;
window.performSearch = performSearch;

// Initialize the application
init();
