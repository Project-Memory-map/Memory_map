/* Bản đồ Leaflet dùng chung: ghim xanh (của tôi) / đỏ (cộng đồng), nhấp đúp / nhấn giữ để chọn vị trí. */
const MemoryMap = (() => {
  const DEFAULT_CENTER = [16.0471, 108.2068];
  const DEFAULT_ZOOM = 6;
  const LONG_PRESS_MS = 600;
  const PIN_SVG =
    '<svg viewBox="0 0 32 42" aria-hidden="true"><path d="M16 1C7.7 1 1 7.6 1 15.8 1 27 16 41 16 41s15-14 15-25.2C31 7.6 24.3 1 16 1z"/><circle cx="16" cy="15.5" r="6"/></svg>';

  let map;
  let pickMode = null;
  let lastPickAt = 0;
  let tempMarker = null;
  let routeLayer = null;
  const pickHandlers = [];
  const icons = {};

  function icon(kind) {
    if (!icons[kind]) {
      icons[kind] = L.divIcon({
        className: `map-pin map-pin--${kind}`,
        html: PIN_SVG,
        iconSize: [30, 40],
        iconAnchor: [15, 39],
        popupAnchor: [0, -34],
      });
    }
    return icons[kind];
  }

  function init(elementId) {
    map = L.map(elementId, { doubleClickZoom: false, zoomControl: false, worldCopyJump: true, minZoom: 3 }).setView(
      DEFAULT_CENTER,
      DEFAULT_ZOOM,
    );
    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.control.scale({ position: "bottomleft", imperial: false }).addTo(map);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    bindPickGestures();
    return map;
  }

  function bindPickGestures() {
    map.on("dblclick", (event) => emitPick(event.latlng));
    map.on("contextmenu", (event) => emitPick(event.latlng));
    map.on("click", (event) => {
      if (pickMode) {
        const handler = pickMode;
        pickMode = null;
        map.getContainer().classList.remove("is-picking");
        handler({ latitude: event.latlng.lat, longitude: event.latlng.lng });
      }
    });

    let pressTimer = null;
    const container = map.getContainer();
    container.addEventListener(
      "touchstart",
      (event) => {
        if (event.touches.length !== 1) {
          clearTimeout(pressTimer);
          return;
        }
        const touch = event.touches[0];
        const latlng = map.containerPointToLatLng(map.mouseEventToContainerPoint(touch));
        pressTimer = setTimeout(() => emitPick(latlng), LONG_PRESS_MS);
      },
      { passive: true },
    );
    ["touchend", "touchmove", "touchcancel"].forEach((name) =>
      container.addEventListener(name, () => clearTimeout(pressTimer), { passive: true }),
    );
    map.on("movestart zoomstart", () => clearTimeout(pressTimer));
  }

  function emitPick(latlng) {
    const now = Date.now();
    if (now - lastPickAt < 800) return;
    lastPickAt = now;
    pickHandlers.forEach((handler) => handler({ latitude: latlng.lat, longitude: latlng.lng }));
  }

  function onPick(handler) {
    pickHandlers.push(handler);
  }

  /* Chế độ chọn vị trí bằng một lần nhấp (dùng trong form ký ức) */
  function startPickMode(handler) {
    pickMode = handler;
    map.getContainer().classList.add("is-picking");
  }

  function cancelPickMode() {
    pickMode = null;
    if (map) map.getContainer().classList.remove("is-picking");
  }

  function onViewChange(handler) {
    let timer;
    map.on("moveend", () => {
      clearTimeout(timer);
      timer = setTimeout(() => handler(getBounds()), 250);
    });
  }

  function getBounds() {
    const bounds = map.getBounds();
    return {
      south: Math.max(bounds.getSouth(), -90),
      west: Math.max(bounds.getWest(), -180),
      north: Math.min(bounds.getNorth(), 90),
      east: Math.min(bounds.getEast(), 180),
    };
  }

  function createLayer() {
    return L.layerGroup().addTo(map);
  }

  function setLayerVisible(layer, visible) {
    if (visible && !map.hasLayer(layer)) layer.addTo(map);
    if (!visible && map.hasLayer(layer)) map.removeLayer(layer);
  }

  /* buildPopup trả về phần tử DOM (không dùng chuỗi HTML từ dữ liệu người dùng — BR-21) */
  function addPin(layer, latitude, longitude, kind, buildPopup, title) {
    const marker = L.marker([latitude, longitude], { icon: icon(kind), title: title || "", riseOnHover: true });
    if (buildPopup) {
      marker.bindPopup(buildPopup, { maxWidth: 280, minWidth: 220, className: "pin-popup-wrap" });
    }
    return marker.addTo(layer);
  }

  function setTempMarker(latitude, longitude, onMove) {
    clearTempMarker();
    tempMarker = L.marker([latitude, longitude], { icon: icon("new"), draggable: true, zIndexOffset: 1000 }).addTo(map);
    tempMarker.on("dragend", () => {
      const position = tempMarker.getLatLng();
      if (onMove) onMove({ latitude: position.lat, longitude: position.lng });
    });
    return tempMarker;
  }

  function clearTempMarker() {
    if (tempMarker) {
      map.removeLayer(tempMarker);
      tempMarker = null;
    }
  }

  function flyTo(latitude, longitude, zoom) {
    const targetZoom = zoom || Math.max(map.getZoom(), 13);
    map.flyTo([latitude, longitude], targetZoom, { duration: 0.8 });
  }

  function fitBox(bbox) {
    if (!bbox) return;
    const [south, west, north, east] = bbox;
    map.flyToBounds(
      [
        [south, west],
        [north, east],
      ],
      { padding: [30, 30], duration: 0.8 },
    );
  }

  function fitPoints(points) {
    if (!points.length) return;
    if (points.length === 1) {
      flyTo(points[0][0], points[0][1], 13);
      return;
    }
    map.flyToBounds(points, { padding: [50, 50], maxZoom: 14, duration: 0.8 });
  }

  function drawRoute(points) {
    clearRoute();
    if (points.length < 2) return;
    routeLayer = L.polyline(points, { color: "#7c3aed", weight: 3, opacity: 0.8, dashArray: "6 8" }).addTo(map);
  }

  function clearRoute() {
    if (routeLayer) {
      map.removeLayer(routeLayer);
      routeLayer = null;
    }
  }

  function locate() {
    if (!navigator.geolocation) {
      UI.toast("Trình duyệt không hỗ trợ định vị", "error");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => flyTo(position.coords.latitude, position.coords.longitude, 14),
      () => UI.toast("Không lấy được vị trí hiện tại", "error"),
      { enableHighAccuracy: true, timeout: 8000 },
    );
  }

  function closePopup() {
    if (map) map.closePopup();
  }

  function invalidate() {
    if (map) setTimeout(() => map.invalidateSize(), 260);
  }

  return {
    init,
    onPick,
    startPickMode,
    cancelPickMode,
    onViewChange,
    getBounds,
    createLayer,
    setLayerVisible,
    addPin,
    setTempMarker,
    clearTempMarker,
    flyTo,
    fitBox,
    fitPoints,
    drawRoute,
    clearRoute,
    locate,
    closePopup,
    invalidate,
    get instance() {
      return map;
    },
  };
})();
