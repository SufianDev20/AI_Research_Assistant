import { DOMManager } from './core.js';

// Extend DOMManager prototype with binder-related methods
DOMManager.prototype.renderBinders = function() {
  if (!this.elements.bindersContainer) return;

  this.elements.bindersContainer.innerHTML = "";

  if (this.elements.binderCount) {
    this.elements.binderCount.textContent =
      window.appState.binders.length + " active";
  }

  window.appState.binders.forEach(
    function (binder) {
      var binderElement = this.createBinderElement(binder);
      this.elements.bindersContainer.appendChild(binderElement);
    }.bind(this),
  );
};

DOMManager.prototype.createBinderElement = function(binder) {
  var lastMessage =
    binder.messages && binder.messages.length > 0
      ? binder.messages[binder.messages.length - 1].content
      : "No messages yet";
  var paperCount = binder.papers ? binder.papers.length : 0;
  var messageCount = binder.messages ? binder.messages.length : 0;
  var firstPaper =
    binder.papers && binder.papers.length > 0
      ? binder.papers[0].title
      : null;

  var card = document.createElement("div");
  card.className = "binder-card";
  var self = this;
  card.onclick = function () {
    return self.openBinder(binder.id);
  };

  // Build HTML string with compatible syntax
  var html =
    '<div style="background: ' +
    binder.color +
    '" class="binder-color-bar"></div>' +
    '<div class="binder-content">' +
    '<div class="binder-header">' +
    '<div onclick="event.stopImmediatePropagation(); editBinderColor(\'' +
    binder.id +
    '\');" ' +
    'style="background: ' +
    binder.color +
    '" class="binder-color-dot"></div>' +
    '<div contenteditable="true" spellcheck="false" ' +
    'onblur="saveBinderName(\'' +
    binder.id +
    '\', this.innerText)" ' +
    'class="binder-title">' +
    binder.name +
    "</div>" +
    '<button onclick="event.stopImmediatePropagation(); deleteBinder(\'' +
    binder.id +
    '\');" ' +
    'class="binder-delete-btn" title="Delete binder">' +
    '<i class="fa-solid fa-trash"></i>' +
    "</button>" +
    "</div>";

  // Add paper preview if exists
  if (firstPaper) {
    html +=
      '<div class="binder-paper-preview">' +
      '<div class="binder-paper-label">Latest Paper</div>' +
      '<div class="binder-paper-title">' +
      (firstPaper.substring(0, 80) +
        (firstPaper.length > 80 ? "..." : "")) +
      "</div>" +
      "</div>";
  }

  // Add stats
  html +=
    '<div class="binder-stats">' +
    '<div class="binder-stats-left">' +
    '<div class="binder-stat">' +
    '<i class="fa-solid fa-comment-dots"></i>' +
    "<span>" +
    messageCount +
    " messages</span>" +
    "</div>";

  if (paperCount > 0) {
    html +=
      '<div class="binder-stat">' +
      '<i class="fa-solid fa-file-alt"></i>' +
      "<span>" +
      paperCount +
      " papers</span>" +
      "</div>";
  }

  html += "</div>" + '<div class="binder-status">Live</div>' + "</div>";

  // Add last message if exists
  if (lastMessage && lastMessage !== "No messages yet") {
    html +=
      '<div class="binder-last-message">' +
      '<div class="binder-last-message-text">' +
      '"' +
      (lastMessage.substring(0, 60) +
        (lastMessage.length > 60 ? "..." : "")) +
      '"' +
      "</div>" +
      "</div>";
  }

  html += "</div>";
  card.innerHTML = html;

  return card;
};

