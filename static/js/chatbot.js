// AI College Assistant floating chat widget
(function () {
  "use strict";

  function qs(id) {
    return document.getElementById(id);
  }

  function createBubble(text, role, metaText) {
    var bubble = document.createElement("div");
    bubble.className = "ai-chat-bubble " + (role === "user" ? "user" : "bot");

    var inner = document.createElement("div");
    inner.className = "ai-chat-bubble-inner";

    var body = document.createElement("div");
    body.className = "ai-chat-bubble-text";
    body.textContent = text;

    var meta = document.createElement("div");
    meta.className = "ai-chat-meta";
    meta.textContent = metaText || (role === "user" ? "You" : "Assistant");

    inner.appendChild(body);
    inner.appendChild(meta);
    bubble.appendChild(inner);
    return bubble;
  }

  function scrollToBottom(container) {
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }

  function nowTime() {
    try {
      var d = new Date();
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch (e) {
      return "";
    }
  }

  function initChatbot() {
    var toggle = qs("ai-chat-toggle");
    var windowEl = qs("ai-chat-window");
    var closeBtn = windowEl ? windowEl.querySelector(".ai-chat-close") : null;
    var form = qs("ai-chat-form");
    var input = qs("ai-chat-input");
    var messages = qs("ai-chat-messages");
    var typing = qs("ai-chat-typing");

    if (!toggle || !windowEl || !form || !input || !messages || !typing) {
      return;
    }

    function openWindow() {
      windowEl.classList.add("open");
      toggle.classList.add("active");
      input.focus();
    }

    function closeWindow() {
      windowEl.classList.remove("open");
      toggle.classList.remove("active");
    }

    toggle.addEventListener("click", function () {
      if (windowEl.classList.contains("open")) {
        closeWindow();
      } else {
        openWindow();
      }
    });

    if (closeBtn) {
      closeBtn.addEventListener("click", closeWindow);
    }

    form.addEventListener("submit", function (evt) {
      evt.preventDefault();
      var text = (input.value || "").trim();
      if (!text) {
        return;
      }

      // Append user message
      messages.appendChild(
        createBubble(text, "user", "You · " + nowTime())
      );
      scrollToBottom(messages);
      input.value = "";

      // Show typing indicator
      typing.classList.add("visible");

      // Call backend
      fetch("/chat/assistant", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({ message: text }),
      })
        .then(function (r) {
          if (!r.ok) {
            throw new Error("Request failed");
          }
          return r.json();
        })
        .then(function (data) {
          typing.classList.remove("visible");
          var replyText =
            (data && data.reply) ||
            "Sorry, I was not able to generate a reply.";
          var meta =
            "Assistant · " +
            (data && data.intent ? data.intent.replace(/_/g, " ") : "answer");
          messages.appendChild(createBubble(replyText, "bot", meta));
          scrollToBottom(messages);
        })
        .catch(function () {
          typing.classList.remove("visible");
          messages.appendChild(
            createBubble(
              "Sorry, I could not reach the assistant service. Please try again.",
              "bot",
              "Assistant · error"
            )
          );
          scrollToBottom(messages);
        });
    });

    // Optional: submit on Enter
    input.addEventListener("keydown", function (evt) {
      if (evt.key === "Enter" && !evt.shiftKey) {
        evt.preventDefault();
        form.dispatchEvent(new Event("submit", { cancelable: true }));
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initChatbot);
  } else {
    initChatbot();
  }
})();

