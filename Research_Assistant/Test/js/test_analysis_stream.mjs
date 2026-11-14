// Offline tests for the analysis page's SSE stream parser.
//
// Run from Research_Assistant/:  node --test Test/js/
//
// fetch is stubbed with a response whose body streams the given SSE text, so
// requestPaperAnalysisStream runs its real parsing loop.

import { test } from "node:test";
import assert from "node:assert/strict";

const JS = "../../Research_AI_Assistant/templates/static/js/";
const { requestPaperAnalysisStream } = await import(JS + "analysis/analysis_api.js");

function stubFetch(sseText) {
  globalThis.fetch = async () => ({
    ok: true,
    body: new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(sseText));
        controller.close();
      },
    }),
  });
}

const sse = (event, data) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;

test("a reset event clears the tokens shown so far", async () => {
  stubFetch(
    sse("token", { t: '{"answer": "cut' }) +
    sse("reset", {}) +
    sse("token", { t: '{"answer": "ok"}' }),
  );

  // Mirrors how analysis.js accumulates streamed text.
  let shown = "";
  await requestPaperAnalysisStream({
    paperIds: ["W1"],
    question: "q",
    onToken(t) { shown += t; },
    onReset() { shown = ""; },
  });

  assert.equal(shown, '{"answer": "ok"}');
});
