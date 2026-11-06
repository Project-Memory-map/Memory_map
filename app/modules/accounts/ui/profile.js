(async () => {
  const user = await AccountMenu.ready;
  if (!user) {
    window.location.href = "/accounts/login.html";
    return;
  }

  const form = document.getElementById("profile-form");
  form.elements.display_name.value = user.display_name;
  form.elements.bio.value = user.bio || "";

  const avatarInput = document.querySelector('input[name="avatar"]');
  const preview = document.getElementById("avatar-preview");
  avatarInput.addEventListener("change", () => {
    const file = avatarInput.files[0];
    if (!file) {
      preview.hidden = true;
      return;
    }
    preview.src = URL.createObjectURL(file);
    preview.hidden = false;
  });
})();
