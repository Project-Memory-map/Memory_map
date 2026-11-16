/* T05B58F: lọc ghim đã tải theo năm của memory_date. */
window.MemoryTimeline = (() => {
  const active = new Map();
  const tracked = new WeakSet();

  let map;
  let panel;
  let enabled;
  let slider;
  let output;
  let status;
  let reset;
  let selected = null;
  let frame = null;

  function yearOf(value) {
    if (typeof value !== "string") return null;

    const match = /^(\d{4})-(\d{2})-(\d{2})(?:T.*)?$/.exec(value);
    if (!match) return null;

    const year = Number(match[1]);
    const month = Number(match[2]);
    const day = Number(match[3]);
    const leap =
      year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);

    const days = [
      31, leap ? 29 : 28, 31, 30, 31, 30,
      31, 31, 30, 31, 30, 31,
    ];

    return (
      year >= 1 &&
      month >= 1 &&
      month <= 12 &&
      day >= 1 &&
      day <= days[month - 1]
    )
      ? year
      : null;
  }

  function schedule() {
    if (!map || frame !== null) return;

    frame = requestAnimationFrame(() => {
      frame = null;
      render();
    });
  }

  function paint(marker, record) {
    const hidden = selected !== null && record.year !== selected;

    if (hidden) marker.closePopup();

    const element = marker.getElement();
    if (!element) return;

    element.classList.add("timeline-pin");

    if (record.element !== element) {
      record.element = element;
      record.tabindex = element.getAttribute("tabindex");
      record.ariaHidden = element.getAttribute("aria-hidden");
    }

    element.classList.toggle("timeline-pin--hidden", hidden);

    if (hidden) {
      if (document.activeElement === element) slider.focus();

      element.setAttribute("tabindex", "-1");
      element.setAttribute("aria-hidden", "true");
    } else {
      const attributes = [
        ["tabindex", record.tabindex],
        ["aria-hidden", record.ariaHidden],
      ];

      for (const [name, value] of attributes) {
        if (value === null) element.removeAttribute(name);
        else element.setAttribute(name, value);
      }
    }
  }

  function render() {
    const records = [...active.values()];
    const years = records
      .map((record) => record.year)
      .filter((year) => year !== null);

    const hasYears = years.length > 0;
    const domain = selected === null ? years : [...years, selected];

    const minimum = domain.length
      ? Math.min(...domain)
      : new Date().getFullYear();

    const maximum = domain.length ? Math.max(...domain) : minimum;

    slider.min = String(minimum);
    slider.max = String(maximum);
    slider.value = String(selected === null ? maximum : selected);
    slider.disabled = !hasYears;

    enabled.disabled = !hasYears && selected === null;
    enabled.checked = selected !== null;
    reset.disabled = selected === null;

    const label = selected === null ? "Tất cả năm" : `Năm ${selected}`;
    output.textContent = label;
    slider.setAttribute("aria-valuetext", label);

    let visible = 0;
    let unknown = 0;

    for (const [marker, record] of active) {
      paint(marker, record);

      if (record.year === null) unknown++;
      if (selected === null || record.year === selected) visible++;
    }

    status.textContent = records.length
      ? `${visible}/${records.length} ghim đã tải thuộc lớp đang bật${
          unknown ? ` · ${unknown} ghim thiếu ngày hợp lệ` : ""
        }`
      : "Chưa có ghim đã tải trong các lớp đang bật.";
  }

  function setYear(year) {
    if (
      year !== null &&
      (!Number.isInteger(year) || year < 1 || year > 9999)
    ) {
      return;
    }

    selected = year;
    schedule();
  }

  function track(marker, memoryDate) {
    if (tracked.has(marker)) return marker;
    tracked.add(marker);

    const record = { year: yearOf(memoryDate) };

    marker.on("add", () => {
      active.set(marker, record);
      paint(marker, record);
      schedule();
    });

    // Khi mở ký ức từ danh sách, chuyển sang năm của ký ức đó.
    marker.on("popupopen", () => {
      if (selected !== null && selected !== record.year) {
        setYear(record.year);
      }
    });

    marker.on("remove", () => {
      active.delete(marker);
      schedule();
    });

    return marker;
  }

  function mount(instance) {
    if (panel) return;
    map = instance;

    const style = document.createElement("style");

    style.textContent = `
      .memory-timeline {
        box-sizing: border-box;
        width: 270px;
        max-width: calc(100vw - 90px);
        padding: 12px 14px;
        border: 1px solid #dbe3ee;
        border-radius: 12px;
        background: #fff;
        color: #1e293b;
        box-shadow: 0 3px 16px #0f172a20;
        font: 13px/1.5 system-ui, sans-serif;
      }

      .memory-timeline__head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }

      .memory-timeline__toggle {
        display: flex;
        align-items: center;
        gap: 6px;
        margin: 8px 0;
      }

      .memory-timeline input[type=checkbox] {
        width: 16px;
        height: 16px;
        margin: 0;
        accent-color: #2563eb;
      }

      .memory-timeline input[type=range] {
        display: block;
        box-sizing: border-box;
        width: 100%;
        height: 30px;
        margin: 4px 0;
        accent-color: #2563eb;
        cursor: pointer;
      }

      .memory-timeline output {
        display: block;
        font-weight: 700;
        color: #1d4ed8;
      }

      .memory-timeline small {
        display: block;
        margin-top: 4px;
        color: #475569;
      }

      .memory-timeline button {
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 5px 8px;
        background: #f8fafc;
        color: #1e293b;
        font: inherit;
        cursor: pointer;
      }

      .memory-timeline :disabled {
        opacity: .5;
        cursor: default;
      }

      .memory-timeline :focus-visible {
        outline: 3px solid #93c5fd;
        outline-offset: 2px;
      }

      .timeline-pin {
        transition: opacity 160ms ease, visibility 0s linear;
      }

      .timeline-pin--hidden {
        opacity: 0 !important;
        visibility: hidden;
        pointer-events: none !important;
        transition: opacity 160ms ease, visibility 0s linear 160ms;
      }

      @media (prefers-reduced-motion: reduce) {
        .timeline-pin,
        .timeline-pin--hidden {
          transition: none;
        }
      }
    `;

    document.head.append(style);

    const control = L.control({ position: "bottomleft" });

    control.onAdd = () => {
      panel = document.createElement("section");
      panel.className = "memory-timeline";
      panel.setAttribute("aria-label", "Thanh trượt thời gian");

      panel.innerHTML = `
        <div class="memory-timeline__head">
          <strong>Dòng thời gian</strong>
          <button type="button" data-reset>Tất cả năm</button>
        </div>

        <label class="memory-timeline__toggle">
          <input type="checkbox" data-enabled>
          Lọc ghim theo năm
        </label>

        <output id="timeline-year" aria-live="polite">
          Tất cả năm
        </output>

        <input
          type="range"
          min="2000"
          max="2000"
          step="1"
          aria-label="Năm của ký ức"
          aria-describedby="timeline-status"
          data-slider
        >

        <small id="timeline-status" role="status"></small>
      `;

      enabled = panel.querySelector("[data-enabled]");
      slider = panel.querySelector("[data-slider]");
      output = panel.querySelector("output");
      status = panel.querySelector("#timeline-status");
      reset = panel.querySelector("[data-reset]");

      slider.addEventListener("input", () => {
        setYear(Number(slider.value));
      });

      enabled.addEventListener("change", () => {
        setYear(enabled.checked ? Number(slider.value) : null);
      });

      reset.addEventListener("click", () => {
        setYear(null);
      });

      L.DomEvent.disableClickPropagation(panel);
      L.DomEvent.disableScrollPropagation(panel);

      panel.addEventListener("keydown", (event) => {
        event.stopPropagation();
      });

      return panel;
    };

    control.addTo(map);
    render();
  }

  return {
    mount,
    track,
    yearOf,
    setYear,

    get selectedYear() {
      return selected;
    },
  };
})();