/* Xử lý chung cho mọi form tài khoản: form[data-endpoint] gửi JSON (hoặc multipart) tới API. */
(() => {
  const params = new URLSearchParams(window.location.search);
  const forms = document.querySelectorAll("form[data-endpoint]");
  const PASSWORD_RULE = /^(?=.*[A-Za-zÀ-ỹ])(?=.*\d).{8,}$/;

  function safeNext() {
    const next = params.get("next");
    return next && next.startsWith("/") && !next.startsWith("//") ? next : "/ban-do";
  }

  function validate(form, data) {
    const email = form.elements.email;
    if (email && email.value && !email.checkValidity()) return "Email không hợp lệ";
    const password = data.password !== undefined ? data.password : data.new_password;
    if (password !== undefined && form.elements.password_confirm) {
      if (!PASSWORD_RULE.test(password)) return "Mật khẩu phải có ít nhất 8 ký tự gồm chữ và số";
      if (password !== data.password_confirm) return "Mật khẩu nhập lại không khớp";
    }
    if (data.display_name !== undefined && !data.display_name) return "Vui lòng nhập tên hiển thị";
    if (data.display_name && data.display_name.length > 100) return "Tên hiển thị tối đa 100 ký tự";
    return "";
  }

  function buildPayload(form) {
    if (form.enctype === "multipart/form-data") {
      return { formData: new FormData(form) };
    }
    const data = UI.formToJson(form);
    delete data.password_confirm;
    Object.keys(data).forEach((key) => {
      if (form.elements[key] && form.elements[key].type === "password") {
        data[key] = form.elements[key].value; // không cắt khoảng trắng trong mật khẩu
      }
    });
    const token = params.get("token");
    if (form.dataset.withToken !== undefined && token) {
      data.token = token;
    }
    return { body: data };
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const message = form.querySelector(".form-message");
    const error = validate(form, UI.formToJson(form));
    if (error) {
      UI.showMessage(message, error);
      return;
    }
    if (form.dataset.withToken !== undefined && !params.get("token")) {
      UI.showMessage(message, "Liên kết đã hết hạn, vui lòng yêu cầu lại");
      return;
    }

    const payload = buildPayload(form); // đọc dữ liệu trước khi khóa form (ô bị disabled không có trong FormData)
    UI.setBusy(form, true);
    UI.showMessage(message, "");
    try {
      const method = (form.dataset.method || "post").toLowerCase();
      const result = await Api[method](form.dataset.endpoint, payload);
      if (result && result.access_token) {
        Api.setToken(result.access_token);
      }
      if (form.dataset.redirect) {
        const target = form.dataset.redirect === "next" ? safeNext() : form.dataset.redirect;
        const separator = target.includes("?") ? "&" : "?";
        window.location.href = form.dataset.notice ? `${target}${separator}notice=${form.dataset.notice}` : target;
        return;
      }
      UI.showMessage(message, form.dataset.success || "Đã lưu thành công", "success");
      if (form.dataset.reset !== undefined) form.reset();
      form.dispatchEvent(new CustomEvent("accounts:saved", { detail: result }));
    } catch (requestError) {
      UI.showMessage(message, requestError.message);
    } finally {
      UI.setBusy(form, false);
    }
  }

  forms.forEach((form) => form.addEventListener("submit", handleSubmit));

  /* Nút hiện/ẩn mật khẩu */
  document.querySelectorAll(".password-field").forEach((wrapper) => {
    const input = wrapper.querySelector("input");
    const toggle = UI.el("button", { type: "button", className: "password-toggle", "aria-label": "Hiện mật khẩu", text: "👁" });
    toggle.addEventListener("click", () => {
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      toggle.setAttribute("aria-label", show ? "Ẩn mật khẩu" : "Hiện mật khẩu");
      toggle.textContent = show ? "🙈" : "👁";
    });
    wrapper.append(toggle);
  });

  /* Thông báo truyền qua URL (lỗi OAuth, đã đăng xuất...) */
  const pageMessage = document.getElementById("page-message");
  if (pageMessage) {
    if (params.get("error")) UI.showMessage(pageMessage, params.get("error"), "error");
    else if (params.get("logged_out")) UI.showMessage(pageMessage, "Bạn đã đăng xuất", "info");
    else if (params.get("registered")) UI.showMessage(pageMessage, "Đăng ký thành công", "success");
  }

  /* Đã đăng nhập mà vào trang đăng nhập/đăng ký thì về bản đồ */
  if (document.body.dataset.guestOnly !== undefined && Api.getToken()) {
    Api.get("/api/auth/me")
      .then(() => window.location.replace(safeNext()))
      .catch(() => Api.setToken(null));
  }

  /* Trạng thái cấu hình đăng nhập mạng xã hội */
  const socialButtons = document.querySelectorAll("[data-provider]");
  if (socialButtons.length) {
    Api.get("/api/auth/providers")
      .then((status) => {
        socialButtons.forEach((button) => {
          if (!status[button.dataset.provider]) {
            button.classList.add("is-disabled");
            button.title = "Quản trị hệ thống chưa cấu hình khóa đăng nhập này trong .env";
          }
        });
      })
      .catch(() => {});
  }

  /* Quên mật khẩu (chế độ dev chưa cấu hình SMTP): hiện liên kết đặt lại để kiểm thử */
  const forgotForm = document.getElementById("forgot-form");
  if (forgotForm) {
    forgotForm.addEventListener("accounts:saved", (event) => {
      const link = event.detail && event.detail.dev_reset_url;
      const box = document.getElementById("dev-link");
      if (link && box) {
        box.replaceChildren(
          UI.el("strong", { text: "Chế độ phát triển (chưa cấu hình SMTP): " }),
          UI.el("a", { href: link, text: "mở liên kết đặt lại mật khẩu" }),
        );
        box.hidden = false;
      }
    });
  }
})();
