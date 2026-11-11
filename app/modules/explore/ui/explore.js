(() => {
  const layer = MemoryMap.createLayer();

  let filters = {};
  let pinVersion = 0;
  let listVersion = 0;
  let page = 1;
  let timer;
  let busy = false;
  let detailVersion = 0;

  const byId = (id) => document.getElementById(id);

  const element = (tag, text) => {
    const node = document.createElement(tag);
    node.textContent = text;
    return node;
  };

  async function openDetail(id) {
    const version = ++detailVersion;

    try {
      const memory = await Api.get(
        `/api/explore/memories/${id}`
      );

      if (version !== detailVersion) return;

      document.querySelector(".public-detail")?.remove();

      const dialog = document.createElement("dialog");
      dialog.className = "public-detail";
      dialog.setAttribute(
        "aria-label",
        "Ký ức công khai"
      );

      const close = element("button", "Đóng");
      close.type = "button";
      close.onclick = () => dialog.close();

      dialog.addEventListener(
        "close",
        () => dialog.remove()
      );

      dialog.append(
        close,
        element("h2", memory.title),
        element(
          "p",
          `${memory.author_name} · ` +
          `${UI.formatDate(memory.memory_date)} · ` +
          `${memory.place_name}`
        ),
        element("p", memory.content || "")
      );

      for (const media of memory.media || []) {
        const node = document.createElement(
          media.type === "video" ? "video" : "img"
        );

        node.src = media.url;

        if (media.type === "video") {
          node.controls = true;
        } else {
          node.alt = "Ảnh đính kèm ký ức";
          node.loading = "lazy";
        }

        dialog.append(node);
      }

      document.body.append(dialog);
      dialog.showModal();

    } catch (error) {
      if (version === detailVersion) {
        UI.toast(error.message);
      }
    }
  }

  function popup(pin) {
    const box = document.createElement("div");
    box.className = "pin-popup";

    const button = element(
      "button",
      "Xem chi tiết"
    );

    button.type = "button";
    button.onclick = () => openDetail(pin.id);

    box.append(
      element("h3", pin.title),
      element("p", pin.place_name),
      element(
        "p",
        `${UI.formatDate(pin.memory_date)} · ` +
        `${pin.author_name}`
      ),
      button
    );

    return box;
  }

  async function loadPins() {
    const version = ++pinVersion;

    layer.clearLayers();
    byId("pin-count").textContent = "Đang tải ghim…";

    try {
      const pins = await Api.get(
        "/api/explore/pins",
        {
          query: {
            ...MemoryMap.getBounds(),
            ...filters,
          },
        }
      );

      if (version !== pinVersion) return;

      pins.forEach((pin) => {
        MemoryMap.addPin(
          layer,
          pin.latitude,
          pin.longitude,
          "#d1242f",
          () => popup(pin)
        );
      });

      byId("pin-count").textContent = pins.length
        ? `${pins.length} ghim công khai trong vùng đang xem${
            pins.length === 500
              ? " (tối đa 500; phóng to để xem rõ hơn)"
              : ""
          }`
        : "Chưa có ký ức công khai trong khu vực này";

    } catch (error) {
      if (version === pinVersion) {
        byId("pin-count").textContent = error.message;
      }
    }
  }

  async function loadList(reset = true) {
    if (!reset && busy) return;

    const version = ++listVersion;
    const targetPage = reset ? 1 : page + 1;

    busy = true;
    byId("explore-more").disabled = true;

    if (reset) {
      byId("explore-results").replaceChildren();
      byId("explore-more").hidden = true;
    }

    byId("explore-status").textContent =
      "Đang tải ký ức…";

    try {
      const bounds = byId("explore-viewport").checked
        ? MemoryMap.getBounds()
        : {};

      const result = await Api.get(
        "/api/explore/memories",
        {
          query: {
            ...filters,
            ...bounds,
            page: targetPage,
          },
        }
      );

      if (version !== listVersion) return;

      page = targetPage;

      for (const memory of result.items) {
        const card = document.createElement("button");

        card.type = "button";
        card.className = "explore-card";

        card.append(
          element("strong", memory.title),
          element("small", memory.place_name),
          element(
            "small",
            `${UI.formatDate(memory.memory_date)} · ` +
            `${memory.author_name}`
          )
        );

        card.onclick = () => {
          MemoryMap.flyTo(
            memory.latitude,
            memory.longitude
          );

          openDetail(memory.id);
        };

        byId("explore-results").append(card);
      }

      byId("explore-status").textContent =
        result.items.length ? "" : result.message;

      byId("explore-more").hidden =
        !result.has_more;

    } catch (error) {
      if (version === listVersion) {
        byId("explore-status").textContent =
          error.message;
      }

    } finally {
      if (version === listVersion) {
        busy = false;
        byId("explore-more").disabled = false;
      }
    }
  }

  function refresh() {
    clearTimeout(timer);
    loadPins();
    loadList();
  }

  async function init() {
    await UI.loadPartial(
      "explore-panel",
      "/explore/panel.html"
    );

    byId("explore-filter").onsubmit = (event) => {
      event.preventDefault();

      const data = new FormData(
        event.currentTarget
      );

      filters = Object.fromEntries(
        [...data.entries()].map(
          ([key, value]) => [
            key,
            value.trim(),
          ]
        )
      );

      refresh();
    };

    byId("explore-reset").onclick = () => {
      byId("explore-filter").reset();
      filters = {};
      refresh();
    };

    byId("explore-viewport").onchange = () => {
      loadList();
    };

    byId("explore-more").onclick = () => {
      loadList(false);
    };

    MemoryMap.onViewChange(() => {
      // Loại phản hồi cũ ngay khi vùng nhìn thay đổi.
      ++pinVersion;
      layer.clearLayers();

      const bounded =
        byId("explore-viewport").checked;

      if (bounded) {
        ++listVersion;
        busy = false;

        byId("explore-results").replaceChildren();
        byId("explore-more").hidden = true;
      }

      clearTimeout(timer);

      timer = setTimeout(() => {
        loadPins();

        if (bounded) {
          loadList();
        }
      }, 250);
    });

    document.addEventListener(
      "memories:changed",
      () => {
        ++detailVersion;

        document
          .querySelector(".public-detail")
          ?.close();

        refresh();
      }
    );

    refresh();

    try {
      const regions = await Api.get(
        "/api/explore/regions"
      );

      regions.forEach((region) => {
        const option = element(
          "option",
          region.name
        );

        option.value = region.slug;
        byId("explore-region").append(option);
      });

    } catch (error) {
      UI.toast(
        `Không tải được khu vực: ${error.message}`
      );
    }
  }

  init().catch((error) => {
    UI.toast(error.message);
  });
})();