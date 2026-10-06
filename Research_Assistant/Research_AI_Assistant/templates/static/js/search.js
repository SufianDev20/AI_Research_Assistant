import { DOMManager } from './core.js';

// Extend DOMManager prototype with search-related methods
DOMManager.prototype.updateYearLabel = function() {
  if (!this.elements.yearFilter) return;

  var year = parseInt(this.elements.yearFilter.value);
  if (this.elements.yearValue) {
    this.elements.yearValue.textContent = year;
  }
  if (this.elements.sliderTooltip) {
    this.elements.sliderTooltip.textContent = year;
  }

  this.updateTooltipPosition();
};

const YEAR_MIN = 1900;
const YEAR_MAX = 2026;

// Validates and clamps the two year inputs on blur/change: each value is
// clamped to [YEAR_MIN, YEAR_MAX], a non-numeric entry falls back to its
// own bound, and an inverted range (from > to) swaps the two rather than
// silently discarding one. A brief, dismissable message explains what
// happened when a correction occurs; the request always uses the
// corrected values, never the raw invalid ones.
DOMManager.prototype.validateYearRange = function() {
  const minEl = this.elements.yearMin;
  const maxEl = this.elements.yearMax;
  if (!minEl || !maxEl) return;

  const clamp = (raw, fallback) => {
    const n = parseInt(raw, 10);
    if (Number.isNaN(n)) return fallback;
    return Math.min(YEAR_MAX, Math.max(YEAR_MIN, n));
  };

  let min = clamp(minEl.value, YEAR_MIN);
  let max = clamp(maxEl.value, YEAR_MAX);
  let corrected = min !== parseInt(minEl.value, 10) || max !== parseInt(maxEl.value, 10);

  if (min > max) {
    [min, max] = [max, min];
    corrected = true;
  }

  minEl.value = min;
  maxEl.value = max;

  // Only ever set here when a correction just happened. Deliberately not
  // cleared on a "nothing to fix" call -- blurring the *other*, already-
  // valid field re-runs this too, and that must not wipe a message the
  // user hasn't had a chance to read yet. Clearing it is handled by the
  // "start typing again" listener in setupAdvancedOptionsToggle.
  const errorEl = this.elements.yearError;
  if (errorEl && corrected) {
    errorEl.textContent = `Adjusted to a valid range: ${min}–${max}.`;
    errorEl.hidden = false;
  }
};

