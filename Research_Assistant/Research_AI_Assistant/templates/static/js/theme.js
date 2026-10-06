// Light/dark theme toggle for the workspace.
// The inline flash-prevention script at body-open already applies the saved
// preference to document.body.dataset.theme before any paint. This module
// wires the #themeToggle button, persists changes to localStorage, and
// dispatches "scholara-theme-change" so workspace-bg.js can repaint the
// canvas without restarting the animation loop.
(function () {
  "use strict";
  var btn = document.getElementById("themeToggle");
  if (!btn) return;

  function dark() { return document.body.dataset.theme === "dark"; }

  function apply(isDark, persist) {
    document.body.dataset.theme = isDark ? "dark" : "light";
    btn.setAttribute("aria-label", isDark ? "Switch to light mode" : "Switch to dark mode");
    btn.title = isDark ? "Switch to light mode" : "Switch to dark mode";
    if (persist) {
      try { localStorage.setItem("scholara-theme", isDark ? "dark" : "light"); } catch (_) {}
    }
    window.dispatchEvent(new CustomEvent("scholara-theme-change", { detail: { dark: isDark } }));
  }

  // Sync button label with the theme the inline script already applied
  btn.setAttribute("aria-label", dark() ? "Switch to light mode" : "Switch to dark mode");
  btn.title = dark() ? "Switch to light mode" : "Switch to dark mode";

  btn.addEventListener("click", function () { apply(!dark(), true); });
})();
