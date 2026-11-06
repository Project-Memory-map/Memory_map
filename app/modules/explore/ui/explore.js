(() => {
  const PUBLIC_PIN_COLOR = "#d1242f";
  const layer = MemoryMap.createLayer();
  let filters = {};
  let latestRequest = 0;

  function buildPopup(pin) {
    const wrapper = document.createElement("div");
    wrapper.className = "pin-popup";

    const title = document.createElement("h3");
    title.textContent = pin.title;

    const place = document.createElement("p");
    place.textContent = pin.place_name;

    const meta = document.createElement("p");
    meta.textContent = `${UI.formatDate(pin.memory_date)} · ${pin.author_name}`;

    wrapper.append(title, place, meta);
    return wrapper;
  }

  function render(pins) {
    layer.clearLayers();
    pins.forEach((pin) => {
      MemoryMap.addPin(layer, pin.latitude, pin.longitude, PUBLIC_PIN_COLOR, () => buildPopup(pin));
    });
    document.getElementById("pin-count").textContent = pins.length
      ? `${pins.length} ký ức công khai trong vùng đang xem`
      : "Chưa có ký ức công khai trong vùng này";
  }

  async function loadPins(bounds) {
    const requestId = ++latestRequest;
    try {
      const pins = await Api.get("/api/explore/pins", { query: { ...bounds, ...filters } });
      if (requestId === latestRequest) {
        render(pins);
      }
    } catch (error) {
      UI.toast(error.message);
    }
  }

  function handleFilter(event) {
    event.preventDefault();
    filters = Object.fromEntries(
      Object.entries(UI.formToJson(event.currentTarget)).filter(([, value]) => value),
    );
    loadPins(MemoryMap.getBounds());
  }

  async function init() {
    await UI.loadPartial("explore-panel", "/explore/panel.html");
    document.getElementById("explore-filter").addEventListener("submit", handleFilter);
    MemoryMap.onViewChange(loadPins);
    loadPins(MemoryMap.getBounds());
  }

  init();
})();