// ---------------------------------------------------------------------
// Advanced options panel: opens/closes attached directly below the
// search input. [hidden] toggling is the source of truth for whether
// the panel exists in the a11y tree and can be focused/submitted --
// that part always works even with zero CSS. The .ws-panel--open class
// on top of it drives two coordinated effects: .ws-tab__fold's 3D
// rotation (each sheet's paper+controls folding as one rigid unit) and
// the panel's own max-height (the layout space that pushes the binders
// section down/up). Both are purely decorative and safe to skip
// (prefers-reduced-motion, or no CSS transition support at all).
//
// max-height's target is measured from the panel's real content height
// (wsTabs.scrollHeight) rather than a guessed constant -- see the CSS
// comment on .ws-advanced-panel for why a fixed cap mismatches the
// declared transition duration against when the motion actually stops.
//
// Interrupt safety: both open and close read the panel's CURRENT
// rendered height via getBoundingClientRect() before retargeting, so a
// toggle fired mid-transition reverses smoothly from wherever it
// actually is instead of jumping. A single tracked cleanup callback
// (closeCleanup) means a rapid re-open cancels any pending close
// transitionend listener/timeout instead of leaving it to fire later
// and incorrectly re-hide an now-open panel.
// ---------------------------------------------------------------------
DOMManager.prototype.setupAdvancedOptionsToggle = function() {
  const toggle = this.elements.advancedToggle;
  const panel = this.elements.advancedPanel;
  const tabs = this.elements.filtersContainer;
  if (!toggle || !panel) return;

  const prefersReducedMotion = () =>
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let closeCleanup = null;
  const cancelPendingClose = () => {
    if (closeCleanup) {
      closeCleanup();
      closeCleanup = null;
    }
  };

  // openPanel defers adding .ws-panel--open to the next animation frame
  // (see comment inside openPanel). If closePanel() runs before that frame
  // -- a rapid open-then-close -- the stale callback would still fire and
  // re-open a panel the user just asked to close. Tracked and cancelled
  // the same way cancelPendingClose() guards the reverse case.
  let openRaf = null;
  const cancelPendingOpen = () => {
    if (openRaf !== null) {
      cancelAnimationFrame(openRaf);
      openRaf = null;
    }
  };

  // Locks in the panel's CURRENT rendered height as the transition's
  // "from" value (reading getBoundingClientRect, not the possibly-stale
  // inline style, so this is correct whether starting from a true 0,
  // mid-opening, or mid-closing), forces layout so the browser registers
  // it, then schedules the real target for the next frame so a
  // transition actually plays instead of jumping straight there.
  const retargetHeight = (targetPx) => {
    const current = panel.getBoundingClientRect().height;
    panel.style.maxHeight = current + "px";
    void panel.offsetHeight;
    requestAnimationFrame(() => {
      panel.style.maxHeight = targetPx;
    });
  };

  const openPanel = () => {
    cancelPendingClose();
    cancelPendingOpen();
    panel.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
    if (prefersReducedMotion()) {
      panel.classList.add("ws-panel--open");
      panel.style.maxHeight = "none";
      return;
    }
    // Force the browser to commit a render of the CLOSED state (every
    // .ws-tab__fold still at its default rotateX(-90deg)) now that the
    // panel is unhidden, THEN defer adding .ws-panel--open to the next
    // animation frame. A forced reflow alone isn't enough here: this is
    // the same task that just flipped the panel from display:none to
    // visible, and confirmed via transitionrun/transitionstart listeners
    // on a real click (not screenshot timing, which is too slow relative
    // to a 400ms transition to prove anything either way) -- max-height
    // fired transitionrun/transitionend normally, but .ws-tab__fold's
    // transform never fired transitionrun at all when the class was
    // added synchronously in the same task as offsetHeight, even with
    // the reflow. Deferring to the next frame (matching what
    // retargetHeight already does for max-height below) gives the browser
    // an actual completed frame boundary to render the closed state
    // before the open state is applied, and the transform transition
    // fires correctly.
    void panel.offsetHeight;
    // Double rAF, not single: a single requestAnimationFrame callback
    // still runs BEFORE that frame's own paint, so it guarantees a
    // completed STYLE/LAYOUT pass but not a completed PAINT of the
    // closed state -- on a freshly-unhidden element, the first frame
    // after unhiding is exactly when that distinction can matter. The
    // second rAF only runs after the browser has painted the frame
    // scheduled by the first one, which is the stronger guarantee this
    // needs. This did not reproduce as a failure in this environment
    // (confirmed working via transitionrun/transitionend events and via
    // live getAnimations() progress sampling at a slowed duration), but
    // it's a real, well-documented gap in the single-rAF version of this
    // pattern and costs one extra frame (~16ms) to close.
    openRaf = requestAnimationFrame(() => {
      openRaf = requestAnimationFrame(() => {
        openRaf = null;
        panel.classList.add("ws-panel--open");
        const target = tabs ? tabs.scrollHeight + "px" : "none";
        retargetHeight(target);
      });
    });
  };

  const closePanel = () => {
    toggle.setAttribute("aria-expanded", "false");
    // Focus is about to fall into a soon-to-be-hidden subtree -- move it
    // back to the control that owns it rather than letting it drop to
    // <body>.
    if (panel.contains(document.activeElement)) {
      toggle.focus();
    }
    cancelPendingOpen();
    if (prefersReducedMotion()) {
      panel.classList.remove("ws-panel--open");
      panel.style.maxHeight = "0px";
      panel.hidden = true;
      return;
    }
    cancelPendingClose();
    panel.classList.remove("ws-panel--open");
    retargetHeight("0px");
    const onEnd = (e) => {
      if (e.target !== panel || e.propertyName !== "max-height") return;
      cleanup();
    };
    const cleanup = () => {
      panel.removeEventListener("transitionend", onEnd);
      clearTimeout(safety);
      panel.hidden = true;
      closeCleanup = null;
    };
    panel.addEventListener("transitionend", onEnd);
    // Safety net: if no transition fires (e.g. the property being
    // watched never changed, or a browser quirk swallows the event),
    // still end up closed instead of stuck open forever. Read the
    // REAL declared max-height duration from computed style rather than
    // hardcoding 400ms -- a diagnostic or future retune that changes the
    // CSS duration (e.g. the temporary 2000ms slow-motion override in
    // styles.css) would otherwise have this safety timeout fire well
    // before the slowed transition visually finishes, force-hiding the
    // panel mid-animation and making the motion impossible to inspect.
    const panelDurationMs = parseFloat(getComputedStyle(panel).transitionDuration || "0.4") * 1000;
    const safety = setTimeout(cleanup, panelDurationMs + 150);
    closeCleanup = cleanup;
  };

  toggle.addEventListener("click", () => {
    if (panel.hidden) openPanel();
    else closePanel();
  });

  this._closeAdvancedPanel = closePanel;
};

