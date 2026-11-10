/* Nhận JWT từ /api/auth/{google|facebook}/callback qua phần # của URL (không gửi lên máy chủ, không lưu lịch sử). */
(() => {
  const params = new URLSearchParams(window.location.hash.slice(1));
  const token = params.get("token");
  const notices = (params.get("notice") || "").split(",").filter(Boolean);
  history.replaceState(null, "", window.location.pathname);
  if (!token) {
    UI.showMessage(document.getElementById("page-message"), "Đăng nhập chưa hoàn tất, vui lòng thử lại");
    return;
  }
  Api.setToken(token);
  const target = notices.includes("need_email") ? "/accounts/profile.html?notice=need_email" : "/ban-do?notice=oauth";
  window.location.replace(target);
})();
