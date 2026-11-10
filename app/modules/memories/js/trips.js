/* M2 – Chuyến đi (US-MEM-009): danh sách, tạo/sửa/xóa, thêm/bỏ ký ức, lộ trình theo thời gian trên bản đồ. */
const Trips = (() => {
  let user = null;
  let openTripId = null;

  function summaryText(trip) {
    const range = trip.start_date
      ? trip.start_date === trip.end_date
        ? UI.formatDate(trip.start_date)
        : `${UI.formatDate(trip.start_date)} – ${UI.formatDate(trip.end_date)}`
      : "Chưa có ký ức";
    return `${trip.memory_count} ký ức · ${range}`;
  }

  async function loadList() {
    const list = document.getElementById("trip-list");
    if (!list || !user) return;
    try {
      const trips = await Api.get("/api/trips");
      list.replaceChildren(
        ...(trips.length
          ? trips.map((trip) =>
              UI.el("button", { type: "button", className: "trip-card", onclick: () => openTrip(trip.id) }, [
                UI.el("strong", { text: `🧳 ${trip.name}` }),
                UI.el("small", { text: summaryText(trip) }),
                trip.description ? UI.el("small", { text: trip.description }) : null,
              ]),
            )
          : [UI.emptyState("🧳", "Chưa có chuyến đi nào. Tạo chuyến đi rồi thêm các ký ức vào để xem lại hành trình.")]),
      );
    } catch (error) {
      list.replaceChildren(UI.emptyState("⚠️", error.message));
    }
  }

  function tripForm({ title, trip }) {
    return UI.modal((box, close) => {
      const name = UI.el("input", { type: "text", maxlength: 150, required: true, value: trip ? trip.name : "", autofocus: true, placeholder: "VD: Đà Lạt mùa săn mây 2025" });
      const description = UI.el("textarea", { rows: 3, maxlength: 500, placeholder: "Mô tả ngắn (không bắt buộc)" });
      description.value = trip && trip.description ? trip.description : "";
      const error = UI.el("p", { className: "form-message form-message--error", hidden: true });
      const form = UI.el("form", { className: "form" }, [
        UI.el("label", { className: "field" }, ["Tên chuyến đi", name]),
        UI.el("label", { className: "field" }, ["Mô tả", description]),
        error,
        UI.el("div", { className: "modal__actions" }, [
          UI.el("button", { type: "button", className: "button", text: "Hủy", onclick: () => close(null) }),
          UI.el("button", { type: "submit", className: "button button--primary", text: trip ? "Lưu" : "Tạo chuyến đi" }),
        ]),
      ]);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!name.value.trim()) {
          UI.showMessage(error, "Vui lòng nhập tên chuyến đi");
          return;
        }
        try {
          const body = { name: name.value.trim(), description: description.value.trim() };
          const saved = trip
            ? await Api.patch(`/api/trips/${trip.id}`, { body })
            : await Api.post("/api/trips", { body });
          close(saved);
        } catch (requestError) {
          UI.showMessage(error, requestError.message);
        }
      });
      box.append(UI.el("h3", { text: title }), form);
    });
  }

  async function createTrip() {
    const trip = await tripForm({ title: "Chuyến đi mới" });
    if (!trip) return;
    UI.toast("Đã tạo chuyến đi", "success");
    loadList();
    openTrip(trip.id);
  }

  async function addMemories(trip) {
    const data = await Api.get("/api/memories/mine", { query: { page_size: 50, order: "asc" } }).catch(() => ({ items: [] }));
    const inTrip = new Set(trip.memories.map((memory) => memory.id));
    const candidates = data.items.filter((memory) => !inTrip.has(memory.id));
    const ids = await UI.modal((box, close) => {
      const search = UI.el("input", { className: "input", type: "search", placeholder: "Lọc theo tiêu đề, địa điểm..." });
      const list = UI.el("div", { className: "check-list" });
      candidates.forEach((memory) =>
        list.append(
          UI.el("label", { dataset: { text: `${memory.title} ${memory.place_name}`.toLowerCase() } }, [
            UI.el("input", { type: "checkbox", value: memory.id }),
            UI.el("span", {}, [memory.title, UI.el("small", { text: `${UI.formatDate(memory.memory_date)} · ${memory.place_name}` })]),
          ]),
        ),
      );
      search.addEventListener("input", () => {
        const query = search.value.trim().toLowerCase();
        list.querySelectorAll("label").forEach((label) => {
          label.hidden = query && !label.dataset.text.includes(query);
        });
      });
      box.append(
        UI.el("h3", { text: `Thêm ký ức vào “${trip.name}”` }),
        candidates.length ? search : null,
        candidates.length ? list : UI.el("p", { text: "Tất cả ký ức của bạn đã nằm trong chuyến đi này (hoặc bạn chưa có ký ức nào)." }),
        UI.el("div", { className: "modal__actions" }, [
          UI.el("button", { type: "button", className: "button", text: "Hủy", onclick: () => close(null) }),
          candidates.length
            ? UI.el("button", {
                type: "button",
                className: "button button--primary",
                text: "Thêm",
                onclick: () => close([...list.querySelectorAll("input:checked")].map((input) => Number(input.value))),
              })
            : null,
        ]),
      );
    }, { wide: true });
    if (!ids || !ids.length) return;
    try {
      await Api.post(`/api/trips/${trip.id}/memories`, { body: { memory_ids: ids } });
      UI.toast(`Đã thêm ${ids.length} ký ức vào chuyến đi`, "success");
      loadList();
      openTrip(trip.id);
    } catch (error) {
      UI.toast(error.message, "error");
    }
  }

  async function removeMemory(trip, memory) {
    const ok = await UI.confirm({
      title: "Bỏ ký ức khỏi chuyến đi?",
      message: `“${memory.title}” chỉ bị bỏ khỏi chuyến đi, ký ức vẫn được giữ nguyên.`,
      confirmText: "Bỏ khỏi chuyến đi",
    });
    if (!ok) return;
    try {
      await Api.delete(`/api/trips/${trip.id}/memories/${memory.id}`);
      loadList();
      openTrip(trip.id);
    } catch (error) {
      UI.toast(error.message, "error");
    }
  }

  async function deleteTrip(trip) {
    const ok = await UI.confirm({
      title: "Xóa chuyến đi?",
      message: `Chuyến đi “${trip.name}” sẽ bị xóa. Các ký ức bên trong vẫn được giữ nguyên.`,
      confirmText: "Xóa chuyến đi",
      danger: true,
    });
    if (!ok) return;
    try {
      await Api.delete(`/api/trips/${trip.id}`);
      Shell.closeDrawer();
      UI.toast("Đã xóa chuyến đi, các ký ức vẫn được giữ nguyên", "success");
      loadList();
    } catch (error) {
      UI.toast(error.message, "error");
    }
  }

  async function openTrip(id) {
    if (!user) user = await AccountMenu.ready;
    if (!user) {
      UI.toast("Đăng nhập để xem chuyến đi", "error");
      return;
    }
    let trip;
    try {
      trip = await Api.get(`/api/trips/${id}`);
    } catch (error) {
      UI.toast(error.message, "error");
      Shell.setUrlParam("trip", null);
      return;
    }
    openTripId = trip.id;
    Shell.setUrlParam("trip", trip.id);
    Shell.selectTab("trips");

    const points = trip.memories.map((memory) => [memory.latitude, memory.longitude]);
    MemoryMap.drawRoute(points);
    MemoryMap.fitPoints(points);

    const timeline = UI.el("ol", { className: "timeline" });
    trip.memories.forEach((memory, index) => {
      timeline.append(
        UI.el("li", {}, [
          UI.el("span", { className: "timeline__num", text: index + 1 }),
          UI.memoryCard(memory, { showAuthor: false, showVisibility: true, onClick: () => Memories.openDetail(memory.id, { fly: true }) }),
          UI.el("button", { type: "button", className: "icon-button icon-button--round", title: "Bỏ khỏi chuyến đi", "aria-label": "Bỏ khỏi chuyến đi", text: "✕", onclick: () => removeMemory(trip, memory) }),
        ]),
      );
    });

    const body = UI.el("div", { className: "memory-detail" }, [
      UI.el("h1", { className: "memory-detail__title", text: trip.name }),
      UI.el("div", { className: "memory-detail__meta", text: summaryText(trip) }),
      trip.description ? UI.el("div", { className: "memory-content", text: trip.description }) : null,
      UI.el("div", { className: "panel-head", style: { marginBottom: "0" } }, [
        UI.el("div", { className: "section-label", text: "Hành trình theo thời gian" }),
        UI.el("button", { type: "button", className: "button button--soft button--sm", text: "+ Thêm ký ức", onclick: () => addMemories(trip) }),
      ]),
      trip.memories.length ? timeline : UI.emptyState("📍", "Chuyến đi chưa có ký ức nào."),
    ]);

    Shell.openDrawer({
      title: "Chuyến đi",
      body,
      footer: [
        UI.el("button", { type: "button", className: "button button--danger", text: "Xóa chuyến đi", onclick: () => deleteTrip(trip) }),
        UI.el("button", {
          type: "button",
          className: "button button--primary",
          text: "✏️ Đổi tên / mô tả",
          onclick: async () => {
            const saved = await tripForm({ title: "Sửa chuyến đi", trip });
            if (saved) {
              UI.toast("Đã cập nhật chuyến đi", "success");
              loadList();
              openTrip(trip.id);
            }
          },
        }),
      ],
      onClose: () => {
        openTripId = null;
        MemoryMap.clearRoute();
      },
    });
  }

  async function init() {
    user = await AccountMenu.ready;
    if (!user) {
      document.getElementById("trips-guest").hidden = false;
      return;
    }
    const button = document.getElementById("trip-new");
    button.hidden = false;
    button.addEventListener("click", createTrip);
    loadList();
  }

  UI.on("trip:open", ({ id }) => openTrip(id));
  UI.on("trips:changed", loadList);
  UI.on("memories:changed", () => {
    loadList();
  });
  init();

  return { openTrip, reload: loadList };
})();
