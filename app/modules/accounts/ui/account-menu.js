const AccountMenu = (() => {
  const menu = document.getElementById("account-menu");

  function link(text, href, className = "icon-button") {
    const element = document.createElement("a");
    element.className = className;
    element.href = href;
    element.textContent = text;
    return element;
  }

  function renderGuest() {
    menu.replaceChildren(
      link("Đăng nhập", "/accounts/login.html", "button"),
      link("Đăng ký", "/accounts/register.html"),
    );
  }

  function renderUser(user) {
    const name = document.createElement("span");
    name.className = "account-menu__name";
    name.textContent = user.display_name;

    const logout = document.createElement("button");
    logout.type = "button";
    logout.className = "icon-button";
    logout.textContent = "Đăng xuất";
    logout.addEventListener("click", () => {
      Api.setToken(null);
      window.location.href = "/";
    });

    const items = [name, link("Hồ sơ", "/accounts/profile.html")];
    if (user.role === "admin") {
      items.push(link("Quản trị", "/admin/"));
    }
    items.push(logout);
    menu.replaceChildren(...items);
  }

  async function init() {
    if (!menu) {
      return null;
    }
    if (!Api.getToken()) {
      renderGuest();
      return null;
    }
    try {
      const user = await Api.get("/api/auth/me");
      renderUser(user);
      return user;
    } catch (error) {
      renderGuest();
      return null;
    }
  }

  // Thông báo do trang tài khoản để lại trước khi chuyển về bản đồ (ví dụ "Đăng ký thành công").
  function showFlash() {
    try {
      const message = sessionStorage.getItem("bdku_flash");
      if (message) {
        sessionStorage.removeItem("bdku_flash");
        UI.toast(message);
      }
    } catch (error) {
      return;
    }
  }

  showFlash();
  const ready = init();

  return { ready };
})();
