(() => {
  const forms = document.querySelectorAll("form[data-endpoint]");

  const FLASH_KEY = "bdku_flash";
  const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const STRONG_PASSWORD = /^(?=.*\p{L})(?=.*\d).{8,}$/u;

  // FR-1.1 / US-ACC-001: cùng thông báo với backend để AC hiển thị giống nhau ở cả hai phía.
  function validateRegister(data) {
    if (!data.display_name) {
      return "Tên hiển thị không được để trống và tối đa 100 ký tự";
    }
    if (!EMAIL_PATTERN.test(data.email || "")) {
      return "Email không hợp lệ";
    }
    if (!STRONG_PASSWORD.test(data.password || "")) {
      return "Mật khẩu phải có ít nhất 8 ký tự gồm chữ và số";
    }
    return "";
  }

  function validate(data, form) {
    if (form.dataset.validate === "register") {
      const error = validateRegister(data);
      if (error) {
        return error;
      }
    }
    if (data.password !== undefined && data.password_confirm !== undefined && data.password !== data.password_confirm) {
      return "Mật khẩu nhập lại không khớp";
    }
    if (data.new_password !== undefined && data.password_confirm !== undefined && data.new_password !== data.password_confirm) {
      return "Mật khẩu nhập lại không khớp";
    }
    return "";
  }

  function buildPayload(form) {
    if (form.enctype === "multipart/form-data") {
      return { formData: new FormData(form) };
    }
    const data = UI.formToJson(form);
    delete data.password_confirm;
    const token = new URLSearchParams(window.location.search).get("token");
    if (form.dataset.withToken !== undefined && token) {
      data.token = token;
    }
    return { body: data };
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const message = form.querySelector(".form-message");
    const error = validate(UI.formToJson(form), form);
    if (error) {
      UI.showMessage(message, error);
      return;
    }

    UI.setBusy(form, true);
    UI.showMessage(message, "");
    try {
      const method = (form.dataset.method || "post").toLowerCase();
      const result = await Api[method](form.dataset.endpoint, buildPayload(form));
      if (result && result.access_token) {
        Api.setToken(result.access_token);
      }
      if (form.dataset.flash) {
        try {
          sessionStorage.setItem(FLASH_KEY, form.dataset.flash);
        } catch (storageError) {
          // Không lưu được thông báo thì vẫn chuyển trang bình thường.
        }
      }
      if (form.dataset.redirect) {
        window.location.href = form.dataset.redirect;
        return;
      }
      UI.showMessage(message, form.dataset.success || "Đã lưu thành công", "success");
      form.dispatchEvent(new CustomEvent("accounts:saved", { detail: result }));
    } catch (requestError) {
      UI.showMessage(message, requestError.message);
    } finally {
      UI.setBusy(form, false);
    }
  }

  forms.forEach((form) => form.addEventListener("submit", handleSubmit));
})();
