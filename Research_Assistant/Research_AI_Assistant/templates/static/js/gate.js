// Enforces the Clerk sign-in gate and patches fetch for /api/ calls.
import { installFetchInterceptor, requireSignIn } from "./auth.js";
import { createLogger } from "./logger.js";

const log = createLogger("gate");
log.info(`page boot: ${location.pathname}`);
installFetchInterceptor();
requireSignIn().then((clerk) => {
  if (clerk) log.info("signed-in gate passed");
});
