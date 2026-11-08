(() => {
  const forms = document.querySelectorAll("form[data-endpoint]");
  const resetToken = new URLSearchParams(location.search).get("token");

  function readForm(form) {
    const data = {};

    new FormData(form).forEach((value, name) => {
      if (typeof value === "string") {
        // Giữ nguyên khoảng trắng trong mật khẩu.
        data[name] = name.includes("password")
          ? value
          : value.trim();
      }
    });

    return data;
  }

  function passwordError(password) {
    if (
      password.length < 8 ||
      !/\p{L}/u.test(password) ||
      !/[0-9]/.test(password)
    ) {
      return "Mật khẩu phải có ít nhất 8 ký tự gồm chữ và số";
    }

    if (new TextEncoder().encode(password).length > 72) {
      return "Mật khẩu không được dài quá 72 byte";
    }

    return "";
  }

  function validate(data, form) {
    // Hỗ trợ form đăng ký khi được tích hợp với phần của nhóm.
    if (form.dataset.validate === "register") {
      if (
        !data.display_name ||
        data.display_name.length > 100
      ) {
        return "Tên hiển thị không được để trống và tối đa 100 ký tự";
      }

      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email || "")) {
        return "Email không hợp lệ";
      }

      const error = passwordError(data.password || "");

      if (error) {
        return error;
      }
    }

    if (data.new_password !== undefined) {
      const error = passwordError(data.new_password);

      if (error) {
        return error;
      }
    }

    const password = data.new_password ?? data.password;

    if (
      data.password_confirm !== undefined &&
      password !== data.password_confirm
    ) {
      return "Mật khẩu nhập lại không khớp";
    }

    if (
      form.hasAttribute("data-with-token") &&
      !resetToken
    ) {
      return "Liên kết không hợp lệ, vui lòng yêu cầu lại";
    }

    return "";
  }

  async function handleSubmit(event) {
    event.preventDefault();

    const form = event.currentTarget;

    if (
      form.dataset.busy === "true" ||
      form.dataset.done === "true"
    ) {
      return;
    }

    const message = form.querySelector(".form-message");
    const data = readForm(form);
    const error = validate(data, form);

    if (error) {
      UI.showMessage(message, error);
      return;
    }

    delete data.password_confirm;

    if (form.hasAttribute("data-with-token")) {
      data.token = resetToken;
    }

    // Phải lấy dữ liệu TRƯỚC khi vô hiệu hóa input.
    const payload =
      form.enctype === "multipart/form-data"
        ? { formData: new FormData(form) }
        : { body: data };

    form.dataset.busy = "true";
    UI.setBusy(form, true);
    UI.showMessage(message, "");

    try {
      const method = (
        form.dataset.method || "post"
      ).toLowerCase();

      const result = await Api[method](
        form.dataset.endpoint,
        payload
      );

      if (result?.access_token) {
        Api.setToken(result.access_token);
      }

      // Sau khi đặt lại mật khẩu, yêu cầu đăng nhập lại.
      if (form.hasAttribute("data-with-token")) {
        Api.setToken(null);
        form.dataset.done = "true";
        form.reset();
      }

      if (form.dataset.flash) {
        try {
          sessionStorage.setItem(
            "bdku_flash",
            form.dataset.flash
          );
        } catch (_) {
          // Vẫn tiếp tục nếu trình duyệt không cho lưu.
        }
      }

      if (form.dataset.redirect) {
        location.href = form.dataset.redirect;
        return;
      }

      UI.showMessage(
        message,
        form.dataset.success || "Đã lưu thành công",
        "success"
      );

      form.dispatchEvent(
        new CustomEvent("accounts:saved", {
          detail: result,
        })
      );
    } catch (error) {
      UI.showMessage(
        message,
        error.message || "Không kết nối được máy chủ"
      );
    } finally {
      form.dataset.busy = "false";

      UI.setBusy(
        form,
        form.dataset.done === "true"
      );
    }
  }

  forms.forEach((form) => {
    form.addEventListener("submit", handleSubmit);
  });

  // Kiểm tra token ngay khi mở liên kết trong email.
  async function checkResetLink() {
    const form = document.querySelector(
      "form[data-with-token]"
    );

    if (!form) {
      return;
    }

    form.dataset.busy = "true";
    UI.setBusy(form, true);

    try {
      if (!resetToken) {
        throw new Error(
          "Liên kết không hợp lệ, vui lòng yêu cầu lại"
        );
      }

      await Api.post("/api/auth/validate-reset-token", {
        body: {
          token: resetToken,
        },
      });

      UI.setBusy(form, false);
    } catch (error) {
      form.dataset.done = "true";

      UI.showMessage(
        form.querySelector(".form-message"),
        error.message
      );
    } finally {
      form.dataset.busy = "false";
    }
  }

  checkResetLink();
})();