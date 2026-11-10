// Offline tests for HTML escaping in the workspace page's renderers.
//
// Run from Research_Assistant/:  node --test Test/js/
//
// Paper metadata (OpenAlex / the local corpus) and LLM summaries are untrusted
// text. Every renderer below writes to innerHTML, so each must escape that
// text. There is no DOM here: document is stubbed and the tests inspect the
// HTML string each renderer assigns to innerHTML.

import { test } from "node:test";
import assert from "node:assert/strict";

function stubElement() {
  return {
    style: {},
    dataset: {},
    children: [],
    innerHTML: "",
    appendChild(child) { this.children.push(child); },
    addEventListener() {},
    setAttribute() {},
    querySelectorAll() { return []; },
  };
}

globalThis.window = { appState: { binders: [] } };
globalThis.document = {
  cookie: "",
  querySelector: () => null,
  createElement: stubElement,
};

const JS = "../../Research_AI_Assistant/templates/static/js/";
const { DOMManager } = await import(JS + "core.js");
await import(JS + "paper.js");
await import(JS + "research.js");
await import(JS + "binders.js");

// The constructor wires up the real page; the renderers only need the prototype.
const dom = Object.create(DOMManager.prototype);

const IMG = "<img src=x onerror=alert(1)>";
const SCRIPT = "<script>alert(1)</script>";

function assertNoMarkup(html) {
  assert.doesNotMatch(html, /<img\s+src=x/i);
  assert.doesNotMatch(html, /<script/i);
}

// ---- markdownToHtml (LLM summaries) ---------------------------------------

test("markdownToHtml escapes HTML in summary text", () => {
  const html = dom.markdownToHtml(
    `Paper [1]: ${IMG}\nAuthors: ${SCRIPT}\nSummary: a <b>bold</b> claim\n\n- item ${IMG}`,
  );
  assertNoMarkup(html);
  assert.doesNotMatch(html, /<b>/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
});

test("markdownToHtml image syntax cannot add attributes to the <img>", () => {
  const html = dom.markdownToHtml(
    '![x" onerror="alert(1)](http://a.test/b.png" onload="alert(2))',
  );
  assert.doesNotMatch(html, /<img[^>]*\son(error|load)="/i);
});

test("markdownToHtml still renders markdown", () => {
  const html = dom.markdownToHtml("**bold** and `code` and [2]");
  assert.match(html, /<strong>bold<\/strong>/);
  assert.match(html, /<code>code<\/code>/);
  assert.match(html, /<span class="cite">\[2\]<\/span>/);
});

test("markdownToHtml escapes code blocks exactly once", () => {
  const html = dom.markdownToHtml("```\na < b && c\n```");
  assert.match(html, /<code>a &lt; b &amp;&amp; c<\/code>/);
});

test("markdownToHtml still renders blockquotes", () => {
  assert.match(dom.markdownToHtml("> quoted"), /<blockquote>quoted<\/blockquote>/);
});

test("markdownToHtml still builds paper cards with DOI links", () => {
  const html = dom.markdownToHtml(
    "Paper [1]: A Title\nAuthors: A. Smith\nDOI: 10.1234/abc\nSummary: It's fine.",
  );
  assert.match(html, /<h3 class="summary-card__title">A Title<\/h3>/);
  assert.match(html, /<a href="https:\/\/doi\.org\/10\.1234\/abc"/);
});

// ---- createPaperCard --------------------------------------------------------

test("createPaperCard escapes title, authors, abstract and year", () => {
  const card = dom.createPaperCard(
    {
      title: IMG,
      authors: [{ name: SCRIPT }],
      abstract: IMG,
      publication_year: IMG,
      doi: "10.1234/abc",
    },
    0,
  );
  assertNoMarkup(card.innerHTML);
  assert.match(card.innerHTML, /&lt;img src=x/);
});

test("createPaperCard escapes the title when there is no DOI", () => {
  assertNoMarkup(dom.createPaperCard({ title: IMG }, 0).innerHTML);
});

test("createPaperCard DOI cannot break out of the href", () => {
  const card = dom.createPaperCard(
    { title: "T", doi: '10.1234/x" onmouseover="alert(1)' },
    0,
  );
  assert.doesNotMatch(card.innerHTML, /"\s+onmouseover="/);
});

test("createPaperCard does not double-prefix a DOI that is already a URL", () => {
  const card = dom.createPaperCard(
    { title: "T", doi: "https://doi.org/10.1234/abc" },
    0,
  );
  assert.match(card.innerHTML, /href="https:\/\/doi\.org\/10\.1234\/abc"/);
});

// ---- renderReferences -------------------------------------------------------

function renderReferences(papers) {
  const list = stubElement();
  const self = Object.create(DOMManager.prototype);
  self.elements = { referencesPanel: stubElement(), referencesList: list };
  self.renderReferences(papers);
  return list.children.map((c) => c.innerHTML).join("");
}

test("renderReferences escapes the title, with and without a DOI", () => {
  const html = renderReferences([
    { title: IMG, doi: "10.1234/abc" },
    { title: SCRIPT },
  ]);
  assertNoMarkup(html);
});

test("renderReferences DOI cannot break out of the href", () => {
  const html = renderReferences([
    { title: "T", doi: 'https://doi.org/x" onmouseover="alert(1)' },
  ]);
  assert.doesNotMatch(html, /"\s+onmouseover="/);
});

test("renderReferences does not render a non-numeric citation count as HTML", () => {
  assertNoMarkup(renderReferences([{ title: "T", cited_by_count: IMG }]));
});

// ---- createBinderElement ----------------------------------------------------

test("createBinderElement escapes name, paper title and last message", () => {
  const card = dom.createBinderElement({
    id: "binder-1",
    name: IMG,
    color: "#123456",
    papers: [{ title: SCRIPT }],
    messages: [{ role: "assistant", content: IMG }],
  });
  assertNoMarkup(card.innerHTML);
  assert.match(card.innerHTML, /&lt;img src=x/);
});

test("createBinderElement colour cannot break out of the style attribute", () => {
  const card = dom.createBinderElement({
    id: "binder-1",
    name: "n",
    color: 'red" onmouseover="alert(1)',
    papers: [],
    messages: [],
  });
  assert.doesNotMatch(card.innerHTML, /"\s+onmouseover="/);
});
