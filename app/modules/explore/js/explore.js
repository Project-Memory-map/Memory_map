/* M3 – Khám phá: ghim đỏ công khai trong vùng đang xem, tìm theo từ khóa, lọc theo tỉnh/thành và hashtag (OR). */
(() => {
  const layer = MemoryMap.createLayer();
  const selectedTags = new Set();
  const state = { filters: {}, page: 1, regions: [], myIds: new Set(), latestPins: 0, latestList: 0 };
  const TAG_RE = /^[\p{L}\p{N}_]{1,30}$/u;

  function buildPopup(pin) {
    return UI.el("div", { className: "pin-popup" }, [
      UI.el("span", { className: "badge badge--public pin-popup__badge", text: "Cộng đồng" }),
      UI.el("h3", { text: pin.title }),
      UI.el("p", { text: pin.place_name }),
      UI.el("p", { text: `${UI.formatDate(pin.memory_date)} · ${pin.author_name}` }),
      UI.el("button", {
        type: "button",
        className: "button button--primary button--sm",
        text: "Xem chi tiết",
        onclick: () => Memories.openDetail(pin.id),
      }),
    ]);
  }

  function currentQuery() {
    const query = { ...state.filters };
    if (selectedTags.size) query.hashtags = [...selectedTags].join(" ");
    return query;
  }

  async function loadPins() {
    const requestId = ++state.latestPins;
    try {
      const pins = await Api.get("/api/explore/pins", { query: { ...MemoryMap.getBounds(), ...currentQuery() } });
      if (requestId !== state.latestPins) return;
      layer.clearLayers();
      const visible = pins.filter((pin) => !state.myIds.has(pin.id));
      visible.forEach((pin) => MemoryMap.addPin(layer, pin.latitude, pin.longitude, "public", () => buildPopup(pin), pin.title));
      const count = document.getElementById("pin-count");
      if (count && !document.getElementById("explore-filter").elements.viewport.checked) {
        count.dataset.pins = pins.length;
      }
    } catch (error) {
      if (error.status !== 422) UI.toast(error.message, "error");
    }
  }

  async function loadList(page = 1) {
    state.page = page;
    const requestId = ++state.latestList;
    const form = document.getElementById("explore-filter");
    const list = document.getElementById("explore-list");
    const status = document.getElementById("pin-count");
    const message = form.querySelector(".form-message");
    UI.showMessage(message, "");
    const query = { ...currentQuery(), page, page_size: 20 };
    if (form.elements.viewport.checked) Object.assign(query, MemoryMap.getBounds());
    if (page === 1) list.replaceChildren(UI.el("div", { className: "empty-state" }, UI.el("span", { className: "spinner" })));
    try {
      const result = await Api.getFull("/api/explore/memories", { query });
      if (requestId !== state.latestList) return;
      const data = result.data;
      if (page === 1) list.replaceChildren();
      data.items.forEach((memory) => list.append(UI.memoryCard(memory, { onClick: () => Memories.openDetail(memory.id, { fly: true }) })));
      if (!data.total) {
        const emptyText = form.elements.viewport.checked && !state.filters.q ? "Chưa có ký ức công khai trong khu vực này" : result.message;
        list.replaceChildren(UI.emptyState("🧭", emptyText));
        status.textContent = "";
      } else {
        const scope = form.elements.viewport.checked ? " trong vùng đang xem" : state.filters.region ? ` tại ${regionName(state.filters.region)}` : "";
        status.textContent = `${data.total} ký ức công khai${scope}${state.filters.q ? ` khớp “${state.filters.q}”` : ""}`;
      }
      document.getElementById("explore-more").hidden = data.page >= data.pages;
    } catch (error) {
      if (requestId !== state.latestList) return;
      list.replaceChildren();
      status.textContent = "";
      UI.showMessage(message, error.message);
    }
  }

  function regionName(slug) {
    const region = state.regions.find((item) => item.slug === slug);
    return region ? region.name : slug;
  }

  function reload() {
    loadPins();
    loadList(1);
  }

  function renderTagChips(tags) {
    const box = document.getElementById("explore-tags");
    const names = new Set(tags.map((tag) => tag.name));
    const extra = [...selectedTags].filter((name) => !names.has(name)).map((name) => ({ name, count: null }));
    box.replaceChildren(
      ...[...extra, ...tags].map((tag) => {
        const chip = UI.el("button", { type: "button", className: `chip${selectedTags.has(tag.name) ? " is-active" : ""}`, "aria-pressed": String(selectedTags.has(tag.name)) }, [
          `#${tag.name}`,
          tag.count !== null ? UI.el("span", { className: "chip__count", text: tag.count }) : null,
        ]);
        chip.addEventListener("click", () => {
          if (selectedTags.has(tag.name)) selectedTags.delete(tag.name);
          else selectedTags.add(tag.name);
          renderTagChips(tags);
          reload();
        });
        return chip;
      }),
    );
    if (!box.childElementCount) box.append(UI.el("span", { className: "muted", text: "Chưa có hashtag nào" }));
    state.popular = tags;
  }

  async function loadOptions() {
    const [regions, tags, overview] = await Promise.all([
      Api.get("/api/explore/regions").catch(() => []),
      Api.get("/api/explore/hashtags", { query: { limit: 12 } }).catch(() => []),
      Api.get("/api/explore/overview").catch(() => null),
    ]);
    state.regions = regions;
    const select = document.getElementById("explore-filter").elements.region;
    regions.forEach((region) =>
      select.append(UI.el("option", { value: region.slug, text: `${region.name}${region.public_count ? ` (${region.public_count})` : ""}` })),
    );
    renderTagChips(tags);
    if (overview) {
      document.getElementById("explore-overview").textContent = `${overview.public_memories} ký ức công khai · ghim đỏ trên bản đồ`;
    }
  }

  function addCustomTag() {
    const form = document.getElementById("explore-filter");
    const input = form.elements.custom_tag;
    const tag = input.value.trim().replace(/^#+/, "").normalize("NFC").toLowerCase();
    const message = form.querySelector(".form-message");
    if (!tag) return;
    if (!TAG_RE.test(tag)) {
      UI.showMessage(message, "Hashtag chỉ gồm chữ, số, dấu gạch dưới (tối đa 30 ký tự)");
      return;
    }
    selectedTags.add(tag);
    input.value = "";
    renderTagChips(state.popular || []);
    reload();
  }

  async function init() {
    const form = document.getElementById("explore-filter");
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const q = form.elements.q.value.trim();
      if (q && q.length < 2) {
        UI.showMessage(form.querySelector(".form-message"), "Nhập ít nhất 2 ký tự");
        return;
      }
      state.filters.q = q || undefined;
      reload();
    });
    form.elements.q.addEventListener("search", () => {
      if (!form.elements.q.value && state.filters.q) {
        state.filters.q = undefined;
        reload();
      }
    });
    form.elements.region.addEventListener("change", () => {
      const slug = form.elements.region.value;
      state.filters.region = slug || undefined;
      const region = state.regions.find((item) => item.slug === slug);
      if (region && region.bbox) MemoryMap.fitBox(region.bbox);
      reload();
    });
    form.elements.viewport.addEventListener("change", () => loadList(1));
    document.getElementById("explore-add-tag").addEventListener("click", addCustomTag);
    form.elements.custom_tag.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        addCustomTag();
      }
    });
    form.addEventListener("reset", () =>
      setTimeout(() => {
        state.filters = {};
        selectedTags.clear();
        renderTagChips(state.popular || []);
        UI.showMessage(form.querySelector(".form-message"), "");
        reload();
      }, 0),
    );
    document.getElementById("explore-more").addEventListener("click", () => loadList(state.page + 1));

    MemoryMap.onViewChange(() => {
      loadPins();
      if (form.elements.viewport.checked) loadList(1);
    });
    await loadOptions();
    reload();
  }

  UI.on("layers:change", (layers) => MemoryMap.setLayerVisible(layer, layers.public));
  UI.on("mine:loaded", (ids) => {
    state.myIds = ids;
    loadPins();
  });
  UI.on("memories:changed", () => loadPins());
  UI.on("explore:hashtag", (tag) => {
    selectedTags.clear();
    selectedTags.add(tag);
    Shell.selectTab("explore");
    Shell.closeDrawer();
    renderTagChips(state.popular || []);
    reload();
  });

  init();
})();
