// Theme handling: light / dark mode toggle, persisted in localStorage
(function () {
  const root = document.documentElement;
  const stored = localStorage.getItem("healthai-theme");
  const theme = stored || "light";
  root.setAttribute("data-theme", theme);

  function applyToggleState() {
    document.querySelectorAll(".theme-toggle").forEach((btn) => {
      btn.setAttribute("aria-pressed", root.getAttribute("data-theme") === "dark");
    });
  }

  window.toggleTheme = function () {
    const current = root.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("healthai-theme", next);
    applyToggleState();
  };

  document.addEventListener("DOMContentLoaded", applyToggleState);
})();
