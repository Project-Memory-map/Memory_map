const UI = (() => {
  let toastTimer = null;

  function toast(message) {
    const element = document.getElementById("toast");
    if (!element) {
      return;
    }
    element.textContent = message;
    element.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      element.hidden = true;
    }, 3000);
  }

  async function loadPartial(container, url) {
    const target = typeof container === "string" ? document.getElementById(container) : container;
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Không tải được giao diện ${url}`);
    }
    target.innerHTML = await response.text();
    return target;
  }

  function formToJson(form) {
    const data = {};
    new FormData(form).forEach((value, key) => {
      if (typeof value === "string") {
        data[key] = value.trim();
      }
    });
    return data;
  }

  function setBusy(form, busy) {
    form.querySelectorAll("button, input, select, textarea").forEach((element) => {
      element.disabled = busy;
    });
  }

  function showMessage(element, message, type = "error") {
    element.textContent = message;
    element.className = `form-message form-message--${type}`;
    element.hidden = !message;
  }

  function formatDate(value) {
    const [year, month, day] = value.split("-");
    return `${day}/${month}/${year}`;
  }

  return { toast, loadPartial, formToJson, setBusy, showMessage, formatDate };
})();
