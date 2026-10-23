// Refresh behavior for the performance dashboard (/performance/).
// All figures are rendered server-side, so refreshing is a page reload --
// the same two triggers the dashboard has always had: the Refresh Data
// button and an automatic reload every 30 seconds.
(function () {
  "use strict";
  var AUTO_REFRESH_MS = 30000;
  var btn = document.getElementById("pfRefresh");

  function refresh() {
    if (btn) {
      btn.setAttribute("aria-busy", "true");
      btn.disabled = true;
    }
    window.location.reload();
  }

  if (btn) btn.addEventListener("click", refresh);
  setTimeout(refresh, AUTO_REFRESH_MS);
})();
