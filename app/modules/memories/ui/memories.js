(() => {
  const MAX_IMAGES = 10;
  const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
  const MAX_VIDEO_BYTES = 50 * 1024 * 1024;
  const drawer = document.getElementById("drawer");

  function today() {
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    return now.toISOString().slice(0, 10);
  }

  function closeDrawer() {
    drawer.hidden = true;
    drawer.replaceChildren();
  }

  function validateFiles(form) {
    const images = Array.from(form.elements.images.files);
    const video = form.elements.video.files[0];
    if (images.length > MAX_IMAGES) {
      return `Mỗi ký ức tối đa ${MAX_IMAGES} ảnh`;
    }
    if (images.some((file) => file.size > MAX_IMAGE_BYTES)) {
      return "Ảnh không được vượt quá 5 MB";
    }
    if (video && video.size > MAX_VIDEO_BYTES) {
      return "Video không được vượt quá 50 MB";
    }
    return "";
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const message = form.querySelector(".form-message");
    const error = validateFiles(form);
    if (error) {
      UI.showMessage(message, error);
      return;
    }
    const formData = new FormData(form);
    UI.setBusy(form, true);
    try {
      await Api.post("/api/memories", { formData });
      closeDrawer();
      UI.toast("Đã lưu ký ức");
    } catch (requestError) {
      UI.showMessage(message, requestError.message);
      UI.setBusy(form, false);
    }
  }

  async function openForm({ latitude, longitude }) {
    await UI.loadPartial(drawer, "/memories/memory-form.html");
    drawer.hidden = false;
    const form = document.getElementById("memory-form");
    form.elements.latitude.value = latitude.toFixed(6);
    form.elements.longitude.value = longitude.toFixed(6);
    form.elements.memory_date.max = today();
    form.elements.memory_date.value = today();
    document.getElementById("memory-coords").textContent =
      `Tọa độ: ${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
    drawer.querySelector("[data-close-drawer]").addEventListener("click", closeDrawer);
    form.addEventListener("submit", handleSubmit);
    form.elements.title.focus();
  }

  async function handlePick(position) {
    const user = await AccountMenu.ready;
    if (!user) {
      UI.toast("Đăng nhập để ghim ký ức tại vị trí này");
      return;
    }
    openForm(position);
  }

  UI.loadPartial("memories-panel", "/memories/panel.html");
  MemoryMap.onPick(handlePick);
})();
