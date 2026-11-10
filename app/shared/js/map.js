const MemoryMap = (() => {
  const DEFAULT_CENTER = [16.0471, 108.2068];
  const DEFAULT_ZOOM = 6;
  const LONG_PRESS_MS = 600;

  let map;
  const pickHandlers = [];

  function init(elementId) {
    map = L.map(elementId, {
      doubleClickZoom: false,
    }).setView(DEFAULT_CENTER, DEFAULT_ZOOM);

    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);

    bindPickGestures();
    return map;
  }

  function bindPickGestures() {
    map.on("dblclick", (event) => emitPick(event.latlng));

    let pressTimer = null;

    map.on("touchstart", (event) => {
      const touch = event.originalEvent.touches[0];

      if (!touch) return;

      const latlng = map.mouseEventToLatLng(touch);

      pressTimer = setTimeout(
        () => emitPick(latlng),
        LONG_PRESS_MS
      );
    });

    ["touchend", "touchmove", "movestart"].forEach((name) => {
      map.on(name, () => clearTimeout(pressTimer));
    });
  }

  function emitPick(latlng) {
    pickHandlers.forEach((handler) => handler({
      latitude: latlng.lat,
      longitude: latlng.lng,
    }));
  }

  function onPick(handler) {
    pickHandlers.push(handler);
  }

  function onViewChange(handler) {
    map.on("moveend", () => handler(getBounds()));
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

  function addPin(layer, latitude, longitude, color, buildPopup) {
    return L.circleMarker([latitude, longitude], {
      radius: 8,
      color,
      fillColor: color,
      fillOpacity: 0.85,
    })
      .bindPopup(buildPopup)
      .addTo(layer);
  }

  function flyTo(latitude, longitude) {
    map.flyTo([latitude, longitude], 15);
  }

  return {
    init,
    onPick,
    onViewChange,
    getBounds,
    createLayer,
    addPin,
    flyTo,
  };
})();