// Reset animation: a brief "remove the current sheet, reveal a fresh
// one" pass over the filters, purely decorative on top of the values
// being reset synchronously below regardless of whether this runs.
DOMManager.prototype.playResetTransition = function() {
  const container = this.elements.filtersContainer;
  if (!container) return;
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return; // values already reset synchronously by the caller
  }
  container.classList.remove("ws-filters--resetting");
  // Re-trigger the animation even if it was already mid-play.
  void container.offsetWidth;
  container.classList.add("ws-filters--resetting");
  const onEnd = (e) => {
    if (e.target !== container) return;
    container.classList.remove("ws-filters--resetting");
    container.removeEventListener("animationend", onEnd);
  };
  container.addEventListener("animationend", onEnd);
  setTimeout(() => container.classList.remove("ws-filters--resetting"), 500);
};

DOMManager.prototype.updateTooltipPosition = function() {
  if (!this.elements.yearFilter || !this.elements.sliderTooltip) return;

  var slider = this.elements.yearFilter;
  var tooltip = this.elements.sliderTooltip;
  var percent = (slider.value - slider.min) / (slider.max - slider.min); // Calculates how far along the slider's thumb is as a value between 0 and 1. For example if value is 2008, min is 1990, max is 2026: (2008 - 1990) / (2026 - 1990) = 18/36 = 0.5, meaning that thumb is at 50%. Converts into pixel values for slider width to be visible.
  var offset = percent * slider.offsetWidth;

  tooltip.style.left = offset + "px";
};

DOMManager.prototype.retrieveFromBackend = async function(
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

  // Year range params
  let yearParams = "";
  if (minYear !== null && minYear !== undefined) {
    yearParams += "&min_year=" + minYear;
  }
  if (maxYear !== null && maxYear !== undefined) {
    yearParams += "&max_year=" + maxYear;
  }

  var url =
    "/api/search/?q=" +
    encodeURIComponent(query) +
    "&mode=" +
    sortPref +
    "&per_page=" +
    Math.min(maxPapers, 50) +
    yearParams +
    cursorParam +
    seedParam;

  var response = await fetch(url);
  if (!response.ok) {
    // Distinguish "the search service itself failed" (auth/config/upstream
    // issue — nothing to do with the query) from a query that legitimately
    // matched zero papers, which is a normal 200 response handled by the caller.
    let detail = null;
    try {
      const errBody = await response.json();
      detail = errBody.error || errBody.detail || null;
    } catch (_parseErr) {
      // Non-JSON error body; fall back to a status-based message below.
    }
    const err = new Error(
      detail
        ? `Search service unavailable: ${detail}`
        : `Search service unavailable (HTTP ${response.status})`,
    );
    err.isServiceError = true;
    err.status = response.status;
    throw err;
  }

  const data = await response.json();
  return data; // Return full data object including pagination info
};
