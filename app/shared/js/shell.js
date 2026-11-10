/* Khung trang bản đồ: thanh bên + tab, ngăn kéo, ô tìm địa điểm, lớp bản đồ, liên kết sâu (?memory=, ?trip=). */
const Shell = (() => {
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("sidebar-backdrop");
  const drawer = document.getElementById("drawer");
  const tabs = document.querySelectorAll(".tab[data-tab]");
  const panels = document.querySelectorAll("[data-panel]");
  const layers = { mine: true, public: true };
  let drawerOnClose = null;
  let currentTab = "explore";

  MemoryMap.init("map");

  /* ---------- Thanh bên ---------- */
  function setSidebar(open) {
    sidebar.classList.toggle("is-open", open);
    backdrop.hidden = !open;
  }
  document.getElementById("sidebar-toggle").addEventListener("click", () => setSidebar(!sidebar.classList.contains("is-open")));
  backdrop.addEventListener("click", () => setSidebar(false));
  const isMobile = () => window.matchMedia("(max-width: 768px)").matches;

  function selectTab(name) {
    currentTab = name;
    tabs.forEach((tab) => {
      const active = tab.dataset.tab === name;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", String(active));
    });
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.panel !== name;
    });
    UI.emit("tab:change", name);
  }
  tabs.forEach((tab) => tab.addEventListener("click", () => selectTab(tab.dataset.tab)));

  /* ---------- Ngăn kéo bên phải ---------- */
  function openDrawer({ title, body, footer, onClose, actions }) {
    if (drawerOnClose) {
      const previous = drawerOnClose;
      drawerOnClose = null;
      previous();
    }
    const closeButton = UI.el("button", { type: "button", className: "icon-button icon-button--round", "aria-label": "Đóng", text: "✕", onclick: closeDrawer });
    const header = UI.el("div", { className: "drawer__header" }, [
      UI.el("h2", { text: title }),
      UI.el("div", { style: { display: "flex", gap: "6px" } }, [...(actions || []), closeButton]),
    ]);
    const content = [header, UI.el("div", { className: "drawer__body" }, body)];
    if (footer) content.push(UI.el("div", { className: "drawer__footer" }, footer));
    drawer.replaceChildren(...content);
    drawer.hidden = false;
    drawer.scrollTop = 0;
    drawerOnClose = onClose || null;
    document.body.classList.add("drawer-open");
    if (isMobile()) setSidebar(false);
  }

  function closeDrawer() {
    drawer.hidden = true;
    drawer.replaceChildren();
    document.body.classList.remove("drawer-open");
    MemoryMap.cancelPickMode();
    if (drawerOnClose) {
      const handler = drawerOnClose;
      drawerOnClose = null;
      handler();
    }
    const url = new URL(window.location.href);
    if (url.searchParams.has("memory") || url.searchParams.has("trip")) {
      url.searchParams.delete("memory");
      url.searchParams.delete("trip");
      history.replaceState(null, "", url.pathname + url.search);
    }
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !drawer.hidden && !document.querySelector(".modal-backdrop, .lightbox")) {
      closeDrawer();
    }
  });

  function setUrlParam(name, value) {
    const url = new URL(window.location.href);
    url.searchParams.delete("memory");
    url.searchParams.delete("trip");
    if (value) url.searchParams.set(name, value);
    history.replaceState(null, "", url.pathname + url.search);
  }

  /* ---------- Tìm địa điểm (Nominatim qua /api/geocode, BR-19: chỉ gọi khi nhấn Enter/Tìm) ---------- */
  const searchForm = document.getElementById("place-search");
  const searchInput = document.getElementById("place-search-input");
  const results = document.getElementById("place-results");

  function hideResults() {
    results.hidden = true;
    results.replaceChildren();
  }

  function choosePlace(place) {
    hideResults();
    searchInput.value = place.name;
    MemoryMap.flyTo(place.latitude, place.longitude, 14);
    const marker = MemoryMap.setTempMarker(place.latitude, place.longitude);
    const popup = UI.el("div", { className: "pin-popup" }, [
      UI.el("h3", { text: place.name }),
      UI.el("p", { text: place.display_name }),
      UI.el("button", {
        type: "button",
        className: "button button--primary button--sm",
        text: "📍 Ghim ký ức tại đây",
        onclick: () => {
          MemoryMap.closePopup();
          UI.emit("memory:create", { latitude: place.latitude, longitude: place.longitude, place_name: place.name });
        },
      }),
    ]);
    marker.bindPopup(popup, { className: "pin-popup-wrap" }).openPopup();
  }

  searchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = searchInput.value.trim();
    if (query.length < 2) {
      UI.toast("Nhập ít nhất 2 ký tự");
      return;
    }
    results.hidden = false;
    results.replaceChildren(UI.el("li", { className: "empty" }, [UI.el("span", { className: "spinner" }), " Đang tìm..."]));
    try {
      const places = await Api.get("/api/geocode", { query: { q: query } });
      if (!places.length) {
        results.replaceChildren(
          UI.el("li", { className: "empty", text: "Không tìm thấy địa điểm. Hãy thử tên khác hoặc chọn trực tiếp trên bản đồ" }),
        );
        return;
      }
      results.replaceChildren(
        ...places.map((place) =>
          UI.el("li", {}, UI.el("button", { type: "button", onclick: () => choosePlace(place) }, [
            UI.el("strong", { text: place.name }),
            UI.el("small", { text: place.display_name }),
          ])),
        ),
      );
    } catch (error) {
      results.replaceChildren(UI.el("li", { className: "empty", text: error.message }));
    }
  });
  document.addEventListener("click", (event) => {
    if (!searchForm.contains(event.target)) hideResults();
  });

  /* ---------- Lớp bản đồ ---------- */
  ["mine", "public"].forEach((name) => {
    document.getElementById(`layer-${name}`).addEventListener("change", (event) => {
      layers[name] = event.target.checked;
      UI.emit("layers:change", { ...layers });
    });
  });
  document.getElementById("locate-me").addEventListener("click", () => MemoryMap.locate());

  const hint = document.getElementById("map-hint");
  setTimeout(() => hint.classList.add("is-fading"), 9000);
  setTimeout(() => (hint.hidden = true), 9600);

  /* ---------- Liên kết sâu ---------- */
  window.addEventListener("load", () => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("memory")) UI.emit("memory:open", { id: Number(params.get("memory")), fly: true });
    else if (params.get("trip")) UI.emit("trip:open", { id: Number(params.get("trip")) });
  });

  return {
    openDrawer,
    closeDrawer,
    selectTab,
    setUrlParam,
    layers,
    isMobile,
    get currentTab() {
      return currentTab;
    },
  };
})();
