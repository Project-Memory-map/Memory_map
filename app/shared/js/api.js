const Api = (() => {
  const TOKEN_KEY = "bdku_access_token";
  const BASE_URL = "";

  function getToken() {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch (error) {
      return null;
    }
  }

  function setToken(token) {
    try {
      if (token) {
        localStorage.setItem(TOKEN_KEY, token);
      } else {
        localStorage.removeItem(TOKEN_KEY);
      }
    } catch (error) {
      return;
    }
  }

  async function request(method, path, { query, body, formData } = {}) {
    const url = new URL(BASE_URL + path, window.location.origin);
    if (query) {
      Object.entries(query).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, value);
        }
      });
    }

    const headers = {};
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

    const response = await fetch(url, { method, headers, body: payload });
    const result = await response.json().catch(() => ({ message: "Phản hồi không hợp lệ từ máy chủ" }));

    if (response.status === 401) {
      setToken(null);
    }
    if (!response.ok) {
      const error = new Error(result.message || "Đã có lỗi xảy ra");
      error.status = response.status;
      error.data = result.data;
      throw error;
    }
    return result.data;
  }

  return {
    getToken,
    setToken,
    get: (path, options) => request("GET", path, options),
    post: (path, options) => request("POST", path, options),
    put: (path, options) => request("PUT", path, options),
    patch: (path, options) => request("PATCH", path, options),
    delete: (path, options) => request("DELETE", path, options),
  };
})();
