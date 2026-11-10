/* Gọi API backend, tự gắn JWT. Mọi phản hồi theo khung {statusCode, message, error, data}. */
const Api = (() => {
  const TOKEN_KEY = "bdku_access_token";
  const BASE_URL = "";
  let memoryToken = null;

  function getToken() {
    try {
      return localStorage.getItem(TOKEN_KEY) || memoryToken;
    } catch (error) {
      return memoryToken;
    }
  }

  function setToken(token) {
    memoryToken = token || null;
    try {
      if (token) {
        localStorage.setItem(TOKEN_KEY, token);
      } else {
        localStorage.removeItem(TOKEN_KEY);
      }
    } catch (error) {
      /* trình duyệt chặn localStorage: giữ token trong bộ nhớ */
    }
  }

  function buildUrl(path, query) {
    const url = new URL(BASE_URL + path, window.location.origin);
    if (query) {
      Object.entries(query).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
          url.searchParams.append(key, value);
        }
      });
    }
    return url;
  }

  async function request(method, path, { query, body, formData, signal } = {}) {
    const headers = { Accept: "application/json" };
    const token = getToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    let payload;
    if (formData) {
      payload = formData;
    } else if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }

    let response;
    try {
      response = await fetch(buildUrl(path, query), { method, headers, body: payload, signal });
    } catch (networkError) {
      if (networkError.name === "AbortError") {
        throw networkError;
      }
      const error = new Error("Không kết nối được máy chủ, vui lòng kiểm tra mạng");
      error.status = 0;
      throw error;
    }
    const result = await response
      .json()
      .catch(() => ({ message: response.status === 413 ? "Tệp tải lên quá lớn" : "Phản hồi không hợp lệ từ máy chủ" }));

    if (response.status === 401 && token) {
      setToken(null);
      document.dispatchEvent(new CustomEvent("auth:expired"));
    }
    if (!response.ok) {
      const error = new Error(result.message || "Đã có lỗi xảy ra");
      error.status = response.status;
      error.data = result.data;
      throw error;
    }
    return result.data;
  }

  /* Gọi API kèm thông điệp (message) của máy chủ */
  async function requestWithMessage(method, path, options) {
    const headers = { Accept: "application/json" };
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    const response = await fetch(buildUrl(path, options && options.query), { method, headers });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(result.message || "Đã có lỗi xảy ra");
      error.status = response.status;
      throw error;
    }
    return result;
  }

  return {
    getToken,
    setToken,
    get: (path, options) => request("GET", path, options),
    getFull: (path, options) => requestWithMessage("GET", path, options),
    post: (path, options) => request("POST", path, options),
    put: (path, options) => request("PUT", path, options),
    patch: (path, options) => request("PATCH", path, options),
    delete: (path, options) => request("DELETE", path, options),
  };
})();
