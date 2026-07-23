// Dashboard health reminders widget
document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("reminder-form");
  const input = document.getElementById("reminder-input");
  const list = document.getElementById("reminder-list");
  if (!form) return;

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function renderItem(r) {
    const div = document.createElement("div");
    div.className = "reminder-item" + (r.is_done ? " done" : "");
    div.dataset.id = r.id;
    div.innerHTML = `
      <input type="checkbox" ${r.is_done ? "checked" : ""} onchange="toggleReminder(${r.id})">
      <span>${escapeHtml(r.text)}</span>
      <button type="button" class="reminder-delete" onclick="deleteReminder(${r.id})">
        <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6h16Z"/></svg>
      </button>`;
    return div;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    const res = await fetch("/api/reminders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const reminders = await res.json();
    input.value = "";

    const empty = document.getElementById("reminder-empty");
    if (empty) empty.remove();
    list.innerHTML = "";
    reminders.forEach((r) => list.appendChild(renderItem(r)));
  });
});

async function toggleReminder(id) {
  await fetch(`/api/reminders/${id}/toggle`, { method: "POST" });
  const item = document.querySelector(`.reminder-item[data-id="${id}"]`);
  if (item) item.classList.toggle("done");
}

async function deleteReminder(id) {
  await fetch(`/api/reminders/${id}/delete`, { method: "POST" });
  const item = document.querySelector(`.reminder-item[data-id="${id}"]`);
  if (item) item.remove();
  const list = document.getElementById("reminder-list");
  if (list && !list.querySelector(".reminder-item")) {
    list.innerHTML = '<div class="reminder-empty">No reminders yet. Add one above.</div>';
  }
}
