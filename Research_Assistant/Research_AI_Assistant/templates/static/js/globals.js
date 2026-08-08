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
function toggleProfileDropdown() {
  const dropdown = document.getElementById("profileDropdown");
  if (dropdown) {
    dropdown.classList.toggle("show);
  }
}

function logout() {
  if (confirm("Log out of BRAIN?")) {
    alert("👋 Logged out (demo)");
  }
}

function resetFilters() {
  console.log("Reset button clicked");
  if (domManager) {
    console.log("DOM Manager exists");
    // Reset year range filter to default (1900-2026)
    if (domManager.elements.yearMin && domManager.elements.yearMax) {
      console.log("Resetting sliders to 1900 and 2026");
      // Reset slider values to defaults
      domManager.elements.yearMin.value = "1900";
      domManager.elements.yearMax.value = "2026";

      // Reset slider fills
      domManager.updateSingleSlider("min");
      domManager.updateSingleSlider("max");
      console.log("Sliders reset complete");
    } else {
      console.log("Sliders not found:", {
        yearMin: !!domManager.elements.yearMin,
        yearMax: !!domManager.elements.yearMax,
      });
    }

    // Reset search by to default (best_match)
    if (domManager.elements.searchBy) {
      domManager.elements.searchBy.value = "best_match";
      console.log("Search by reset to best_match");
    }

    // Reset quota to default (5 papers)
    if (domManager.elements.quota) {
      domManager.elements.quota.value = "5";
      console.log("Quota reset to 5");
    }

    console.log("Filters reset to defaults");
  } else {
    console.log("DOM Manager not found");
  }
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
  if (domManager.elements.yearMin && domManager.elements.yearMax) {
    domManager.updateSingleSlider("min");
    domManager.updateSingleSlider("max");
  } else {
    domManager.updateYearLabel();
  }

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
window.toggleProfileDropdown = toggleProfileDropdown;
window.logout = logout;
window.resetFilters = resetFilters;
window.performSearch = performSearch;

// Initialize the application
init();
