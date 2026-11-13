/* Trang hồ sơ (US-ACC-006, US-ACC-007, FR-1.8): thông tin, ảnh đại diện, mật khẩu, ký ức + chuyến đi lọc theo thời gian. */
(async () => {
  let user = await AccountMenu.ready;
  if (!user) {
    window.location.replace("/accounts/login.html?next=/accounts/profile.html");
    return;
  }
  const page = document.getElementById("profile-page");
  let currentPage = 1;

  function renderHero() {
    document.getElementById("hero-avatar").replaceChildren(AccountMenu.avatar(user, "avatar--xl"));
    document.getElementById("hero-name").textContent = user.display_name;
    const joined = new Date(user.created_at).toLocaleDateString("vi-VN");
    document.getElementById("hero-meta").textContent = `${user.email || "Chưa có email"} · Tham gia ${joined}${user.role === "admin" ? " · Quản trị viên" : ""}`;
    document.getElementById("hero-bio").textContent = user.bio || "";
    document.getElementById("avatar-preview").replaceChildren(AccountMenu.avatar(user, "avatar--xl"));
    document.getElementById("avatar-remove").hidden = !user.avatar_url;
  }

  function fillForms() {
    const form = document.getElementById("profile-form");
    form.elements.display_name.value = user.display_name;
    form.elements.bio.value = user.bio || "";
    const email = form.elements.email;
    email.value = user.email || "";
    email.disabled = Boolean(user.email);
    document.getElementById("email-hint").textContent = user.email
      ? "Email dùng để đăng nhập và đặt lại mật khẩu, không thể đổi."
      : "Bổ sung email để dùng chức năng quên mật khẩu.";

    const hasPassword = user.has_password;
    document.getElementById("current-password-field").hidden = !hasPassword;
    document.getElementById("password-title").textContent = hasPassword ? "Đổi mật khẩu" : "Tạo mật khẩu";
    document.getElementById("password-intro").textContent = hasPassword
      ? "Sau khi đổi mật khẩu, mọi phiên đăng nhập khác sẽ bị đăng xuất."
      : "Tài khoản của bạn đang đăng nhập bằng mạng xã hội. Tạo mật khẩu để có thể đăng nhập bằng email.";
    document.getElementById("password-form").dataset.success = hasPassword ? "Đổi mật khẩu thành công" : "Tạo mật khẩu thành công";
    const names = { google: "Google", facebook: "Facebook" };
    document.getElementById("providers-text").textContent = user.providers.length
      ? `Đã liên kết: ${user.providers.map((item) => names[item] || item).join(", ")}.`
      : "Chưa liên kết tài khoản Google hoặc Facebook.";
  }

  async function loadStats() {
    try {
      const stats = await Api.get("/api/users/me/stats");
      const items = [
        [stats.memories, "Ký ức"],
        [stats.public_memories, "Công khai"],
        [stats.trips, "Chuyến đi"],
        [stats.places, "Tỉnh/thành đã đến"],
      ];
      document.getElementById("profile-stats").replaceChildren(
        ...items.map(([value, label]) =>
          UI.el("div", { className: "stat" }, [UI.el("div", { className: "stat__value", text: value }), UI.el("div", { className: "stat__label", text: label })]),
        ),
      );
    } catch (error) {
      UI.toast(error.message, "error");
    }
  }

  /* ---------- Ký ức theo thời gian (US-EXP-005) ---------- */
  const filterForm = document.getElementById("profile-filter");
  for (let month = 1; month <= 12; month += 1) {
    filterForm.elements.month.append(UI.el("option", { value: month, text: `Tháng ${month}` }));
  }

  async function loadYears() {
    const years = await Api.get("/api/memories/mine/years").catch(() => []);
    years.forEach((year) => filterForm.elements.year.append(UI.el("option", { value: year, text: `Năm ${year}` })));
  }

  async function loadMemories(pageNumber = 1) {
    currentPage = pageNumber;
    const filters = UI.formToJson(filterForm);
    const timeFiltered = Boolean(filters.year || filters.date_from || filters.date_to);
    const message = document.getElementById("filter-message");
    UI.showMessage(message, "");
    const list = document.getElementById("profile-memories");
    try {
      const data = await Api.get("/api/memories/mine", {
        query: { ...filters, page: pageNumber, page_size: 12, order: timeFiltered ? "asc" : "desc" },
      });
      document.getElementById("profile-status").textContent = data.total ? `${data.total} ký ức` : "";
      list.replaceChildren(
        ...(data.items.length
          ? data.items.map((memory) =>
              UI.memoryCard(memory, { showAuthor: false, showVisibility: true, onClick: () => (window.location.href = `/ban-do?memory=${memory.id}`) }),
            )
          : [UI.emptyState("🗺️", timeFiltered ? "Không có ký ức nào trong khoảng thời gian này" : "Bạn chưa có ký ức nào. Hãy ghim ký ức đầu tiên trên bản đồ!")]),
      );
      renderPagination(data);
    } catch (error) {
      UI.showMessage(message, error.message);
    }
  }

  function renderPagination(data) {
    const box = document.getElementById("profile-pagination");
    if (data.pages <= 1) {
      box.replaceChildren();
      return;
    }
    box.replaceChildren(
      UI.el("button", { type: "button", className: "button button--sm", text: "‹ Trước", disabled: data.page <= 1, onclick: () => loadMemories(data.page - 1) }),
      UI.el("span", { text: `Trang ${data.page}/${data.pages}` }),
      UI.el("button", { type: "button", className: "button button--sm", text: "Sau ›", disabled: data.page >= data.pages, onclick: () => loadMemories(data.page + 1) }),
    );
  }

  async function loadTrips() {
    const box = document.getElementById("profile-trips");
    const trips = await Api.get("/api/trips").catch(() => []);
    box.replaceChildren(
      ...(trips.length
        ? trips.map((trip) =>
            UI.el("a", { className: "trip-mini", href: `/ban-do?trip=${trip.id}` }, [
              UI.el("strong", { text: trip.name }),
              UI.el("small", {
                text: `${trip.memory_count} ký ức${trip.start_date ? ` · ${UI.formatDate(trip.start_date)} – ${UI.formatDate(trip.end_date)}` : ""}`,
              }),
            ]),
          )
        : [UI.emptyState("🧳", "Chưa có chuyến đi nào.")]),
    );
  }

  filterForm.addEventListener("submit", (event) => {
    event.preventDefault();
    loadMemories(1);
  });
  filterForm.addEventListener("reset", () => setTimeout(() => loadMemories(1), 0));

  /* ---------- Tab ---------- */
  const tabs = document.querySelectorAll(".profile-tabs .tab");
  function showTab(name) {
    tabs.forEach((tab) => tab.classList.toggle("is-active", tab.dataset.tab === name));
    document.querySelectorAll("[data-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.panel !== name;
    });
  }
  tabs.forEach((tab) => tab.addEventListener("click", () => showTab(tab.dataset.tab)));

  /* ---------- Sau khi lưu ---------- */
  function onSaved(event) {
    if (event.detail && event.detail.id) {
      user = event.detail;
    } else if (event.detail && event.detail.user) {
      user = event.detail.user;
    }
    AccountMenu.refresh(user);
    renderHero();
    fillForms();
  }
  document.getElementById("profile-form").addEventListener("accounts:saved", onSaved);
  document.getElementById("avatar-form").addEventListener("accounts:saved", (event) => {
    onSaved(event);
    event.currentTarget.reset();
  });
  document.getElementById("password-form").addEventListener("accounts:saved", onSaved);

  const avatarInput = document.querySelector('input[name="avatar"]');
  avatarInput.addEventListener("change", () => {
    const file = avatarInput.files[0];
    const message = avatarInput.form.querySelector(".form-message");
    UI.showMessage(message, "");
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      UI.showMessage(message, "Ảnh không được vượt quá 5 MB");
      avatarInput.value = "";
      return;
    }
    if (!/\.(jpe?g|png|heic)$/i.test(file.name)) {
      UI.showMessage(message, "Định dạng tệp không được hỗ trợ");
      avatarInput.value = "";
      return;
    }
    if (!/\.heic$/i.test(file.name)) {
      document.getElementById("avatar-preview").replaceChildren(UI.el("img", { className: "avatar avatar--xl", src: URL.createObjectURL(file), alt: "Xem trước" }));
    }
  });

  document.getElementById("avatar-remove").addEventListener("click", async () => {
    if (!(await UI.confirm({ title: "Gỡ ảnh đại diện?", message: "Ảnh đại diện hiện tại sẽ bị xóa.", confirmText: "Gỡ ảnh", danger: true }))) return;
    try {
      user = await Api.delete("/api/users/me/avatar");
      AccountMenu.refresh(user);
      renderHero();
      UI.toast("Đã gỡ ảnh đại diện", "success");
    } catch (error) {
      UI.toast(error.message, "error");
    }
  });

  renderHero();
  fillForms();
  page.hidden = false;
  if (new URLSearchParams(window.location.search).get("notice") === "need_email" || !user.email) {
    if (!user.email) showTab("info");
    if (new URLSearchParams(window.location.search).get("notice") === "need_email") {
      UI.toast("Tài khoản Facebook chưa có email. Vui lòng bổ sung email trong hồ sơ cá nhân để dùng chức năng quên mật khẩu.");
    }
  }
  loadStats();
  loadYears();
  loadMemories(1);
  loadTrips();
})();
