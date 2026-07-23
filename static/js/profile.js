// Profile page: live preview of selected photo before upload
document.addEventListener("DOMContentLoaded", function () {
  const input = document.getElementById("profile_photo_input");
  if (!input) return;

  input.addEventListener("change", () => {
    const file = input.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      let img = document.getElementById("photo-preview");
      const fallback = document.getElementById("photo-preview-fallback");
      if (!img && fallback) {
        img = document.createElement("img");
        img.id = "photo-preview";
        img.className = "profile-photo-preview";
        img.alt = "Profile photo";
        fallback.replaceWith(img);
      }
      if (img) img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
});
