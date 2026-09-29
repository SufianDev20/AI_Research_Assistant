// Clerk sign-in gate + token helper.
import { createLogger } from "./logger.js";

const log = createLogger("auth");
let clerkPromise = null;

function readPublishableKey() {
  const meta = document.querySelector('meta[name="clerk-publishable-key"]');
  return meta ? meta.content : "";
}

// pk_test_<base64(frontend-api-host + "$")> -> frontend API host
function frontendApiHost(key) {
  try {
    return atob(key.split("_").slice(2).join("_")).replace(/\$$/, "");
  } catch (err) {
    return "";
  }
}

export function loadClerk() {
  if (clerkPromise) return clerkPromise;
  clerkPromise = new Promise((resolve, reject) => {
    const key = readPublishableKey();
    if (!key) {
      reject(new Error("Sign-in is not configured (missing Clerk publishable key)."));
      return;
    }
    const host = frontendApiHost(key);
    if (!host) {
      reject(new Error("Sign-in is misconfigured (invalid Clerk publishable key)."));
      return;
    }
    log.info("loading Clerk SDK");
    const script = document.createElement("script");
    script.async = true;
    script.crossOrigin = "anonymous";
    script.setAttribute("data-clerk-publishable-key", key);
    script.src = `https://${host}/npm/@clerk/clerk-js@5/dist/clerk.browser.js`;
    script.onload = async () => {
      try {
        await window.Clerk.load();
        log.info("Clerk loaded; signed in:", Boolean(window.Clerk.user));
        resolve(window.Clerk);
      } catch (err) {
        log.error("Clerk failed to initialise:", err);
        reject(new Error("Could not start sign-in. Check your connection and Clerk settings."));
      }
    };
    script.onerror = () => {
      log.error("Clerk SDK script failed to load");
      reject(new Error("Could not load the sign-in service. Check your connection and try again."));
    };
    document.head.appendChild(script);
  });
  return clerkPromise;
}

/** Redirects to /sign-in/ when signed out. Resolves with Clerk when signed in. */
export async function requireSignIn() {
  // No publishable key: fail open; the API still enforces auth server-side.
  if (!readPublishableKey()) {
    log.error(
      "CLERK_PUBLISHABLE_KEY is not set — sign-in gate disabled. " +
        "Add it to Research_Assistant/.env to turn sign-in on."
    );
    return null;
  }
  try {
    const clerk = await loadClerk();
    if (!clerk.user) {
      log.info("not signed in; redirecting to /sign-in/");
      window.location.replace("/sign-in/");
      return null;
    }
    return clerk;
  } catch (err) {
    log.error("sign-in gate failed:", err);
    window.location.replace("/sign-in/?error=config");
    return null;
  }
}

/** Authorization header for API calls ({} when signed out). Never logs the token. */
export async function getAuthHeaders() {
  try {
    const clerk = await loadClerk();
    const token = clerk.session ? await clerk.session.getToken() : null;
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch (err) {
    log.warn("could not get auth token:", err);
    return {};
  }
}

export async function signOut() {
  const clerk = await loadClerk();
  await clerk.signOut();
  window.location.replace("/sign-in/");
}

// Wraps fetch: attaches the Clerk token to /api/ calls and logs them.
export function installFetchInterceptor() {
  if (window.__scholaraFetchPatched) return;
  window.__scholaraFetchPatched = true;
  const httpLog = createLogger("http");
  const originalFetch = window.fetch.bind(window);

  window.fetch = async (input, init = {}) => {
    const rawUrl = typeof input === "string" ? input : input.url;
    if (!rawUrl || !rawUrl.startsWith("/api/")) return originalFetch(input, init);

    const method = (init.method || (typeof input !== "string" && input.method) || "GET").toUpperCase();
    const headers = new Headers(init.headers || {});
    if (!headers.has("Authorization")) {
      const authHeaders = await getAuthHeaders();
      Object.entries(authHeaders).forEach(([k, v]) => headers.set(k, v));
    }
    const started = performance.now();
    httpLog.info(`${method} ${rawUrl} started`);
    try {
      const response = await originalFetch(input, { ...init, headers });
      const ms = Math.round(performance.now() - started);
      if (response.ok) {
        httpLog.info(`${method} ${rawUrl} -> ${response.status} (${ms} ms)`);
      } else {
        httpLog.warn(`${method} ${rawUrl} -> ${response.status} ${response.statusText} (${ms} ms)`);
        if (response.status === 401) {
          httpLog.warn("session expired or missing; redirecting to sign-in");
          window.location.replace("/sign-in/");
        }
      }
      return response;
    } catch (err) {
      if (err && err.name === "AbortError") {
        httpLog.info(`${method} ${rawUrl} aborted`);
      } else {
        httpLog.error(`${method} ${rawUrl} failed before a response arrived:`, err);
      }
      throw err;
    }
  };
}
