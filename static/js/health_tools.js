// Health Tools: carousel navigation, disease search, BMI calculator
document.addEventListener("DOMContentLoaded", function () {
  const track = document.getElementById("disease-track");
  const prevBtn = document.getElementById("carousel-prev");
  const nextBtn = document.getElementById("carousel-next");
  const searchInput = document.getElementById("disease-search");
  const noResults = document.getElementById("no-results");

  if (track) {
    function cardWidth() {
      const card = track.querySelector(".disease-card");
      return card ? card.offsetWidth + 20 : 340;
    }

    prevBtn?.addEventListener("click", () => {
      track.scrollBy({ left: -cardWidth(), behavior: "smooth" });
    });
    nextBtn?.addEventListener("click", () => {
      track.scrollBy({ left: cardWidth(), behavior: "smooth" });
    });
  }

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      const query = searchInput.value.trim().toLowerCase();
      const cards = track.querySelectorAll(".disease-card");
      let visibleCount = 0;

      cards.forEach((card) => {
        const matches = card.dataset.name.includes(query);
        card.style.display = matches ? "flex" : "none";
        if (matches) visibleCount++;
      });

      if (noResults) noResults.classList.toggle("show", visibleCount === 0);
      track.style.display = visibleCount === 0 ? "none" : "flex";
    });
  }

  // BMI Calculator
  const bmiBtn = document.getElementById("bmi-calc-btn");
  const heightInput = document.getElementById("bmi-height");
  const weightInput = document.getElementById("bmi-weight");
  const resultBox = document.getElementById("bmi-result");
  const valueEl = document.getElementById("bmi-value");
  const categoryEl = document.getElementById("bmi-category-text");

  bmiBtn?.addEventListener("click", () => {
    const heightCm = parseFloat(heightInput.value);
    const weightKg = parseFloat(weightInput.value);

    if (!heightCm || !weightKg || heightCm <= 0 || weightKg <= 0) {
      alert("Please enter valid height and weight values.");
      return;
    }

    const heightM = heightCm / 100;
    const bmi = weightKg / (heightM * heightM);
    let category;

    if (bmi < 18.5) category = "Underweight";
    else if (bmi < 25) category = "Normal weight";
    else if (bmi < 30) category = "Overweight";
    else category = "Obese";

    valueEl.textContent = bmi.toFixed(1);
    categoryEl.textContent = category;
    resultBox.classList.add("show");
  });
});
