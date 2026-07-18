import { DOMManager } from './core.js';

// Extend DOMManager prototype with modal-related methods (backwards compatibility)
DOMManager.prototype.generateAssistantResponse = function(binder, container) {
  // This method is kept for backwards compatibility with modal system
  if (window.appState.isThinking || !binder) return;

  const sendBtn = this.elements.modalSendBtn;
  window.appState.isThinking = true;
  if (sendBtn) sendBtn.disabled = true;

  const assistantDiv = this.addMessage("", false, container);

  // Similar implementation to generateResearchResponse but for modal
  async function generateResponse() {
    try {
      const maxYear = domManager.elements.yearFilter?.value || "2026";
      const sortPref = domManager.elements.searchBy?.value || "most-cited";
      const maxPapers = parseInt(domManager.elements.quota?.value || "5");

      const lastUserQuery =
        binder.messages[binder.messages.length - 1].content;
      const data = await domManager.retrieveFromBackend(
        lastUserQuery,
        null, // minYear - not needed for single filter
        maxYear,
        sortPref,
        maxPapers,
      );
      const papers=data.papers || [];
      binder.papers = papers;

      if (papers.length > 0) {
        domManager.renderPaperCards(papers, container);
      }

      const response = await fetch("/api/summarise/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": window.csrfToken,
        },
        body: JSON.stringify({
          query: lastUserQuery,
          papers: papers,
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || `Summarise error ${response.status}`);
      }

      const responseData = await response.json();
      const summary = responseData.summary || "No summary returned.";

      assistantDiv.innerHTML = domManager.markdownToHtml(summary);
      binder.messages.push({ role: "assistant", content: summary });

      if (binder.messages.length === 2) {
        domManager.generateTitle(binder);
      }
    } catch (err) {
      assistantDiv.innerHTML = `Error: ${err.message}`;
    } finally {
      window.appState.isThinking = false;
      if (sendBtn) sendBtn.disabled = false;
      if (domManager.elements.modalInput) {
        domManager.modalInput.focus();
      }
    }
  }

  generateResponse();
};
