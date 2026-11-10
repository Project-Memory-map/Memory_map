/* Tiện ích giao diện dùng chung. Dữ liệu người dùng chỉ được gán bằng textContent (BR-21). */
const UI = (() => {
  let toastTimer = null;

  /* Tạo phần tử DOM: UI.el("div", {className: "x", text: "..."}, [con...]) */
  function el(tag, props = {}, children = []) {
    const element = document.createElement(tag);
    Object.entries(props).forEach(([key, value]) => {
      if (value === undefined || value === null || value === false) return;
      if (key === "text") element.textContent = value;
      else if (key === "className") element.className = value;
      else if (key === "dataset") Object.assign(element.dataset, value);
      else if (key.startsWith("on") && typeof value === "function") element.addEventListener(key.slice(2), value);
      else if (key === "style") Object.assign(element.style, value);
      else if (value === true) element.setAttribute(key, "");
      else element.setAttribute(key, value);
    });
    (Array.isArray(children) ? children : [children]).forEach((child) => {
      if (child === null || child === undefined || child === false) return;
      element.append(child instanceof Node ? child : document.createTextNode(String(child)));
    });
    return element;
  }

  function toast(message, type = "info") {
    let element = document.getElementById("toast");
    if (!element) {
      element = el("div", { id: "toast", className: "toast", role: "status", hidden: true });
      document.body.append(element);
    }
    element.textContent = message;
    element.className = `toast${type === "error" ? " toast--error" : type === "success" ? " toast--success" : ""}`;
    element.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      element.hidden = true;
    }, type === "error" ? 4500 : 3000);
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
      if (busy) {
        element.dataset.wasDisabled = element.disabled ? "1" : "";
        element.disabled = true;
      } else {
        element.disabled = element.dataset.wasDisabled === "1";
      }
    });
    const submit = form.querySelector('[type="submit"]');
    if (submit) {
      if (busy) {
        submit.dataset.label = submit.textContent;
        submit.textContent = "Đang xử lý...";
      } else if (submit.dataset.label) {
        submit.textContent = submit.dataset.label;
      }
    }
  }

  function showMessage(element, message, type = "error") {
    if (!element) return;
    element.textContent = message || "";
    element.className = `form-message form-message--${type}`;
    element.hidden = !message;
  }

  function formatDate(value) {
    if (!value) return "";
    const [year, month, day] = String(value).slice(0, 10).split("-");
    return `${day}/${month}/${year}`;
  }

  function formatDateTime(value) {
    if (!value) return "";
    const date = new Date(String(value).replace(" ", "T"));
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
  }

  function today() {
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    return now.toISOString().slice(0, 10);
  }

  function debounce(fn, wait = 300) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), wait);
    };
  }

  /* ---------- Hộp thoại ---------- */
  function modal(buildContent, { wide = false } = {}) {
    return new Promise((resolve) => {
      const previous = document.activeElement;
      const box = el("div", { className: `modal${wide ? " modal--wide" : ""}`, role: "dialog", "aria-modal": "true" });
      const backdrop = el("div", { className: "modal-backdrop" }, box);
      function close(value) {
        backdrop.remove();
        document.removeEventListener("keydown", onKey);
        if (previous && previous.focus) previous.focus();
        resolve(value);
      }
      function onKey(event) {
        if (event.key === "Escape") close(null);
      }
      backdrop.addEventListener("mousedown", (event) => {
        if (event.target === backdrop) close(null);
      });
      document.addEventListener("keydown", onKey);
      buildContent(box, close);
      document.body.append(backdrop);
      const focusTarget = box.querySelector("[autofocus], input, textarea, select, button");
      if (focusTarget) focusTarget.focus();
    });
  }

  function confirm({ title, message, confirmText = "Đồng ý", cancelText = "Hủy", danger = false }) {
    return modal((box, close) => {
      box.append(
        el("h3", { text: title }),
        el("p", { text: message }),
        el("div", { className: "modal__actions" }, [
          el("button", { type: "button", className: "button", text: cancelText, onclick: () => close(false) }),
          el("button", {
            type: "button",
            className: `button ${danger ? "button--danger" : "button--primary"}`,
            text: confirmText,
            onclick: () => close(true),
          }),
        ]),
      );
    }).then((value) => value === true);
  }

  /* Hộp nhập lý do (quản trị) — required: bắt buộc nhập */
  function prompt({ title, message, label = "Lý do", placeholder = "", confirmText = "Xác nhận", required = true, danger = false }) {
    return modal((box, close) => {
      const textarea = el("textarea", { rows: 3, maxlength: 500, placeholder, autofocus: true });
      const error = el("p", { className: "form-message form-message--error", hidden: true });
      const form = el("form", { className: "form" }, [
        el("label", { className: "field" }, [label, textarea]),
        error,
        el("div", { className: "modal__actions" }, [
          el("button", { type: "button", className: "button", text: "Hủy", onclick: () => close(null) }),
          el("button", { type: "submit", className: `button ${danger ? "button--danger" : "button--primary"}`, text: confirmText }),
        ]),
      ]);
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const value = textarea.value.trim();
        if (required && !value) {
          showMessage(error, "Vui lòng nhập lý do");
          return;
        }
        close(value);
      });
      box.append(el("h3", { text: title }), message ? el("p", { text: message }) : null, form);
    });
  }

  /* ---------- Xem ảnh phóng to ---------- */
  function lightbox(urls, startIndex = 0) {
    let index = startIndex;
    const image = el("img", { alt: "Ảnh ký ức" });
    const counter = el("div", { className: "lightbox__counter" });
    function show() {
      image.src = urls[index];
      counter.textContent = `${index + 1} / ${urls.length}`;
    }
    function move(step) {
      index = (index + step + urls.length) % urls.length;
      show();
    }
    const box = el("div", { className: "lightbox", role: "dialog", "aria-label": "Xem ảnh" }, [
      image,
      counter,
      el("button", { className: "lightbox__btn lightbox__close", type: "button", "aria-label": "Đóng", text: "✕", onclick: close }),
      urls.length > 1 ? el("button", { className: "lightbox__btn lightbox__prev", type: "button", "aria-label": "Ảnh trước", text: "‹", onclick: () => move(-1) }) : null,
      urls.length > 1 ? el("button", { className: "lightbox__btn lightbox__next", type: "button", "aria-label": "Ảnh sau", text: "›", onclick: () => move(1) }) : null,
    ]);
    function onKey(event) {
      if (event.key === "Escape") close();
      if (event.key === "ArrowLeft") move(-1);
      if (event.key === "ArrowRight") move(1);
    }
    function close() {
      box.remove();
      document.removeEventListener("keydown", onKey);
    }
    box.addEventListener("click", (event) => {
      if (event.target === box) close();
    });
    document.addEventListener("keydown", onKey);
    show();
    document.body.append(box);
  }

  /* ---------- Sự kiện giữa các module ---------- */
  function emit(name, detail) {
    document.dispatchEvent(new CustomEvent(name, { detail }));
  }

  function on(name, handler) {
    document.addEventListener(name, (event) => handler(event.detail));
  }

  function emptyState(icon, text) {
    return el("div", { className: "empty-state" }, [el("span", { className: "empty-state__icon", text: icon }), text]);
  }

  /* Thẻ ký ức dùng cho mọi danh sách */
  function memoryCard(memory, { onClick, showAuthor = true, showVisibility = false } = {}) {
    const thumb = memory.cover_url
      ? el("img", { className: "memory-card__thumb", src: memory.cover_url, alt: "", loading: "lazy" })
      : el("div", { className: "memory-card__thumb", text: memory.has_video ? "🎬" : "📍" });
    const meta = [UI.formatDate(memory.memory_date), memory.place_name].filter(Boolean).join(" · ");
    const badges = el("div", { className: "memory-card__badges" });
    if (showVisibility) {
      badges.append(
        el("span", {
          className: `badge ${memory.visibility === "public" ? "badge--public" : "badge--private"}`,
          text: memory.visibility === "public" ? "Công khai" : "Riêng tư",
        }),
      );
      if (memory.status === "hidden") badges.append(el("span", { className: "badge badge--hidden", text: "Bị ẩn" }));
    }
    if (showAuthor && memory.author) {
      badges.append(el("span", { className: "badge", text: memory.author.display_name }));
    }
    const tags = el("div", { className: "memory-card__tags" });
    (memory.hashtags || []).slice(0, 4).forEach((tag) => tags.append(el("span", { text: `#${tag}` })));
    return el(
      "button",
      { type: "button", className: "memory-card", onclick: () => onClick && onClick(memory) },
      [
        thumb,
        el("div", { className: "memory-card__body" }, [
          el("span", { className: "memory-card__title", text: memory.title }),
          el("span", { className: "memory-card__meta", text: meta }),
          badges.childElementCount ? badges : null,
          tags.childElementCount ? tags : null,
        ]),
      ],
    );
  }

  return {
    el,
    toast,
    formToJson,
    setBusy,
    showMessage,
    formatDate,
    formatDateTime,
    today,
    debounce,
    modal,
    confirm,
    prompt,
    lightbox,
    emit,
    on,
    emptyState,
    memoryCard,
  };
})();
