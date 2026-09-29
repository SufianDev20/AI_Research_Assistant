import { loadClerk } from "./auth.js";
import { createLogger } from "./logger.js";

const log = createLogger("sign-in");
const errorBox = document.getElementById("siError");

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

log.info("sign-in page starting");
if (new URLSearchParams(location.search).get("error") === "config") {
  showError("We couldn't start sign-in. Please try again; if it keeps happening, the site is not configured yet.");
}

loadClerk()
  .then((clerk) => {
    if (clerk.user) {
      log.info("already signed in; going to workspace");
      window.location.replace("/workspace/");
      return;
    }
    log.info("mounting sign-in component");
    clerk.mountSignIn(document.getElementById("clerk-sign-in"), {
      forceRedirectUrl: "/workspace/",
      signUpForceRedirectUrl: "/workspace/",
    });
  })
  .catch((err) => {
    log.error("sign-in failed to start:", err);
    showError(err.message);
  });
