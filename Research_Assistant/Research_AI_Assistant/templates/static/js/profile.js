// Populates the workspace nav's account menu with the real signed-in
// Clerk user (name, email, avatar) and wires real actions (manage
// account, sign out). Reuses the same Clerk instance gate.js already
// starts loading via auth.js's cached loadClerk() promise -- this never
// triggers a second SDK load.
//
// CLERK_PUBLISHABLE_KEY can be unset in a given deployment (auth.js
// "fails open" in that case: no redirect, no Clerk instance). This
// module has to render something reasonable either way, without ever
// inventing a name, email, or a settings link the app doesn't have.
import { loadClerk, signOut } from "./auth.js";
import { createLogger } from "./logger.js";

const log = createLogger("profile");

function initials(label) {
  if (!label) return "S";
  const parts = label.trim().split(/\s+/).filter(Boolean);
  const first = parts[0]?.[0] || "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase() || "S";
}

function els() {
  return {
    trigger: document.getElementById("profileTrigger"),
    avatar: document.getElementById("profileAvatar"),
    name: document.getElementById("profileName"),
    role: document.getElementById("profileRole"),
    menu: document.getElementById("profileMenu"),
    manageItem: document.getElementById("profileManage"),
    signOutItem: document.getElementById("profileSignOut"),
    signInItem: document.getElementById("profileSignIn"),
  };
}

function renderSignedIn(user) {
  const { avatar, name, role, manageItem, signOutItem, signInItem } = els();
  const displayName = user.fullName || user.firstName || "Researcher";
  const email = user.primaryEmailAddress?.emailAddress || "";

  if (name) name.textContent = displayName;
  if (role) role.textContent = email;

  if (avatar) {
    if (user.hasImage && user.imageUrl) {
      avatar.innerHTML = "";
      avatar.style.backgroundImage = `url("${user.imageUrl}")`;
      avatar.classList.add("profile-avatar--photo");
    } else {
      avatar.textContent = initials(displayName);
    }
  }

  if (manageItem) manageItem.hidden = false;
  if (signOutItem) signOutItem.hidden = false;
  if (signInItem) signInItem.hidden = true;
}

function renderSignedOut() {
  const { avatar, name, role, manageItem, signOutItem, signInItem } = els();
  if (avatar) avatar.textContent = "S";
  if (name) name.textContent = "Guest researcher";
  if (role) role.textContent = "Not signed in";
  if (manageItem) manageItem.hidden = true;
  if (signOutItem) signOutItem.hidden = true;
  if (signInItem) signInItem.hidden = false;
}

function wireMenuToggle() {
  const { trigger, menu } = els();
  if (!trigger || !menu) return;

  function closeMenu() {
    menu.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
  }
  function openMenu() {
    menu.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    const firstItem = menu.querySelector('[role="menuitem"]:not([hidden])');
    firstItem?.focus();
  }

  trigger.addEventListener("click", () => {
    if (menu.hidden) openMenu();
    else closeMenu();
  });

  document.addEventListener("click", (e) => {
    if (!menu.hidden && !e.target.closest("#profileMenu") && !e.target.closest("#profileTrigger")) {
      closeMenu();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !menu.hidden) {
      closeMenu();
      trigger.focus();
    }
  });

  window.__scholaraCloseProfileMenu = closeMenu;
}

async function wireActions() {
  const { manageItem, signOutItem } = els();

  manageItem?.addEventListener("click", async () => {
    window.__scholaraCloseProfileMenu?.();
    try {
      const clerk = await loadClerk();
      clerk.openUserProfile();
    } catch (err) {
      log.error("could not open account management:", err);
    }
  });

  signOutItem?.addEventListener("click", async () => {
    window.__scholaraCloseProfileMenu?.();
    try {
      await signOut();
    } catch (err) {
      log.error("sign out failed:", err);
      window.location.replace("/sign-in/");
    }
  });
}

wireMenuToggle();
wireActions();

loadClerk()
  .then((clerk) => {
    if (clerk.user) {
      renderSignedIn(clerk.user);
    } else {
      renderSignedOut();
    }
    clerk.addListener(({ user }) => {
      if (user) renderSignedIn(user);
      else renderSignedOut();
    });
  })
  .catch((err) => {
    log.info("account menu running without Clerk:", err.message);
    renderSignedOut();
  });
