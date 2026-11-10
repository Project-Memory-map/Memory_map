/* M4 – Quản trị: ẩn/bỏ ẩn/xóa ký ức, khóa/mở khóa tài khoản (kèm lý do), nhật ký, thống kê. */
(async () => {
  const user = await AccountMenu.ready;
  if (!user || user.role !== "admin") {
    window.location.replace(user ? "/ban-do" : "/accounts/login.html?next=/admin/");
    return;
  }

  const page = document.querySelector(".admin-page");
  const tabs = document.querySelectorAll(".admin-tabs .tab");
  const panels = document.querySelectorAll(".admin-panel");
  const state = { memories: 1, users: 1, actions: 1 };
  const { el } = UI;

  function showTab(name) {
    tabs.forEach((tab) => tab.classList.toggle("is-active", tab.dataset.tab === name));
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.panel !== name;
    });
    load(name, 1);
  }
  tabs.forEach((tab) => tab.addEventListener("click", () => showTab(tab.dataset.tab)));

  function formQuery(name) {
    const form = document.querySelector(`.admin-search[data-target="${name}"]`);
    return UI.formToJson(form);
  }

  function emptyRow(colspan, text) {
    return el("tr", { className: "empty-row" }, el("td", { colspan, text }));
  }

  function pagination(name, data) {
    const box = document.getElementById(`admin-${name}-pagination`);
    if (data.pages <= 1) {
      box.replaceChildren(data.total ? el("span", { text: `${data.total} mục` }) : "");
      return;
    }
    box.replaceChildren(
      el("button", { type: "button", className: "button button--sm", text: "‹ Trước", disabled: data.page <= 1, onclick: () => load(name, data.page - 1) }),
      el("span", { text: `Trang ${data.page}/${data.pages} · ${data.total} mục` }),
      el("button", { type: "button", className: "button button--sm", text: "Sau ›", disabled: data.page >= data.pages, onclick: () => load(name, data.page + 1) }),
    );
  }

  async function loadStats() {
    try {
      const stats = await Api.get("/api/admin/stats");
      const items = [
        [stats.users, "Tài khoản"],
        [stats.locked_users, "Tài khoản bị khóa"],
        [stats.memories, "Ký ức"],
        [stats.public_memories, "Ký ức công khai"],
        [stats.hidden_memories, "Ký ức bị ẩn"],
        [stats.new_memories_7d, "Ký ức mới 7 ngày"],
      ];
      document.getElementById("admin-stats").replaceChildren(
        ...items.map(([value, label]) => el("div", { className: "stat" }, [el("div", { className: "stat__value", text: value }), el("div", { className: "stat__label", text: label })])),
      );
    } catch (error) {
      UI.toast(error.message, "error");
    }
  }

  async function run(request, success) {
    try {
      await request();
      UI.toast(success, "success");
      loadStats();
      return true;
    } catch (error) {
      UI.toast(error.message, "error");
      return false;
    }
  }

  /* ---------- Ký ức công khai (US-ADM-001, 002) ---------- */
  async function memoryAction(memory, action) {
    if (action === "unhide") {
      const ok = await UI.confirm({ title: "Bỏ ẩn ký ức?", message: `“${memory.title}” sẽ hiển thị lại trên bản đồ cộng đồng.`, confirmText: "Bỏ ẩn" });
      if (!ok) return;
      if (await run(() => Api.post(`/api/admin/memories/${memory.id}/unhide`, { body: {} }), "Đã bỏ ẩn ký ức")) load("memories", state.memories);
      return;
    }
    const reason = await UI.prompt({
      title: action === "hide" ? "Ẩn ký ức vi phạm" : "Xóa ký ức vi phạm nghiêm trọng",
      message: `“${memory.title}” của ${memory.author.display_name}. ${action === "hide" ? "Chủ ký ức vẫn thấy ký ức kèm trạng thái đã bị ẩn." : "Ký ức sẽ bị xóa khỏi mọi màn hình."}`,
      placeholder: "Lý do (bắt buộc, được ghi vào nhật ký)",
      confirmText: action === "hide" ? "Ẩn ký ức" : "Xóa ký ức",
      danger: true,
    });
    if (reason === null) return;
    const label = action === "hide" ? "Đã ẩn ký ức" : "Đã xóa ký ức";
    if (await run(() => Api.post(`/api/admin/memories/${memory.id}/${action}`, { body: { reason } }), label)) load("memories", state.memories);
  }

  function memoryRow(memory) {
    const hidden = memory.status === "hidden";
    return el("tr", {}, [
      el("td", {}, el("div", { className: "cell-title" }, [
        memory.cover_url ? el("img", { src: memory.cover_url, alt: "" }) : el("span", { className: "thumb-empty", text: "📍" }),
        el("div", {}, [
          el("a", { href: `/ban-do?memory=${memory.id}`, target: "_blank", rel: "noopener" }, el("strong", { text: memory.title })),
          el("small", { text: memory.place_name }),
        ]),
      ])),
      el("td", {}, [
        el("span", { text: memory.author.display_name }),
        memory.author.status === "locked" ? el("span", { className: "badge badge--locked", style: { marginLeft: "6px" }, text: "TK bị khóa" }) : null,
      ]),
      el("td", { text: UI.formatDate(memory.memory_date) }),
      el("td", {}, el("span", { className: `badge ${hidden ? "badge--hidden" : "badge--active"}`, text: hidden ? "Đã ẩn" : "Đang hiển thị" })),
      el("td", { className: "actions" }, [
        el("button", { type: "button", className: "button button--sm", text: hidden ? "Bỏ ẩn" : "Ẩn", onclick: () => memoryAction(memory, hidden ? "unhide" : "hide") }),
        el("button", { type: "button", className: "button button--sm button--danger", text: "Xóa", onclick: () => memoryAction(memory, "delete") }),
      ]),
    ]);
  }

  /* ---------- Tài khoản (US-ADM-003) ---------- */
  async function userAction(account, action) {
    if (action === "unlock") {
      const ok = await UI.confirm({ title: "Mở khóa tài khoản?", message: `${account.display_name} sẽ đăng nhập lại được; ký ức và chuyến đi vẫn còn nguyên.`, confirmText: "Mở khóa" });
      if (!ok) return;
      if (await run(() => Api.post(`/api/admin/users/${account.id}/unlock`, { body: {} }), "Đã mở khóa tài khoản")) load("users", state.users);
      return;
    }
    const reason = await UI.prompt({
      title: "Khóa tài khoản vi phạm",
      message: `${account.display_name} (${account.email || "không có email"}) sẽ bị đăng xuất ngay và không đăng nhập được. Toàn bộ ký ức công khai của họ bị ẩn khỏi cộng đồng cho tới khi mở khóa.`,
      placeholder: "Lý do (bắt buộc, được ghi vào nhật ký)",
      confirmText: "Khóa tài khoản",
      danger: true,
    });
    if (reason === null) return;
    if (await run(() => Api.post(`/api/admin/users/${account.id}/lock`, { body: { reason } }), "Đã khóa tài khoản")) load("users", state.users);
  }

  function userRow(account) {
    const locked = account.status === "locked";
    const isSelf = account.id === user.id;
    return el("tr", {}, [
      el("td", {}, [el("strong", { text: account.display_name }), isSelf ? el("small", { className: "muted", text: " (bạn)" }) : null]),
      el("td", { text: account.email || "—" }),
      el("td", {}, el("span", { className: `badge ${account.role === "admin" ? "badge--admin" : ""}`, text: account.role === "admin" ? "Quản trị viên" : "Người dùng" })),
      el("td", { text: account.memory_count }),
      el("td", {}, el("span", { className: `badge ${locked ? "badge--locked" : "badge--active"}`, text: locked ? "locked" : "active" })),
      el("td", { className: "actions" }, [
        locked
          ? el("button", { type: "button", className: "button button--sm", text: "Mở khóa", onclick: () => userAction(account, "unlock") })
          : el("button", {
              type: "button",
              className: "button button--sm button--danger",
              text: "Khóa",
              title: isSelf ? "Bạn không thể khóa chính tài khoản của mình" : "",
              onclick: () => (isSelf ? UI.toast("Bạn không thể khóa chính tài khoản của mình", "error") : userAction(account, "lock")),
            }),
      ]),
    ]);
  }

  /* ---------- Nhật ký ---------- */
  function actionRow(item) {
    const link = item.target_type === "memory" ? el("a", { href: `/ban-do?memory=${item.target_id}`, target: "_blank", rel: "noopener", text: item.target_label }) : el("span", { text: item.target_label });
    return el("tr", {}, [
      el("td", { text: UI.formatDateTime(item.created_at) }),
      el("td", { text: item.admin.display_name }),
      el("td", {}, el("span", { className: "badge", text: item.action_label })),
      el("td", {}, [el("small", { className: "muted", text: item.target_type === "memory" ? "Ký ức: " : "Tài khoản: " }), link]),
      el("td", { className: "reason", text: item.reason || "—" }),
    ]);
  }

  const CONFIG = {
    memories: { url: "/api/admin/memories", body: "admin-memories", row: memoryRow, cols: 5, empty: "Không có ký ức công khai phù hợp" },
    users: { url: "/api/admin/users", body: "admin-users", row: userRow, cols: 6, empty: "Không có tài khoản phù hợp" },
    actions: { url: "/api/admin/actions", body: "admin-actions", row: actionRow, cols: 5, empty: "Chưa có thao tác nào" },
  };

  async function load(name, pageNumber = 1) {
    state[name] = pageNumber;
    const config = CONFIG[name];
    const body = document.getElementById(config.body);
    body.replaceChildren(emptyRow(config.cols, "Đang tải..."));
    try {
      const data = await Api.get(config.url, { query: { ...formQuery(name), page: pageNumber, page_size: 20 } });
      body.replaceChildren(...(data.items.length ? data.items.map(config.row) : [emptyRow(config.cols, config.empty)]));
      pagination(name, data);
    } catch (error) {
      body.replaceChildren(emptyRow(config.cols, error.message));
    }
  }

  document.querySelectorAll(".admin-search").forEach((form) =>
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      load(form.dataset.target, 1);
    }),
  );

  page.hidden = false;
  loadStats();
  load("memories", 1);
})();
