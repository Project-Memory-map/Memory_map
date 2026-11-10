/* Menu tài khoản góc trên: khách thấy Đăng nhập/Đăng ký; người dùng thấy ảnh, tên, Hồ sơ, Quản trị, Đăng xuất. */
const AccountMenu = (() => {
  const menu = document.getElementById("account-menu");
  let currentUser = null;

  function initials(name) {
    return (name || "?").trim().split(/\s+/).slice(-2).map((part) => part[0]).join("").toUpperCase();
  }

  function avatar(user, size = "") {
    if (user.avatar_url) {
      return UI.el("img", { className: `avatar ${size}`, src: user.avatar_url, alt: "" });
    }
    return UI.el("span", { className: `avatar avatar--initials ${size}`, text: initials(user.display_name) });
  }

  function renderGuest() {
    currentUser = null;
    if (!menu) return;
    menu.replaceChildren(
      UI.el("a", { className: "button button--ghost", href: "/accounts/register.html", text: "Đăng ký" }),
      UI.el("a", { className: "button button--primary", href: `/accounts/login.html?next=${encodeURIComponent(location.pathname + location.search)}`, text: "Đăng nhập" }),
    );
  }

  async function logout() {
    try {
      await Api.post("/api/auth/logout");
    } catch (error) {
      /* bỏ qua */
    }
    Api.setToken(null);
    window.location.replace("/accounts/login.html?logged_out=1");
  }

  function renderUser(user) {
    currentUser = user;
    if (!menu) return;
    const dropdown = UI.el("div", { className: "account-dropdown", hidden: true, role: "menu" }, [
      UI.el("div", { className: "account-dropdown__head" }, [
        avatar(user, "avatar--lg"),
        UI.el("div", {}, [
          UI.el("strong", { text: user.display_name }),
          UI.el("small", { text: user.email || "Chưa có email" }),
        ]),
      ]),
      UI.el("a", { href: "/ban-do", role: "menuitem", text: "🗺️ Bản đồ ký ức" }),
      UI.el("a", { href: "/accounts/profile.html", role: "menuitem", text: "👤 Hồ sơ cá nhân" }),
      user.role === "admin" ? UI.el("a", { href: "/admin/", role: "menuitem", text: "🛡️ Trang quản trị" }) : null,
      UI.el("button", { type: "button", role: "menuitem", className: "danger", text: "↪ Đăng xuất", onclick: logout }),
    ]);
    const trigger = UI.el(
      "button",
      { type: "button", className: "account-trigger", "aria-haspopup": "menu", "aria-expanded": "false" },
      [avatar(user), UI.el("span", { className: "account-menu__name", text: user.display_name }), UI.el("span", { className: "caret", text: "▾" })],
    );
    trigger.addEventListener("click", (event) => {
      event.stopPropagation();
      dropdown.hidden = !dropdown.hidden;
      trigger.setAttribute("aria-expanded", String(!dropdown.hidden));
    });
    document.addEventListener("click", (event) => {
      if (!menu.contains(event.target)) {
        dropdown.hidden = true;
        trigger.setAttribute("aria-expanded", "false");
      }
    });
    menu.replaceChildren(trigger, dropdown);
  }

  async function init() {
    if (!Api.getToken()) {
      renderGuest();
      return null;
    }
    try {
      const user = await Api.get("/api/auth/me");
      renderUser(user);
      return user;
    } catch (error) {
      if (error.status === 401 || error.status === 403) Api.setToken(null);
      renderGuest();
      return null;
    }
  }

  document.addEventListener("auth:expired", () => {
    if (currentUser) {
      renderGuest();
      UI.toast("Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại", "error");
    }
  });

  const ready = init();

  /* Thông báo sau khi chuyển trang (?notice=...) */
  const NOTICES = {
    registered: ["Đăng ký thành công", "success"],
    oauth: ["Đăng nhập thành công", "success"],
    need_email: ["Hãy bổ sung email trong hồ sơ để dùng chức năng quên mật khẩu", "info"],
  };
  ready.then(() => {
    const url = new URL(window.location.href);
    const notice = NOTICES[url.searchParams.get("notice")];
    if (notice) {
      UI.toast(notice[0], notice[1]);
      url.searchParams.delete("notice");
      history.replaceState(null, "", url.pathname + url.search);
    }
  });

  return {
    ready,
    avatar,
    refresh(user) {
      renderUser(user);
    },
    get user() {
      return currentUser;
    },
  };
})();
