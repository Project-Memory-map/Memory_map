/* Trang giới thiệu: đổi nút theo trạng thái đăng nhập, tải ký ức công khai mới nhất (dữ liệu thật). */
(() => {
  const { el } = UI;

  async function applyAuthState() {
    if (!Api.getToken()) return;
    try {
      const user = await Api.get("/api/auth/me");
      const account = document.getElementById("nav-account");
      account.textContent = `Mở bản đồ của ${user.display_name}`;
      account.href = "/ban-do";
      document.getElementById("cta-start").href = "/ban-do";
      document.getElementById("cta-free").textContent = "Mở bản đồ của tôi";
      document.getElementById("cta-free").href = "/ban-do";
    } catch (error) {
      /* token hết hạn: giữ giao diện khách */
    }
  }

  function tile(memory) {
    const image = memory.cover_url
      ? el("img", { className: "memory-tile__img", src: memory.cover_url, alt: "", loading: "lazy" })
      : el("div", { className: "memory-tile__img", text: "📍" });
    const tags = el("span", { className: "tags" });
    memory.hashtags.slice(0, 3).forEach((tag) => tags.append(el("b", { text: `#${tag}` })));
    return el("a", { className: "memory-tile", href: `/ban-do?memory=${memory.id}` }, [
      image,
      el("strong", { text: memory.title }),
      el("small", { text: `${UI.formatDate(memory.memory_date)} · ${memory.place_name} · ${memory.author.display_name}` }),
      memory.excerpt ? el("p", { text: memory.excerpt }) : null,
      memory.hashtags.length ? tags : null,
    ]);
  }

  async function loadCommunity() {
    const list = document.getElementById("community-list");
    try {
      const [data, overview] = await Promise.all([
        Api.get("/api/explore/memories", { query: { page_size: 3 } }),
        Api.get("/api/explore/overview").catch(() => null),
      ]);
      if (overview && overview.public_memories) {
        document.getElementById("community-stats").textContent =
          `${overview.public_memories} ký ức đang được chia sẻ công khai trên khắp ${overview.regions} tỉnh, thành.`;
      }
      list.replaceChildren(
        ...(data.items.length
          ? data.items.map(tile)
          : [UI.emptyState("🗺️", "Chưa có ký ức công khai nào — hãy là người đầu tiên!")]),
      );
    } catch (error) {
      list.replaceChildren(UI.emptyState("🗺️", "Không tải được ký ức cộng đồng lúc này."));
    }
  }

  applyAuthState();
  loadCommunity();
})();
