// Emergency page: slider navigation + share live location
document.addEventListener("DOMContentLoaded", function () {
  const track = document.getElementById("emergency-track");
  const prevBtn = document.getElementById("emergency-prev");
  const nextBtn = document.getElementById("emergency-next");

  if (track) {
    function slideWidth() {
      const card = track.querySelector(".emergency-card");
      return card ? card.offsetWidth + 20 : 340;
    }

    prevBtn?.addEventListener("click", () => {
      track.scrollBy({ left: -slideWidth(), behavior: "smooth" });
    });
    nextBtn?.addEventListener("click", () => {
      track.scrollBy({ left: slideWidth(), behavior: "smooth" });
    });
  }

  const shareBtn = document.getElementById("share-location-btn");
  if (shareBtn) {
    shareBtn.addEventListener("click", () => {
      if (!navigator.geolocation) {
        alert("Location access isn't supported in this browser.");
        return;
      }
      shareBtn.disabled = true;
      const originalText = shareBtn.innerHTML;
      shareBtn.textContent = "Getting your location...";

      navigator.geolocation.getCurrentPosition(
        (position) => {
          const { latitude, longitude } = position.coords;
          const url = `https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`;
          window.open(url, "_blank", "noopener");
          shareBtn.disabled = false;
          shareBtn.innerHTML = originalText;
        },
        () => {
          alert("Couldn't access your location. Please allow location permission and try again.");
          shareBtn.disabled = false;
          shareBtn.innerHTML = originalText;
        }
      );
    });
  }
});
