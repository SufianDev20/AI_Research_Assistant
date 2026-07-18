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

DOMManager.prototype.updateSingleSlider = function(which) {
  const minVal = parseInt(this.elements.yearMin?.value || 1900);
  const maxVal = parseInt(this.elements.yearMax?.value || 2026);

  // Prevent crossing
  if (which === "min" && minVal > maxVal) {
    this.elements.yearMin.value = maxVal;
  }
  if (which === "max" && maxVal < minVal) {
    this.elements.yearMax.value = minVal;
  }

  const min = parseInt(this.elements.yearMin.value);
  const max = parseInt(this.elements.yearMax.value);
  const range = 2026 - 1900;
  const leftPct = ((min - 1900) / range) * 100;
  const rightPct = ((2026 - max) / range) * 100;

  // Update fill bar
  const fill = this.elements.sliderFill;
  if (fill) {
    fill.style.left = leftPct + "%";
    fill.style.right = rightPct + "%";
  }

  // Update labels
  if (this.elements.minYearDisplay)
    this.elements.minYearDisplay.textContent = min;
  if (this.elements.maxYearDisplay)
    this.elements.maxYearDisplay.textContent = max;

  // Update tooltips
  const tooltipMin = this.elements.sliderTooltipMin;
  const tooltipMax = this.elements.sliderTooltipMax;
  if (tooltipMin) {
    tooltipMin.textContent = min;
    tooltipMin.style.left = leftPct + "%";
  }
  if (tooltipMax) {
    tooltipMax.textContent = max;
    tooltipMax.style.left = 100 - rightPct + "%";
  }
};

DOMManager.prototype.updateSingleTooltipPosition = function(type) {
  const tooltip =
    type === "min"
      ? this.elements.sliderTooltipMin
      : this.elements.sliderTooltipMax;
  const slider =
    type === "min" ? this.elements.yearMin : this.elements.yearMax;

  if (!tooltip || !slider) return;

  const percent = (slider.value - slider.min) / (slider.max - slider.min);
  const offset = percent * slider.offsetWidth;

  tooltip.style.left = offset + "px";
  tooltip.textContent = slider.value;
};

// Shows .show class which sets opacity: 1 in CSS, fading in the tooltip. Immediately repositions it above the current thumb position before user starts dragging.
DOMManager.prototype.showTooltip = function(type) {
  const tooltip =
    type === "min"
      ? this.elements.sliderTooltipMin
      : this.elements.sliderTooltipMax;
  if (tooltip) {
    tooltip.classList.add("show");
    this.updateSingleTooltipPosition(type);
  }
};

// Removes .show class, setting opacity back to 0, fading out the tooltip when dragging stops on year slider.
DOMManager.prototype.hideTooltip = function(type) {
  const tooltip =
    type === "min"
      ? this.elements.sliderTooltipMin
      : this.elements.sliderTooltipMax;
  if (tooltip) {
    tooltip.classList.remove("show");
  }
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
  if (!response.ok)
    throw new Error(`Backend search error ${response.status}`);

  const data = await response.json();
  return data; // Return full data object including pagination info
};
