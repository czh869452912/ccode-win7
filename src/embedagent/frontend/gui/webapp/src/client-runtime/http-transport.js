function defaultFetch(path, options) {
  return fetch(path, options);
}

function errorDetail(payload) {
  const detail = payload && typeof payload === "object" ? payload.detail : "";
  if (typeof detail === "string") return detail;
  if (detail !== undefined && detail !== null && detail !== "") {
    return JSON.stringify(detail);
  }
  const fallback = payload && typeof payload === "object" ? payload.error : "";
  return typeof fallback === "string" ? fallback : "";
}

export function createHttpTransport({ fetchImpl } = {}) {
  const execute = typeof fetchImpl === "function" ? fetchImpl : defaultFetch;

  async function request({ path, method = "GET", body, signal } = {}) {
    const options = { method, signal };
    if (body !== undefined) {
      options.headers = { "Content-Type": "application/json" };
      options.body = JSON.stringify(body);
    }
    const response = await execute(String(path || ""), options);
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = errorDetail(payload);
      const error = new Error(detail || response.statusText || "HTTP " + response.status);
      error.status = response.status;
      error.detail = detail;
      throw error;
    }
    return payload;
  }

  return Object.freeze({ request });
}
