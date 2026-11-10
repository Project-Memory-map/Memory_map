(() => {
  const drawer = document.getElementById("drawer");
  const pins = MemoryMap.createLayer();
  const preview = MemoryMap.createLayer();
  const markers = new Map();
  let opening = false;

  function today() {
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: "Asia/Ho_Chi_Minh",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(new Date());

    const get = (type) => parts.find((p) => p.type === type).value;
    return `${get("year")}-${get("month")}-${get("day")}`;
  }

  function closeForm() {
    preview.clearLayers();
    drawer.hidden = true;
    drawer.replaceChildren();
  }

  function popup(memory) {
    const box = document.createElement("div");

    const title = document.createElement("strong");
    title.textContent = memory.title;

    const info = document.createElement("p");
    const visibility =
      memory.visibility === "private" ? "Riêng tư" : "Công khai";

    info.textContent =
      `${memory.place_name} · ` +
      `${UI.formatDate(memory.memory_date)} · ${visibility}`;

    const content = document.createElement("p");
    content.textContent = memory.content;
    content.style.cssText =
      "white-space:pre-wrap;max-height:180px;overflow-y:auto";

    box.append(title, info, content);
    return box;
  }

  function addPin(memory) {
    const marker = MemoryMap.addPin(
      pins,
      memory.latitude,
      memory.longitude,
      "#2563eb",
      () => popup(memory)
    );

    markers.set(memory.id, marker);
    return marker;
  }

  async function refresh() {
    const status = document.getElementById("my-memory-status");

    try {
      const memories = await Api.get("/api/memories/mine");

      pins.clearLayers();
      markers.clear();

      const list = document.getElementById("my-memory-list");
      list.replaceChildren();

      memories.forEach((memory) => {
        const marker = addPin(memory);
        const button = document.createElement("button");

        button.type = "button";
        button.className = "button";
        button.style.cssText =
          "display:block;width:100%;margin:8px 0;text-align:left";

        button.textContent =
          `${memory.title} — ${UI.formatDate(memory.memory_date)}`;

        button.onclick = () => {
          MemoryMap.flyTo(memory.latitude, memory.longitude);
          marker.openPopup();
        };

        list.append(button);
      });

      status.textContent = `${memories.length} ký ức`;
    } catch (error) {
      status.textContent =
        `Không tải được danh sách: ${error.message}`;
    }
  }

  function selectPlace(form, place) {
    form.elements.latitude.value = place.latitude;
    form.elements.longitude.value = place.longitude;

    form.elements.place_name.value =
      place.name ||
      `Vị trí ${place.latitude.toFixed(5)}, ${place.longitude.toFixed(5)}`;

    form.querySelector("#memory-coords").textContent =
      `Tọa độ: ${place.latitude.toFixed(6)}, ` +
      `${place.longitude.toFixed(6)}`;

    UI.showMessage(form.querySelector(".form-message"), "");
    preview.clearLayers();

    MemoryMap.addPin(
      preview,
      place.latitude,
      place.longitude,
      "#7c3aed",
      () => {
        const text = document.createElement("span");
        text.textContent = "Vị trí đang chọn — chưa lưu";
        return text;
      }
    );

    MemoryMap.flyTo(place.latitude, place.longitude);
  }

  async function openForm(position) {
    if (opening) return;
    opening = true;

    try {
      if (!(await AccountMenu.ready) || !Api.getToken()) {
        UI.toast("Đăng nhập để tạo ký ức");
        return;
      }

      const current = drawer.querySelector("#memory-form");

      if (current) {
        if (position && current.dataset.busy !== "true") {
          selectPlace(current, position);
        }
        return;
      }

      await UI.loadPartial(drawer, "/memories/memory-form.html");
      drawer.hidden = false;

      const form = drawer.querySelector("#memory-form");
      const message = form.querySelector(".form-message");
      const query = form.querySelector("#location-query");
      const results = form.querySelector("#location-results");
      const searchMessage = form.querySelector("#location-message");
      const searchButton = form.querySelector("#location-search");

      let revision = 0;
      let searching = false;

      form.elements.memory_date.value = today();
      form.elements.memory_date.max = today();

      drawer.querySelector("[data-close-drawer]").onclick = () => {
        if (form.dataset.busy !== "true") closeForm();
      };

      if (position) selectPlace(form, position);

      // Không gửi yêu cầu tìm kiếm khi đang gõ.
      query.addEventListener("input", () => {
        revision++;
        results.replaceChildren();
        searchMessage.textContent = "";
      });

      async function search() {
        if (searching || form.dataset.busy === "true") return;

        const q = query.value.trim();

        if (q.length < 2) {
          searchMessage.textContent =
            "Nhập ít nhất 2 ký tự để tìm địa điểm";
          return;
        }

        const version = ++revision;

        results.replaceChildren();
        preview.clearLayers();

        form.elements.latitude.value = "";
        form.elements.longitude.value = "";
        form.elements.place_name.value = "";
        form.querySelector("#memory-coords").textContent =
          "Chưa chọn vị trí.";

        UI.showMessage(message, "");
        searchMessage.textContent = "Đang tìm địa điểm...";
        searching = true;
        searchButton.disabled = true;

        try {
          const places = await Api.get("/api/memories/geocode", {
            query: { q },
          });

          if (!form.isConnected || version !== revision) return;

          searchMessage.textContent = places.length
            ? "Chọn một kết quả bên dưới:"
            : "Không tìm thấy địa điểm. Hãy thử tên khác hoặc chọn trực tiếp trên bản đồ";

          places.forEach((place) => {
            const button = document.createElement("button");

            button.type = "button";
            button.className = "button";
            button.style.cssText =
              "display:block;width:100%;margin:6px 0;text-align:left";
            button.textContent = place.display_name;

            button.onclick = () => {
              selectPlace(form, place);
              results.replaceChildren();
              searchMessage.textContent = "Đã chọn địa điểm";
              form.elements.title.focus();
            };

            results.append(button);
          });
        } catch (error) {
          if (form.isConnected && version === revision) {
            searchMessage.textContent = error.message;
          }
        } finally {
          searching = false;
          searchButton.disabled = form.dataset.busy === "true";
        }
      }

      searchButton.onclick = search;

      query.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          search();
        }
      });

      form.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (form.dataset.busy === "true") return;

        const fields = form.elements;
        let error = "";

        if (!fields.title.value.trim()) {
          error = "Vui lòng nhập tiêu đề";
        } else if (!fields.memory_date.value) {
          error = "Vui lòng chọn ngày hợp lệ";
        } else if (fields.memory_date.value > today()) {
          error = "Ngày không được ở tương lai";
        } else if (
          !fields.latitude.value ||
          !fields.longitude.value
        ) {
          error =
            "Vui lòng chọn vị trí trên bản đồ hoặc tìm địa điểm";
        } else if (!fields.place_name.value.trim()) {
          error = "Vui lòng nhập tên địa điểm";
        }

        UI.showMessage(message, error);
        if (error) return;

        // Đọc dữ liệu trước khi vô hiệu hóa các ô.
        const formData = new FormData(form);

        revision++;
        form.dataset.busy = "true";
        UI.setBusy(form, true);

        let saved;

        try {
          saved = await Api.post("/api/memories", { formData });
        } catch (failure) {
          UI.showMessage(message, failure.message);
          return;
        } finally {
          form.dataset.busy = "false";
          UI.setBusy(form, false);
          searchButton.disabled = searching;
        }

        closeForm();
        UI.toast("Đã lưu ký ức");

        // Vẽ lại trước rồi mới mở popup của ký ức vừa lưu.
        await refresh();

        const marker = markers.get(saved.id) || addPin(saved);
        MemoryMap.flyTo(saved.latitude, saved.longitude);
        marker.openPopup();
      });

      query.focus();
    } catch (error) {
      UI.toast(error.message);
    } finally {
      opening = false;
    }
  }

  MemoryMap.onPick(openForm);

  (async () => {
    try {
      await UI.loadPartial(
        "memories-panel",
        "/memories/panel.html"
      );

      document.getElementById("create-memory").onclick =
        () => openForm();

      if (await AccountMenu.ready) {
        await refresh();
      } else {
        document.getElementById("my-memory-status").textContent =
          "Đăng nhập để xem ký ức của bạn.";
      }
    } catch (error) {
      UI.toast(error.message);
    }
  })();
})();