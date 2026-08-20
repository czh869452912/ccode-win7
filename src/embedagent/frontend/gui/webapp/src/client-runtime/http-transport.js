function defaultFetch(path, options) {
  return fetch(path, options);
}

function errorFailure(payload) {
  const detail = payload && typeof payload === "object" ? payload.detail : "";
  if (detail && typeof detail === "object" && !Array.isArray(detail)) return detail;
  const fallback = payload && typeof payload === "object" ? payload.error : "";
  if (fallback && typeof fallback === "object" && !Array.isArray(fallback)) return fallback;
  return null;
}

function errorDetail(payload) {
  const failure = errorFailure(payload);
  if (failure) return String(failure.safe_message || failure.message || failure.code || "");
  const detail = payload && typeof payload === "object" ? payload.detail : "";
  if (typeof detail === "string") return detail;
  return typeof payload?.error === "string" ? payload.error : "";
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
      error.failure = errorFailure(payload);
      error.detail = error.failure?.code || detail;
      throw error;
    }
    return payload;
  }

  return Object.freeze({ request });
}
