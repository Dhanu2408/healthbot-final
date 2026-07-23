// Shared app behaviour: skeleton loader, mobile sidebar, active nav link
document.addEventListener("DOMContentLoaded", function () {
  // Hide skeleton screen once content is ready
  const skeleton = document.getElementById("page-skeleton");
  if (skeleton) {
    setTimeout(() => {
      skeleton.classList.add("hidden");
      setTimeout(() => skeleton.remove(), 450);
    }, 400);
  }

  // Mobile sidebar toggle
  const menuBtn = document.querySelector(".menu-btn");
  const sidebar = document.querySelector(".sidebar");
  const backdrop = document.querySelector(".sidebar-backdrop");

  function closeSidebar() {
    if (sidebar) sidebar.classList.remove("open");
    if (backdrop) backdrop.classList.remove("show");
  }

  if (menuBtn && sidebar) {
    menuBtn.addEventListener("click", () => {
      sidebar.classList.toggle("open");
      if (backdrop) backdrop.classList.toggle("show");
    });
  }
  if (backdrop) backdrop.addEventListener("click", closeSidebar);

  // Auto-dismiss flash messages
  document.querySelectorAll(".flash").forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity 0.4s ease";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 400);
    }, 5000);
  });
});
