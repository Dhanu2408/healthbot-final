// Chatbot page behaviour: messaging, voice input, language toggle, history
document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const messages = document.getElementById("chat-messages");
  const clearBtn = document.getElementById("clear-chat-btn");
  const historyList = document.getElementById("history-list");
  const historySearch = document.getElementById("history-search");
  const micBtn = document.getElementById("mic-btn");
  const langToggle = document.getElementById("lang-toggle");
  const suggestedEn = document.getElementById("suggested-en");
  const suggestedTa = document.getElementById("suggested-ta");

  if (!form) return;

  let currentLang = "en";

  function scrollToBottom() {
    messages.scrollTop = messages.scrollHeight;
  }
  scrollToBottom();

  function appendMessage(sender, text) {
    const bubble = document.createElement("div");
    bubble.className = "msg " + (sender === "user" ? "msg-user" : "msg-ai");
    bubble.textContent = text;
    messages.appendChild(bubble);
    scrollToBottom();
  }

  function showTyping() {
    const typing = document.createElement("div");
    typing.className = "typing-indicator";
    typing.id = "typing-indicator";
    typing.innerHTML = "<span></span><span></span><span></span>";
    messages.appendChild(typing);
    scrollToBottom();
  }

  function hideTyping() {
    const typing = document.getElementById("typing-indicator");
    if (typing) typing.remove();
  }

  async function sendMessage(text) {
    if (!text.trim()) return;
    appendMessage("user", text);
    input.value = "";
    showTyping();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, lang: currentLang }),
      });
      const data = await res.json();
      hideTyping();
      if (res.ok) {
        appendMessage("ai", data.reply);
        refreshHistory();
      } else {
        appendMessage("ai", "Sorry, something went wrong. Please try again.");
      }
    } catch (err) {
      hideTyping();
      appendMessage("ai", "Connection error. Please check your network and try again.");
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage(input.value);
  });

  document.querySelectorAll(".chip[data-question]").forEach((chip) => {
    chip.addEventListener("click", () => sendMessage(chip.dataset.question));
  });

  if (clearBtn) {
    clearBtn.addEventListener("click", async () => {
      if (!confirm("Clear the entire conversation?")) return;
      await fetch("/api/chat/clear", { method: "POST" });
      messages.innerHTML = "";
      refreshHistory();
    });
  }

  function renderHistorySkeleton() {
    if (!historyList) return;
    historyList.innerHTML = Array(4)
      .fill('<div class="skeleton skeleton-row"></div>')
      .join("");
  }

  function renderHistory(items) {
    if (!historyList) return;
    if (!items.length) {
      historyList.innerHTML = '<div class="history-empty">No conversations yet.</div>';
      return;
    }
    historyList.innerHTML = items
      .map(
        (item) => `
        <div class="history-item">
          <span class="h-sender">${item.sender === "user" ? "You" : "HealthAI"}</span>
          <div class="h-msg">${escapeHtml(item.message)}</div>
        </div>`
      )
      .join("");
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  async function refreshHistory(query) {
    if (!historyList) return;
    const url = query ? `/api/chat/history?q=${encodeURIComponent(query)}` : "/api/chat/history";
    const res = await fetch(url);
    const data = await res.json();
    renderHistory(data);
  }

  let searchDebounce;
  if (historySearch) {
    historySearch.addEventListener("input", () => {
      clearTimeout(searchDebounce);
      renderHistorySkeleton();
      searchDebounce = setTimeout(() => refreshHistory(historySearch.value), 300);
    });
  }

  // Language toggle (English / Tamil)
  if (langToggle) {
    langToggle.querySelectorAll("button[data-lang]").forEach((btn) => {
      btn.addEventListener("click", () => {
        currentLang = btn.dataset.lang;
        langToggle.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b === btn));
        if (suggestedEn && suggestedTa) {
          suggestedEn.style.display = currentLang === "en" ? "flex" : "none";
          suggestedTa.style.display = currentLang === "ta" ? "flex" : "none";
        }
        input.placeholder = currentLang === "ta" ? "உங்கள் கேள்வியை தட்டச்சு செய்யவும்..." : "Type your health question...";
      });
    });
  }

  // Voice input via Web Speech API (supported in Chrome/Edge)
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (micBtn && SpeechRecognition) {
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;

    micBtn.addEventListener("click", () => {
      recognition.lang = currentLang === "ta" ? "ta-IN" : "en-US";
      micBtn.classList.add("listening");
      try {
        recognition.start();
      } catch (err) {
        micBtn.classList.remove("listening");
      }
    });

    recognition.addEventListener("result", (event) => {
      const transcript = event.results[0][0].transcript;
      input.value = transcript;
    });

    recognition.addEventListener("end", () => micBtn.classList.remove("listening"));
    recognition.addEventListener("error", () => micBtn.classList.remove("listening"));
  } else if (micBtn) {
    micBtn.addEventListener("click", () => {
      alert("Voice input isn't supported in this browser. Try Chrome or Edge.");
    });
  }
});
