// Shared by both the workspace bundle (globals.js entry point) and the
// standalone analysis page bundle (analysis/analysis.js) — the one JS
// module both pages import, since otherwise each re-implements the same
// CSRF-token lookup / HTML-escaping / DOI-URL logic independently.

export function getCsrfToken() {
  const input = document.querySelector('[name=csrfmiddlewaretoken]');
  if (input?.value) return input.value;
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export function escapeHtml(value) {
  if (value == null) return "";
  return String(value).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

// A paper's DOI as a doi.org URL. OpenAlex returns doi as a full
// https://doi.org/... URL; only bare DOIs need the resolver prefix.
export function doiUrl(doi) {
  if (!doi) return "";
  const value = String(doi);
  return /^https?:\/\//i.test(value) ? value : `https://doi.org/${value}`;
}
