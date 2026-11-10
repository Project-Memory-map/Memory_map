/* M2 – Ký ức: ghim xanh của tôi, danh sách + bộ lọc thời gian, chi tiết, form tạo/sửa (ảnh, video, hashtag). */
const Memories = (() => {
  const MAX_IMAGES = 10;
  const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
  const MAX_VIDEO_BYTES = 50 * 1024 * 1024;
  const IMAGE_RE = /\.(jpe?g|png|webp|gif)$/i;
  const IMAGE_MIME = { jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", webp: "image/webp", gif: "image/gif" };
  const VIDEO_RE = /\.(mp4|mov)$/i;
  const VIDEO_MIME = { mp4: "video/mp4", mov: "video/quicktime" };
  const TAG_RE = /^[\p{L}\p{N}_]{1,30}$/u;

  const layer = MemoryMap.createLayer();
  const state = { user: null, filters: {}, tags: new Set(), page: 1, myIds: new Set(), trips: [] };

  function createImageLoader(objectUrls) {
    const cache = new Map();
    return (url, requiresAuth) => {
      if (!requiresAuth) return Promise.resolve(url);
      if (!cache.has(url)) {
        cache.set(url, (async () => {
          const token = Api.getToken();
          const response = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
          if (!response.ok) {
            if (response.status === 401) {
              Api.setToken(null);
              document.dispatchEvent(new CustomEvent("auth:expired"));
            }
            throw new Error("Không thể tải ảnh của ký ức");
          }
          const objectUrl = URL.createObjectURL(await response.blob());
          objectUrls.push(objectUrl);
          return objectUrl;
        })());
      }
      return cache.get(url);
    };
  }

  async function loadMemoryVideo(memory) {
    memory.media = memory.media || [];
    try {
      const video = await Api.get(`/api/memories/${memory.id}/video`);
      memory.media = [...memory.media.filter((item) => item.type !== "video"), ...(video ? [video] : [])];
    } catch (error) {
      /* Keep the video data returned by the existing memory detail API. */
    }
  }

  function videoStreamUrl(url) {
    try {
      const parsed = new URL(url, window.location.origin);
      if (parsed.origin === window.location.origin && /^\/api\/media\/\d+$/.test(parsed.pathname)) {
        parsed.pathname += "/stream";
      }
      return `${parsed.pathname}${parsed.search}${parsed.hash}`;
    } catch (error) {
      return url;
    }
  }

  async function loadProtectedVideo(url, objectUrls) {
    const token = Api.getToken();
    const response = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (!response.ok) {
      if (response.status === 401) {
        Api.setToken(null);
        document.dispatchEvent(new CustomEvent("auth:expired"));
      }
      throw new Error("Không thể tải video của ký ức");
    }
    const objectUrl = URL.createObjectURL(await response.blob());
    objectUrls.push(objectUrl);
    return objectUrl;
  }

  /* ---------- Ghim của tôi (xanh) ---------- */
  function pinKind(pin) {
    if (pin.status === "hidden") return "mine-hidden";
    return pin.visibility === "private" ? "mine-private" : "mine";
  }

  function buildPopup(pin) {
    return UI.el("div", { className: "pin-popup" }, [
      UI.el("span", {
        className: `badge pin-popup__badge ${pin.visibility === "public" ? "badge--public" : "badge--private"}`,
        text: pin.status === "hidden" ? "Bị quản trị viên ẩn" : pin.visibility === "public" ? "Công khai" : "Riêng tư",
      }),
      UI.el("h3", { text: pin.title }),
      UI.el("p", { text: pin.place_name }),
      UI.el("p", { text: UI.formatDate(pin.memory_date) }),
      UI.el("button", { type: "button", className: "button button--primary button--sm", text: "Xem chi tiết", onclick: () => openDetail(pin.id) }),
    ]);
  }

  async function loadPins() {
    if (!state.user) {
      layer.clearLayers();
      return;
    }
    try {
      const pins = await Api.get("/api/memories/mine/pins", { query: state.filters });
      layer.clearLayers();
      pins.forEach((pin) => MemoryMap.addPin(layer, pin.latitude, pin.longitude, pinKind(pin), () => buildPopup(pin), pin.title));
      if (!Object.keys(state.filters).length) {
        state.myIds = new Set(pins.map((pin) => pin.id));
        UI.emit("mine:loaded", state.myIds);
      }
      return pins;
    } catch (error) {
      UI.toast(error.message, "error");
      return [];
    }
  }

  /* ---------- Danh sách + bộ lọc (US-EXP-005, FR-3.4) ---------- */
  function panelEl(id) {
    return document.getElementById(id);
  }

  function readFilters() {
    const data = UI.formToJson(panelEl("mine-filter"));
    const filters = {};
    Object.entries(data).forEach(([key, value]) => {
      if (value) filters[key] = value;
    });
    if (state.tags.size) filters.hashtags = [...state.tags].join(" ");
    return filters;
  }

  async function loadList(page = 1) {
    state.page = page;
    const list = panelEl("mine-list");
    const status = panelEl("mine-status");
    const message = panelEl("mine-filter").querySelector(".form-message");
    UI.showMessage(message, "");
    if (page === 1) list.replaceChildren(UI.el("div", { className: "empty-state" }, UI.el("span", { className: "spinner" })));
    const timeFiltered = Boolean(state.filters.year || state.filters.date_from || state.filters.date_to);
    try {
      const data = await Api.get("/api/memories/mine", {
        query: { ...state.filters, page, page_size: 20, order: timeFiltered ? "asc" : "desc" },
      });
      if (page === 1) list.replaceChildren();
      data.items.forEach((memory) =>
        list.append(UI.memoryCard(memory, { showAuthor: false, showVisibility: true, onClick: () => openDetail(memory.id, { fly: true }) })),
      );
      const filtered = Object.keys(state.filters).length > 0;
      status.textContent = data.total
        ? `${data.total} ký ức${filtered ? " phù hợp bộ lọc" : ""}${timeFiltered ? " · xếp từ cũ đến mới" : ""}`
        : "";
      if (!data.total) {
        list.replaceChildren(
          filtered
            ? UI.emptyState("🔎", "Không có ký ức nào phù hợp bộ lọc")
            : UI.emptyState("🗺️", "Bạn chưa có ký ức nào. Nhấp đúp lên bản đồ để ghim ký ức đầu tiên!"),
        );
      }
      panelEl("mine-more").hidden = data.page >= data.pages;
    } catch (error) {
      UI.showMessage(message, error.message);
      if (page === 1) list.replaceChildren();
    }
  }

  async function loadFilterOptions() {
    const form = panelEl("mine-filter");
    const [years, tags] = await Promise.all([
      Api.get("/api/memories/mine/years").catch(() => []),
      Api.get("/api/memories/mine/hashtags").catch(() => []),
    ]);
    const yearSelect = form.elements.year;
    const selectedYear = yearSelect.value;
    yearSelect.replaceChildren(UI.el("option", { value: "", text: "Mọi năm" }), ...years.map((year) => UI.el("option", { value: year, text: year })));
    yearSelect.value = selectedYear;
    const box = panelEl("mine-tags");
    box.replaceChildren(
      ...(tags.length
        ? tags.slice(0, 30).map((tag) => {
            const chip = UI.el("button", { type: "button", className: `chip${state.tags.has(tag.name) ? " is-active" : ""}` }, [
              `#${tag.name}`,
              UI.el("span", { className: "chip__count", text: tag.count }),
            ]);
            chip.addEventListener("click", () => {
              if (state.tags.has(tag.name)) state.tags.delete(tag.name);
              else state.tags.add(tag.name);
              chip.classList.toggle("is-active");
              applyFilters();
            });
            return chip;
          })
        : [UI.el("span", { className: "muted", text: "Chưa có hashtag" })]),
    );
  }

  function applyFilters() {
    state.filters = readFilters();
    loadList(1);
    loadPins().then((pins) => {
      if (pins && pins.length && Object.keys(state.filters).length) {
        MemoryMap.fitPoints(pins.map((pin) => [pin.latitude, pin.longitude]));
      }
    });
  }

  async function initPanel() {
    const form = panelEl("mine-filter");
    for (let month = 1; month <= 12; month += 1) {
      form.elements.month.append(UI.el("option", { value: month, text: `Tháng ${month}` }));
    }
    if (!state.user) {
      panelEl("mine-guest").hidden = false;
      panelEl("mine-subtitle").textContent = "Ghim xanh trên bản đồ là ký ức của bạn.";
      return;
    }
    panelEl("mine-content").hidden = false;
    panelEl("mine-new").hidden = false;
    panelEl("mine-new").addEventListener("click", () => openForm({}));
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      applyFilters();
    });
    form.addEventListener("reset", () =>
      setTimeout(() => {
        state.tags.clear();
        form.querySelectorAll(".chip.is-active").forEach((chip) => chip.classList.remove("is-active"));
        applyFilters();
      }, 0),
    );
    form.elements.year.addEventListener("change", () => {
      if (!form.elements.year.value) form.elements.month.value = "";
    });
    panelEl("mine-more").addEventListener("click", () => loadList(state.page + 1));
    loadFilterOptions();
    loadList(1);
  }

  async function refreshAll() {
    if (!state.user) return;
    loadPins();
    loadList(1);
    loadFilterOptions();
    UI.emit("memories:changed");
  }

  /* ---------- Chi tiết ký ức (US-MEM-005) ---------- */
  async function openDetail(id, { fly = false } = {}) {
    MemoryMap.closePopup();
    let memory;
    try {
      memory = await Api.get(`/api/memories/${id}`);
    } catch (error) {
      UI.toast(error.status === 404 ? "Không tìm thấy ký ức" : error.message, "error");
      Shell.setUrlParam("memory", null);
      return;
    }
    memory.media = memory.media || [];
    try {
      const imageRows = await Api.get(`/api/memories/${id}/images`);
      memory.media = [...memory.media.filter((item) => item.type !== "image"), ...imageRows];
    } catch (error) {
      /* Keep the media returned by the existing memory detail API as a fallback. */
    }
    await loadMemoryVideo(memory);
    Shell.setUrlParam("memory", memory.id);
    if (fly) MemoryMap.flyTo(memory.latitude, memory.longitude, 13);

    const images = memory.media.filter((item) => item.type === "image");
    const video = memory.media.find((item) => item.type === "video");
    const body = UI.el("article", { className: "memory-detail" });
    const videoObjectUrls = [];

    if (memory.is_owner && memory.hidden_by_admin) {
      body.append(UI.el("div", { className: "notice-banner notice-banner--warning", text: "⚠️ Đã bị quản trị viên ẩn — ký ức này không còn hiển thị trên bản đồ cộng đồng." }));
    } else if (memory.hidden_by_admin) {
      body.append(UI.el("div", { className: "notice-banner notice-banner--warning", text: "Ký ức đang bị ẩn khỏi cộng đồng." }));
    }

    const meta = UI.el("div", { className: "memory-detail__meta" }, [
      UI.el("span", { text: `🗓️ ${UI.formatDate(memory.memory_date)}` }),
      UI.el("span", {
        className: `badge ${memory.visibility === "public" ? "badge--public" : "badge--private"}`,
        text: memory.visibility === "public" ? "🌏 Công khai" : "🔒 Riêng tư",
      }),
      memory.region ? UI.el("span", { className: "badge", text: memory.region.name }) : null,
    ]);
    body.append(
      UI.el("h1", { className: "memory-detail__title", text: memory.title }),
      meta,
      UI.el("div", { className: "memory-detail__place" }, [UI.el("span", { text: "📍" }), UI.el("span", { text: memory.place_name })]),
    );

    const imageObjectUrls = [];
    if (images.length) {
      const gallery = UI.el("div", { className: `gallery gallery--${Math.min(images.length, 3)}` });
      const loadImage = createImageLoader(imageObjectUrls);
      const requiresAuth = memory.visibility !== "public" || memory.status !== "active";
      images.forEach((item, index) => {
        const image = UI.el("img", { alt: `Ảnh ${index + 1} của ký ức`, loading: "lazy" });
        loadImage(item.thumb_url || item.url, requiresAuth).then((url) => { image.src = url; }).catch(() => {});
        gallery.append(
          UI.el("button", {
            type: "button",
            "aria-label": `Xem ảnh ${index + 1}`,
            onclick: async () => {
              try {
                UI.lightbox(await Promise.all(images.map((imageItem) => loadImage(imageItem.url, requiresAuth))), index);
              } catch (error) {
                UI.toast(error.message, "error");
              }
            },
          }, [
            image,
          ]),
        );
      });
      body.append(gallery);
    }
    if (video) {
      const player = UI.el("video", { className: "memory-video", controls: true, preload: "metadata", playsinline: true });
      const requiresAuth = memory.visibility !== "public" || memory.status !== "active";
      const source = videoStreamUrl(video.url);
      if (requiresAuth) {
        loadProtectedVideo(source, videoObjectUrls)
          .then((url) => {
            if (player.isConnected) player.src = url;
            else {
              URL.revokeObjectURL(url);
              const objectUrlIndex = videoObjectUrls.indexOf(url);
              if (objectUrlIndex >= 0) videoObjectUrls.splice(objectUrlIndex, 1);
            }
          })
          .catch((error) => UI.toast(error.message, "error"));
      } else {
        player.src = source;
      }
      body.append(player);
    }

    body.append(
      UI.el("div", {}, [
        UI.el("div", { className: "section-label", text: "Câu chuyện" }),
        UI.el("div", { className: `memory-content${memory.content ? "" : " is-empty"}`, text: memory.content || "Chưa có nội dung." }),
      ]),
    );

    if (memory.hashtags.length) {
      const chips = UI.el("div", { className: "chips" });
      memory.hashtags.forEach((tag) => {
        const isAi = memory.hashtag_sources && memory.hashtag_sources[tag] === "ai";
        chips.append(
          UI.el("button", {
            type: "button",
            className: `chip${isAi ? " chip--ai" : ""}`,
            title: isAi ? "Hashtag gợi ý bằng AI" : "Lọc ký ức công khai theo hashtag này",
            text: `#${tag}`,
            onclick: () => UI.emit("explore:hashtag", tag),
          }),
        );
      });
      body.append(UI.el("div", {}, [UI.el("div", { className: "section-label", text: "Hashtag" }), chips]));
    }

    if (memory.is_owner) {
      const trips = UI.el("div", { className: "chips" });
      memory.trips.forEach((trip) =>
        trips.append(UI.el("button", { type: "button", className: "chip", text: `🧳 ${trip.name}`, onclick: () => UI.emit("trip:open", { id: trip.id }) })),
      );
      trips.append(UI.el("button", { type: "button", className: "chip", text: "+ Thêm vào chuyến đi", onclick: () => pickTrips(memory) }));
      body.append(UI.el("div", {}, [UI.el("div", { className: "section-label", text: "Chuyến đi" }), trips]));
    }

    const author = memory.author;
    body.append(
      UI.el("div", { className: "memory-detail__author" }, [
        AccountMenu.avatar(author),
        UI.el("div", {}, [
          UI.el("strong", { text: memory.is_owner ? `${author.display_name} (bạn)` : author.display_name }),
          UI.el("small", { text: `Cập nhật ${UI.formatDateTime(memory.updated_at)}` }),
        ]),
      ]),
    );

    const footer = [];
    const locateButton = UI.el("button", { type: "button", className: "button button--ghost", text: "🗺️ Trên bản đồ", onclick: () => MemoryMap.flyTo(memory.latitude, memory.longitude, 15) });
    if (memory.is_owner) {
      footer.push(
        UI.el("button", { type: "button", className: "button button--danger", text: "Xóa", onclick: () => removeMemory(memory) }),
        UI.el("button", {
          type: "button",
          className: "button",
          text: memory.visibility === "public" ? "🔒 Chuyển riêng tư" : "🌏 Công khai",
          onclick: () => toggleVisibility(memory),
        }),
        UI.el("button", { type: "button", className: "button button--primary", text: "✏️ Sửa", onclick: () => openForm({ memory }) }),
      );
    } else if (state.user && state.user.role === "admin") {
      footer.push(
        locateButton,
        UI.el("button", { type: "button", className: "button button--danger", text: "Xóa (QTV)", onclick: () => adminAction(memory, "delete") }),
        UI.el("button", {
          type: "button",
          className: "button",
          text: memory.hidden_by_admin ? "Bỏ ẩn" : "Ẩn (QTV)",
          onclick: () => adminAction(memory, memory.hidden_by_admin ? "unhide" : "hide"),
        }),
      );
    } else {
      footer.push(locateButton);
    }

    Shell.openDrawer({
      title: memory.is_owner ? "Ký ức của bạn" : "Ký ức",
      body,
      footer,
      actions: memory.is_owner ? [] : [],
      onClose: () => {
        imageObjectUrls.forEach((url) => URL.revokeObjectURL(url));
        videoObjectUrls.forEach((url) => URL.revokeObjectURL(url));
      },
    });
  }

  async function toggleVisibility(memory) {
    const target = memory.visibility === "public" ? "private" : "public";
    if (target === "public") {
      const ok = await UI.confirm({
        title: "Công khai ký ức?",
        message: "Mọi người (kể cả khách chưa đăng nhập) sẽ thấy nội dung, ảnh và video của ký ức này trên bản đồ cộng đồng. Bạn có thể chuyển về riêng tư bất cứ lúc nào.",
        confirmText: "Công khai",
      });
      if (!ok) return;
    }
    try {
      await Api.patch(`/api/memories/${memory.id}/visibility`, { body: { visibility: target } });
      UI.toast(target === "public" ? "Ký ức đã chuyển sang công khai" : "Ký ức đã chuyển về riêng tư", "success");
      refreshAll();
      openDetail(memory.id);
    } catch (error) {
      UI.toast(error.message, "error");
    }
  }

  async function removeMemory(memory) {
    const ok = await UI.confirm({
      title: "Xóa ký ức này?",
      message: `“${memory.title}” cùng ảnh và video sẽ bị xóa khỏi bản đồ, danh sách và các chuyến đi. Thao tác này không thể hoàn tác.`,
      confirmText: "Xóa ký ức",
      danger: true,
    });
    if (!ok) return;
    try {
      await Api.delete(`/api/memories/${memory.id}`);
      Shell.closeDrawer();
      UI.toast("Đã xóa ký ức", "success");
      refreshAll();
    } catch (error) {
      UI.toast(error.message, "error");
    }
  }

  async function adminAction(memory, action) {
    let reason = "";
    if (action === "unhide") {
      if (!(await UI.confirm({ title: "Bỏ ẩn ký ức?", message: "Ký ức sẽ hiển thị lại trên bản đồ cộng đồng.", confirmText: "Bỏ ẩn" }))) return;
    } else {
      reason = await UI.prompt({
        title: action === "hide" ? "Ẩn ký ức vi phạm" : "Xóa ký ức vi phạm",
        message: action === "hide" ? "Ký ức sẽ bị ẩn khỏi cộng đồng, chủ ký ức vẫn thấy." : "Ký ức sẽ bị xóa vĩnh viễn khỏi hệ thống.",
        placeholder: "Lý do (bắt buộc, được ghi vào nhật ký)",
        confirmText: action === "hide" ? "Ẩn" : "Xóa",
        danger: true,
      });
      if (reason === null) return;
    }
    try {
      await Api.post(`/api/admin/memories/${memory.id}/${action}`, { body: { reason } });
      UI.toast(action === "hide" ? "Đã ẩn ký ức" : action === "unhide" ? "Đã bỏ ẩn ký ức" : "Đã xóa ký ức", "success");
      UI.emit("memories:changed");
      if (action === "delete") Shell.closeDrawer();
      else openDetail(memory.id);
    } catch (error) {
      UI.toast(error.message, "error");
    }
  }

  async function pickTrips(memory) {
    const trips = await Api.get("/api/trips").catch(() => []);
    const current = new Set(memory.trips.map((trip) => trip.id));
    const result = await UI.modal((box, close) => {
      const list = UI.el("div", { className: "check-list" });
      trips.forEach((trip) => {
        list.append(
          UI.el("label", {}, [
            UI.el("input", { type: "checkbox", value: trip.id, checked: current.has(trip.id) }),
            UI.el("span", {}, [trip.name, UI.el("small", { text: `${trip.memory_count} ký ức` })]),
          ]),
        );
      });
      const newName = UI.el("input", { className: "input", type: "text", maxlength: 150, placeholder: "Tên chuyến đi mới (không bắt buộc)" });
      box.append(
        UI.el("h3", { text: "Thêm vào chuyến đi" }),
        trips.length ? list : UI.el("p", { text: "Bạn chưa có chuyến đi nào — nhập tên để tạo mới." }),
        newName,
        UI.el("div", { className: "modal__actions" }, [
          UI.el("button", { type: "button", className: "button", text: "Hủy", onclick: () => close(null) }),
          UI.el("button", {
            type: "button",
            className: "button button--primary",
            text: "Lưu",
            onclick: () => close({ ids: [...list.querySelectorAll("input:checked")].map((input) => Number(input.value)), name: newName.value.trim() }),
          }),
        ]),
      );
    });
    if (!result) return;
    try {
      const ids = result.ids;
      if (result.name) {
        const trip = await Api.post("/api/trips", { body: { name: result.name } });
        ids.push(trip.id);
      }
      const formData = new FormData();
      formData.append("trip_ids", ids.join(","));
      await Api.patch(`/api/memories/${memory.id}`, { formData });
      UI.toast("Đã cập nhật chuyến đi của ký ức", "success");
      UI.emit("trips:changed");
      openDetail(memory.id);
    } catch (error) {
      UI.toast(error.message, "error");
    }
  }

  /* ---------- Form tạo / sửa (US-MEM-001..004, 006, 010) ---------- */
  function parseTags(raw) {
    const tags = [];
    for (const part of (raw || "").split(/[\s,;]+/)) {
      const tag = part.trim().replace(/^#+/, "").normalize("NFC").toLowerCase();
      if (!tag) continue;
      if (!TAG_RE.test(tag)) return { error: "Hashtag chỉ gồm chữ, số, dấu gạch dưới (tối đa 30 ký tự)", tags };
      if (!tags.includes(tag)) tags.push(tag);
    }
    if (tags.length > 10) return { error: "Mỗi ký ức tối đa 10 hashtag", tags };
    return { error: "", tags };
  }

  function uploadWithProgress(method, url, formData, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open(method, url);
      const token = Api.getToken();
      if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      xhr.setRequestHeader("Accept", "application/json");
      xhr.upload.addEventListener("progress", (event) => {
        if (event.lengthComputable) onProgress(event.loaded / event.total);
      });
      xhr.addEventListener("load", () => {
        let result = {};
        try {
          result = JSON.parse(xhr.responseText);
        } catch (error) {
          result = { message: xhr.status === 413 ? "Tệp tải lên quá lớn" : "Phản hồi không hợp lệ từ máy chủ" };
        }
        if (xhr.status >= 200 && xhr.status < 300) resolve(result.data);
        else {
          if (xhr.status === 401) Api.setToken(null);
          const error = new Error(result.message || "Đã có lỗi xảy ra");
          error.status = xhr.status;
          reject(error);
        }
      });
      xhr.addEventListener("error", () => reject(new Error("Không kết nối được máy chủ, vui lòng kiểm tra mạng")));
      xhr.send(formData);
    });
  }

  async function requireLogin(message) {
    const user = await AccountMenu.ready;
    if (user) return user;
    const ok = await UI.confirm({
      title: "Cần đăng nhập",
      message: message || "Bạn cần đăng nhập để ghim ký ức tại vị trí này.",
      confirmText: "Đăng nhập",
      cancelText: "Để sau",
    });
    if (ok) window.location.href = `/accounts/login.html?next=${encodeURIComponent("/ban-do")}`;
    return null;
  }

  async function openForm({ memory = null, latitude, longitude, place_name } = {}) {
    if (!(await requireLogin())) return;
    const editing = Boolean(memory);
    if (editing) {
      memory.media = memory.media || [];
      try {
        const imageRows = await Api.get(`/api/memories/${memory.id}/images`);
        memory.media = [...memory.media.filter((item) => item.type !== "image"), ...imageRows];
      } catch (error) {
        /* Keep existing image data returned by the memory detail API. */
      }
      await loadMemoryVideo(memory);
    }
    const container = UI.el("div");
    container.append(document.getElementById("memory-form-template").content.cloneNode(true));
    const form = container.querySelector("#memory-form");
    const $ = (selector) => container.querySelector(selector);
    const message = form.querySelector(".form-message");

    const local = {
      newImages: [],
      existingImages: editing ? memory.media.filter((item) => item.type === "image") : [],
      originalImageOrder: editing ? memory.media.filter((item) => item.type === "image").map((item) => item.id) : [],
      removedIds: new Set(),
      existingVideo: editing ? memory.media.find((item) => item.type === "video") || null : null,
      newVideo: null,
      removeVideo: false,
      aiTags: new Set(editing ? Object.entries(memory.hashtag_sources || {}).filter(([, source]) => source === "ai").map(([name]) => name) : []),
      placeAuto: false,
      previewUrls: [],
      videoObjectUrls: [],
    };
    let savedMemory = null;
    let imageUploadSaved = false;
    let videoUploadSaved = false;

    /* --- vị trí --- */
    function setLocation(lat, lng, { reverse = true, fly = true } = {}) {
      form.elements.latitude.value = lat.toFixed(6);
      form.elements.longitude.value = lng.toFixed(6);
      $("#memory-coords").textContent = `Tọa độ: ${lat.toFixed(5)}, ${lng.toFixed(5)} · kéo ghim tím để chỉnh`;
      $("#location-box").classList.remove("is-missing");
      MemoryMap.setTempMarker(lat, lng, (position) => setLocation(position.latitude, position.longitude, { fly: false }));
      if (fly) MemoryMap.flyTo(lat, lng, 15);
      if (reverse && (!form.elements.place_name.value.trim() || local.placeAuto)) reverseFill(lat, lng);
    }

    async function reverseFill(lat, lng) {
      const fallback = `Vị trí ${lat.toFixed(5)}, ${lng.toFixed(5)}`;
      try {
        const place = await Api.get("/api/geocode/reverse", { query: { lat, lng } });
        form.elements.place_name.value = place ? place.name : fallback;
      } catch (error) {
        form.elements.place_name.value = fallback;
      }
      local.placeAuto = true;
    }

    form.elements.place_name.addEventListener("input", () => {
      local.placeAuto = false;
    });

    async function searchLocation() {
      const query = $("#location-query").value.trim();
      const results = $("#location-results");
      if (query.length < 2) {
        UI.showMessage(message, "Nhập ít nhất 2 ký tự để tìm địa điểm");
        return;
      }
      UI.showMessage(message, "");
      results.hidden = false;
      results.replaceChildren(UI.el("li", { className: "muted" }, [UI.el("span", { className: "spinner" }), " Đang tìm..."]));
      try {
        const places = await Api.get("/api/geocode", { query: { q: query } });
        if (!places.length) {
          results.replaceChildren(UI.el("li", { className: "muted", text: "Không tìm thấy địa điểm. Hãy thử tên khác hoặc chọn trực tiếp trên bản đồ" }));
          return;
        }
        results.replaceChildren(
          ...places.map((place) =>
            UI.el("li", {}, UI.el("button", {
              type: "button",
              onclick: () => {
                results.hidden = true;
                form.elements.place_name.value = place.name;
                local.placeAuto = false;
                setLocation(place.latitude, place.longitude, { reverse: false });
              },
            }, [UI.el("strong", { text: place.name }), UI.el("small", { text: place.display_name })])),
          ),
        );
      } catch (error) {
        results.replaceChildren(UI.el("li", { className: "muted", text: error.message }));
      }
    }
    $("#location-search").addEventListener("click", searchLocation);
    $("#location-query").addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        searchLocation();
      }
    });
    $("#pick-on-map").addEventListener("click", () => {
      $("#picking-banner").hidden = false;
      if (Shell.isMobile()) UI.toast("Chạm vào bản đồ phía trên để chọn vị trí");
      MemoryMap.startPickMode(({ latitude: lat, longitude: lng }) => {
        $("#picking-banner").hidden = true;
        setLocation(lat, lng, { fly: false });
      });
    });

    /* --- hashtag --- */
    const tagInput = form.elements.hashtags;
    function renderTagPreview() {
      const { error, tags } = parseTags(tagInput.value);
      const box = $("#tag-preview");
      box.replaceChildren(
        ...tags.map((tag) => UI.el("span", { className: `chip chip--static${local.aiTags.has(tag) ? " chip--ai" : ""}`, text: `#${tag}` })),
      );
      if (error) box.append(UI.el("span", { className: "field__hint", style: { color: "var(--color-danger)" }, text: error }));
    }
    tagInput.addEventListener("input", renderTagPreview);

    $("#suggest-tags").addEventListener("click", async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = "Đang gợi ý...";
      try {
        const result = await Api.post("/api/memories/suggest-hashtags", {
          body: {
            title: form.elements.title.value,
            content: form.elements.content.value,
            place_name: form.elements.place_name.value,
            latitude: form.elements.latitude.value ? Number(form.elements.latitude.value) : null,
            longitude: form.elements.longitude.value ? Number(form.elements.longitude.value) : null,
          },
        });
        const current = parseTags(tagInput.value).tags;
        const box = $("#tag-suggestions");
        const fresh = result.hashtags.filter((tag) => !current.includes(tag));
        box.replaceChildren(
          UI.el("span", { className: "field__hint", text: result.engine === "gemini" ? "Gợi ý từ Gemini AI — chạm để thêm:" : "Gợi ý — chạm để thêm:" }),
          ...fresh.map((tag) =>
            UI.el("button", {
              type: "button",
              className: "chip chip--ai",
              text: `+ #${tag}`,
              onclick: (clickEvent) => {
                const tags = parseTags(tagInput.value).tags;
                if (tags.length >= 10) {
                  UI.showMessage(message, "Mỗi ký ức tối đa 10 hashtag");
                  return;
                }
                local.aiTags.add(tag);
                tagInput.value = [...tags, tag].map((item) => `#${item}`).join(" ");
                clickEvent.currentTarget.remove();
                renderTagPreview();
              },
            }),
          ),
        );
        if (!fresh.length) box.append(UI.el("span", { className: "field__hint", text: "Không có gợi ý mới." }));
      } catch (error) {
        UI.showMessage(message, error.message);
      } finally {
        button.disabled = false;
        button.textContent = "✨ Gợi ý hashtag";
      }
    });

    /* --- ảnh --- */
    function imageCount() {
      return local.existingImages.filter((item) => !local.removedIds.has(item.id)).length + local.newImages.length;
    }

    function renderImages() {
      const grid = $("#image-grid");
      const items = [];
      const existing = local.existingImages.filter((item) => !local.removedIds.has(item.id));
      local.previewUrls.forEach((url) => URL.revokeObjectURL(url));
      local.previewUrls = [];
      const loadImage = createImageLoader(local.previewUrls);
      existing.forEach((item, index) => {
        const image = UI.el("img", { alt: `Ảnh ${index + 1}` });
        loadImage(item.thumb_url || item.url, memory.visibility !== "public" || memory.status !== "active")
          .then((url) => { image.src = url; })
          .catch(() => {});
        items.push(
          UI.el("div", { className: "upload-item" }, [
            image,
            UI.el("div", { className: "upload-item__tools" }, [
              UI.el("button", { type: "button", title: "Lên trước", text: "‹", disabled: index === 0, onclick: () => moveExisting(item, -1) }),
              UI.el("button", { type: "button", title: "Xóa ảnh", text: "✕", onclick: () => { local.removedIds.add(item.id); imageUploadSaved = false; renderImages(); } }),
              UI.el("button", { type: "button", title: "Ra sau", text: "›", disabled: index === existing.length - 1, onclick: () => moveExisting(item, 1) }),
            ]),
          ]),
        );
      });
      local.newImages.forEach((file, index) => {
        const url = URL.createObjectURL(file);
        local.previewUrls.push(url);
        const preview = UI.el("img", { src: url, alt: file.name });
        items.push(
          UI.el("div", { className: "upload-item upload-item--new", title: file.name }, [
            preview,
            UI.el("div", { className: "upload-item__tools" }, [
              UI.el("button", { type: "button", title: "Lên trước", text: "‹", disabled: index === 0, onclick: () => moveNew(index, -1) }),
              UI.el("button", { type: "button", title: "Bỏ ảnh", text: "✕", onclick: () => { local.newImages.splice(index, 1); imageUploadSaved = false; renderImages(); } }),
              UI.el("button", { type: "button", title: "Ra sau", text: "›", disabled: index === local.newImages.length - 1, onclick: () => moveNew(index, 1) }),
            ]),
          ]),
        );
      });
      const input = UI.el("input", { type: "file", accept: ".jpg,.jpeg,.png,.webp,.gif,image/jpeg,image/png,image/webp,image/gif", multiple: true });
      input.addEventListener("change", () => addImages([...input.files]));
      items.push(UI.el("label", { className: "upload-add" }, [UI.el("span", { text: "＋\nThêm ảnh" }), input]));
      grid.replaceChildren(...items);
      $("#image-counter").textContent = `${imageCount()}/10 · .jpg .png .webp .gif ≤ 5 MB`;
    }

    function moveExisting(item, step) {
      const visible = local.existingImages.filter((media) => !local.removedIds.has(media.id));
      const index = visible.indexOf(item);
      const target = visible[index + step];
      if (!target) return;
      const a = local.existingImages.indexOf(item);
      const b = local.existingImages.indexOf(target);
      [local.existingImages[a], local.existingImages[b]] = [local.existingImages[b], local.existingImages[a]];
      imageUploadSaved = false;
      renderImages();
    }

    function moveNew(index, step) {
      const target = index + step;
      if (target < 0 || target >= local.newImages.length) return;
      [local.newImages[index], local.newImages[target]] = [local.newImages[target], local.newImages[index]];
      imageUploadSaved = false;
      renderImages();
    }

    function addImages(files) {
      UI.showMessage(message, "");
      for (const file of files) {
        const extension = file.name.split(".").pop().toLowerCase();
        if (!IMAGE_RE.test(file.name) || (file.type && file.type !== IMAGE_MIME[extension])) {
          UI.showMessage(message, "Định dạng tệp không được hỗ trợ");
          continue;
        }
        if (file.size > MAX_IMAGE_BYTES) {
          UI.showMessage(message, "Mỗi ảnh không được vượt quá 5 MB");
          continue;
        }
        if (imageCount() >= MAX_IMAGES) {
          UI.showMessage(message, "Mỗi ký ức tối đa 10 ảnh");
          break;
        }
        local.newImages.push(file);
        imageUploadSaved = false;
      }
      renderImages();
    }

    /* --- video --- */
    function renderVideo() {
      const box = $("#video-box");
      const hasExisting = local.existingVideo && !local.removeVideo;
      if (hasExisting) {
        box.replaceChildren(
          UI.el("div", { className: "video-row" }, [
            UI.el("span", { text: "🎬 Video hiện tại" }),
            UI.el("a", {
              href: videoStreamUrl(local.existingVideo.url),
              target: "_blank",
              rel: "noopener",
              text: "Xem",
              onclick: async (event) => {
                if (memory.visibility === "public" && memory.status === "active") return;
                event.preventDefault();
                const playbackWindow = window.open("about:blank", "_blank");
                if (!playbackWindow) return UI.toast("Trình duyệt đã chặn cửa sổ phát video", "error");
                playbackWindow.opener = null;
                try {
                  playbackWindow.location.href = await loadProtectedVideo(videoStreamUrl(local.existingVideo.url), local.videoObjectUrls);
                } catch (error) {
                  playbackWindow.close();
                  UI.toast(error.message, "error");
                }
              },
            }),
            UI.el("button", { type: "button", className: "button button--sm", text: "Xóa video", onclick: () => { local.removeVideo = true; videoUploadSaved = false; renderVideo(); } }),
          ]),
        );
        return;
      }
      if (local.newVideo) {
        box.replaceChildren(
          UI.el("div", { className: "video-row" }, [
            UI.el("span", { text: `🎬 ${local.newVideo.name} · ${(local.newVideo.size / 1048576).toFixed(1)} MB` }),
            UI.el("button", { type: "button", className: "button button--sm", text: "Bỏ", onclick: () => { local.newVideo = null; videoUploadSaved = false; renderVideo(); } }),
          ]),
        );
        return;
      }
      const input = UI.el("input", { type: "file", accept: ".mp4,.mov,video/mp4,video/quicktime" });
      input.addEventListener("change", () => {
        const file = input.files[0];
        UI.showMessage(message, "");
        if (!file) return;
        const extension = file.name.split(".").pop().toLowerCase();
        if (!VIDEO_RE.test(file.name) || (file.type && file.type !== VIDEO_MIME[extension])) {
          UI.showMessage(message, "Định dạng tệp không được hỗ trợ");
          input.value = "";
          return;
        }
        if (file.size > MAX_VIDEO_BYTES) {
          UI.showMessage(message, "Video không được vượt quá 50 MB");
          input.value = "";
          return;
        }
        local.newVideo = file;
        videoUploadSaved = false;
        renderVideo();
      });
      box.replaceChildren(UI.el("label", { className: "field", style: { fontWeight: 400 } }, [input]));
    }

    /* --- chế độ + chuyến đi --- */
    function updateVisibilityHint() {
      const value = form.querySelector('input[name="visibility"]:checked').value;
      $("#visibility-hint").textContent =
        value === "public" ? "Mọi người đều thấy ký ức này trên bản đồ cộng đồng (ghim đỏ)." : "Chỉ mình bạn xem được ký ức này.";
    }
    form.querySelectorAll('input[name="visibility"]').forEach((input) => input.addEventListener("change", updateVisibilityHint));

    const trips = await Api.get("/api/trips").catch(() => []);
    const tripBox = $("#trip-checks");
    const selectedTrips = new Set(editing ? memory.trips.map((trip) => trip.id) : []);
    if (trips.length) {
      trips.forEach((trip) =>
        tripBox.append(UI.el("label", {}, [UI.el("input", { type: "checkbox", value: trip.id, checked: selectedTrips.has(trip.id) }), trip.name])),
      );
    } else {
      tripBox.append(UI.el("span", { className: "field__hint", text: "Chưa có chuyến đi — tạo ở tab “Chuyến đi”." }));
    }

    /* --- điền dữ liệu --- */
    form.elements.memory_date.max = UI.today();
    if (editing) {
      form.elements.title.value = memory.title;
      form.elements.place_name.value = memory.place_name;
      form.elements.memory_date.value = memory.memory_date;
      form.elements.content.value = memory.content || "";
      tagInput.value = memory.hashtags.map((tag) => `#${tag}`).join(" ");
      form.querySelector(`input[name="visibility"][value="${memory.visibility}"]`).checked = true;
      setLocation(memory.latitude, memory.longitude, { reverse: false });
    } else {
      form.elements.memory_date.value = UI.today();
      if (place_name) form.elements.place_name.value = place_name;
      if (latitude !== undefined && longitude !== undefined) setLocation(latitude, longitude, { reverse: !place_name, fly: false });
    }
    renderTagPreview();
    renderImages();
    renderVideo();
    updateVisibilityHint();

    /* --- gửi --- */
    async function submit() {
      UI.showMessage(message, "");
      const title = form.elements.title.value.trim();
      const placeName = form.elements.place_name.value.trim();
      const date = form.elements.memory_date.value;
      if (!form.elements.latitude.value) {
        $("#location-box").classList.add("is-missing");
        UI.showMessage(message, "Vui lòng chọn vị trí trên bản đồ hoặc tìm địa điểm");
        return;
      }
      if (!placeName) return UI.showMessage(message, "Vui lòng nhập tên địa điểm");
      if (!title) return UI.showMessage(message, "Vui lòng nhập tiêu đề");
      if (!date) return UI.showMessage(message, "Vui lòng chọn ngày");
      if (date > UI.today()) return UI.showMessage(message, "Ngày không được ở tương lai");
      const tagResult = parseTags(tagInput.value);
      if (tagResult.error) return UI.showMessage(message, tagResult.error);
      if (imageCount() > MAX_IMAGES) return UI.showMessage(message, "Mỗi ký ức tối đa 10 ảnh");

      const data = new FormData();
      ["title", "place_name", "latitude", "longitude", "memory_date", "content"].forEach((name) => data.append(name, form.elements[name].value.trim()));
      data.append("visibility", form.querySelector('input[name="visibility"]:checked').value);
      data.append("hashtags", tagResult.tags.join(" "));
      data.append("ai_hashtags", tagResult.tags.filter((tag) => local.aiTags.has(tag)).join(" "));
      data.append("trip_ids", [...tripBox.querySelectorAll("input:checked")].map((input) => input.value).join(","));

      const saveButton = document.getElementById("memory-save");
      const progress = $("#upload-progress");
      const bar = progress.querySelector(".progress__bar");
      const hasFiles = local.newImages.length || local.newVideo || local.removeVideo;
      saveButton.disabled = true;
      saveButton.textContent = hasFiles ? "Đang tải lên..." : "Đang lưu...";
      progress.hidden = !hasFiles;
      try {
        const saved = savedMemory || await uploadWithProgress(editing ? "PATCH" : "POST", editing ? `/api/memories/${memory.id}` : "/api/memories", data, (ratio) => {
          bar.style.width = `${Math.round(ratio * 100)}%`;
        });
        savedMemory = saved;
        const orderedExistingImages = local.existingImages.filter((item) => !local.removedIds.has(item.id));
        const imageOrderChanged = editing && orderedExistingImages.some((item, index) => item.id !== local.originalImageOrder.filter((id) => !local.removedIds.has(id))[index]);
        if (!imageUploadSaved && (local.newImages.length || local.removedIds.size || imageOrderChanged)) {
          const imageData = new FormData();
          local.newImages.forEach((file) => imageData.append("images", file, file.name));
          imageData.append("remove_media_ids", [...local.removedIds].join(","));
          imageData.append("image_order", orderedExistingImages.map((item) => item.id).join(","));
          await uploadWithProgress("POST", `/api/memories/${saved.id}/images`, imageData, (ratio) => {
            bar.style.width = `${Math.round(ratio * 100)}%`;
          });
          imageUploadSaved = true;
        }
        const videoChanged = local.newVideo || (local.removeVideo && local.existingVideo);
        if (!videoUploadSaved && videoChanged) {
          const videoData = new FormData();
          if (local.newVideo) videoData.append("video", local.newVideo, local.newVideo.name);
          if (local.removeVideo && local.existingVideo) videoData.append("remove_video", "true");
          await uploadWithProgress("POST", `/api/memories/${saved.id}/video`, videoData, (ratio) => {
            bar.style.width = `${Math.round(ratio * 100)}%`;
          });
          videoUploadSaved = true;
        }
        MemoryMap.clearTempMarker();
        UI.toast(editing ? "Đã cập nhật ký ức" : "Đã lưu ký ức", "success");
        refreshAll();
        UI.emit("trips:changed");
        openDetail(saved.id);
      } catch (error) {
        UI.showMessage(message, error.message);
        message.scrollIntoView({ behavior: "smooth", block: "center" });
      } finally {
        saveButton.disabled = false;
        saveButton.textContent = editing ? "Lưu thay đổi" : "Lưu ký ức";
        progress.hidden = true;
      }
    }
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      submit();
    });

    Shell.openDrawer({
      title: editing ? "Sửa ký ức" : "Ghim ký ức mới",
      body: container,
      footer: [
        UI.el("button", { type: "button", className: "button", text: "Hủy", onclick: () => (editing ? openDetail(memory.id) : Shell.closeDrawer()) }),
        UI.el("button", { type: "button", id: "memory-save", className: "button button--primary", text: editing ? "Lưu thay đổi" : "Lưu ký ức", onclick: submit }),
      ],
      onClose: () => {
        MemoryMap.clearTempMarker();
        MemoryMap.cancelPickMode();
        local.previewUrls.forEach((url) => URL.revokeObjectURL(url));
        local.videoObjectUrls.forEach((url) => URL.revokeObjectURL(url));
      },
    });
    if (!form.elements.latitude.value) $("#location-query").focus();
    else form.elements.title.focus();
  }

  /* ---------- Khởi động ---------- */
  MemoryMap.onPick(async (position) => {
    if (!(await requireLogin())) return;
    openForm(position);
  });
  UI.on("memory:open", ({ id, fly }) => openDetail(id, { fly }));
  UI.on("memory:create", (detail) => openForm(detail || {}));
  UI.on("layers:change", (layers) => MemoryMap.setLayerVisible(layer, layers.mine));
  UI.on("memories:refresh", refreshAll);

  (async () => {
    state.user = await AccountMenu.ready;
    await initPanel();
    if (state.user) {
      loadPins();
      UI.on("tab:change", (tab) => {
        if (tab === "mine") loadFilterOptions();
      });
    } else {
      const hint = document.getElementById("map-hint");
      if (hint) hint.textContent = "Đăng nhập để ghim ký ức · ghim đỏ là ký ức công khai của cộng đồng";
    }
  })();

  return {
    openDetail,
    openForm,
    refresh: refreshAll,
    get myIds() {
      return state.myIds;
    },
  };
})();