DOMManager.prototype.deleteBinder = function(binderId) {
  const binder = window.appState.binders.find((b) => b.id === binderId);
  if (!binder) {
    console.warn("Binder not found:", binderId);
    return;
  }

  // Prevent deletion if binder is currently open in research view
  if (
    window.appState.currentResearchBinder &&
    window.appState.currentResearchBinder.id === binderId
  ) {
    alert(
      "Cannot delete binder that is currently open. Please close it first.",
    );
    return;
  }

  const messageCount = binder.messages ? binder.messages.length : 0;
  const paperCount = binder.papers ? binder.papers.length : 0;
  const confirmMessage = `Delete binder "${binder.name}"?\n\nThis will remove:\n• ${messageCount} message(s)\n• ${paperCount} paper(s)\n\nThis action cannot be undone.`;

  if (!confirm(confirmMessage)) return;

  console.log("Deleting binder:", binderId, binder.name);

  // Add removing animation
  const binderElement = document
    .querySelector(`[onclick*="${binderId}"]`)
    ?.closest(".binder-card");
  if (binderElement) {
    binderElement.style.transition = "all 0.3s ease";
    binderElement.style.opacity = "0";
    binderElement.style.transform = "scale(0.9)";

    setTimeout(() => {
      window.appState.binders = window.appState.binders.filter((b) => b.id !== binderId);
      this.renderBinders();
      console.log("Binder deleted successfully:", binderId);
    }, 300);
  } else {
    // Fallback if element not found
    window.appState.binders = window.appState.binders.filter((b) => b.id !== binderId);
    this.renderBinders();
    console.log("Binder deleted successfully:", binderId);
  }
};

DOMManager.prototype.createNewBinder = function() {
  const binder = {
    id: "binder-" + Date.now(),
    name: "New Research Binder",
    color: "#" + Math.floor(Math.random() * 16777215).toString(16),
    messages: [],
    papers: [],
  };
  window.appState.binders.unshift(binder);
  this.renderBinders();
  this.openBinder(binder.id);
};

// Opens Binder that is after saving
DOMManager.prototype.openBinder = function(id) {
  var binder = window.appState.binders.find(function (b) {
    return b.id === id;
  });
  if (!binder) return;

  // Hide hero and binders
  if (this.elements.heroSection)
    this.elements.heroSection.style.display = "none";
  if (this.elements.bindersSection)
    this.elements.bindersSection.style.display = "none";

  // Show research view
  if (this.elements.researchView) {
    this.elements.researchView.classList.add("show");
  }

  // Set query
  var firstUserMessage = binder.messages.find(function (m) {
    return m.role === "user";
  });
  if (this.elements.researchQuery) {
    this.elements.researchQuery.textContent = firstUserMessage
      ? firstUserMessage.content
      : binder.name;
  }

  // Hide save button for existing binders
  if (this.elements.saveToBinderBtn) {
    this.elements.saveToBinderBtn.style.display = "none";
  }

  // Clear and populate chat
  if (this.elements.researchChatContainer) {
    this.elements.researchChatContainer.innerHTML = "";
    // Clears container then replays full message history. addMessage handles both user and assistant messages. For assistant messages, thinking indicator placeholder is immediately replaced with actual content via markdownToHtml. opacity: "1" is set explicitly because new assistant messages animate in, but restored messages should appear instantly without animation.
    binder.messages.forEach(
      function (msg) {
        var div = this.addMessage(
          msg.content,
          msg.role === "user",
          this.elements.researchChatContainer,
        );
        if (msg.role === "assistant") {
          div.innerHTML = this.markdownToHtml(msg.content);
          div.style.opacity = "1";
        }
      }.bind(this),
    );

    // Papers are shown in the right-side references panel only
  }
  this.renderReferences(binder.papers || []);

  window.appState.isResearchView = true;
  window.appState.currentResearchBinder = binder; // Brings the temporary saved binder into the frontend based on previous query
};

DOMManager.prototype.saveBinderName = function(binderId, newName) {
  const binder = window.appState.binders.find((b) => b.id === binderId);
  if (binder && newName.trim() !== "") {
    binder.name = newName.trim();
    this.renderBinders();
  }
};

DOMManager.prototype.editBinderColor = function(binderId) {
  event.stopImmediatePropagation();
  const binder = window.appState.binders.find((b) => b.id === binderId);
  if (!binder) return;

  const colorPicker = document.createElement("input");
  colorPicker.type = "color";
  colorPicker.value = binder.color;
  colorPicker.style.position = "absolute";
  colorPicker.style.opacity = "0";
  document.body.appendChild(colorPicker);

  colorPicker.onchange = function () {
    binder.color = this.value;
    domManager.renderBinders();
    document.body.removeChild(colorPicker);
  };

  colorPicker.click();
};
