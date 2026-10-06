import { AppState } from './state.js';
import { DOMManager } from './core.js';
import './search.js';
import './binders.js';
import './modal.js';
import './research.js';
import './paper.js';

// Safely obtain CSRF token after DOM ready. Falls back to cookie if hidden input not present.
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}

let csrfToken = null;
const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
if (csrfInput && csrfInput.value) {
  csrfToken = csrfInput.value;
} else {
  csrfToken = getCookie('csrftoken');
}
window.csrfToken = csrfToken;

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
    domManager.elements.yearMin.value = "1900";
    domManager.elements.yearMax.value = "2026";
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

function deleteBinder(binderId) {
  console.log('deleteBinder called with ID:', binderId);
  console.log('domManager available:', !!domManager);
  if (domManager) domManager.deleteBinder(binderId);
  else console.error('domManager not available when deleteBinder called');
}

function openBinder(id) {
  if (domManager) domManager.openBinder(id);
}

function closeModal() {
  if (domManager) domManager.hideResearchView();
}

function saveBinderName(binderId, newName) {
  if (domManager) domManager.saveBinderName(binderId, newName);
}

function editBinderColor(binderId) {
  if (domManager) domManager.editBinderColor(binderId);
}

// ==================== INITIALIZATION ====================
function init() {
  domManager = new DOMManager();

  // Migrate existing binders with additionalPapers to new format
  migrateExistingBinders();

  // Initial render
  domManager.renderBinders();
  domManager.setupFilterListeners();

  // Expose domManager to global scope AFTER initialization
  window.domManager = domManager;
  window.openBinder = openBinder;
  window.closeModal = closeModal;
  window.saveBinderName = saveBinderName;
  window.editBinderColor = editBinderColor;
  window.deleteBinder = deleteBinder;

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

// Attach functions to window for HTML onclick attributes
window.resetFilters = resetFilters;
window.performSearch = performSearch;

// Initialize the application
init();
