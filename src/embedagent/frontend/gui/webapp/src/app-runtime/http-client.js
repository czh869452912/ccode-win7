function defaultFetch(url, options) {
  return fetch(url, options);
}

function errorDetail(payload) {
  if (typeof payload?.detail === "string") return payload.detail;
  return JSON.stringify(payload?.detail || "");
}

export function createJsonHttpClient({ fetchImpl } = {}) {
  const request = typeof fetchImpl === "function" ? fetchImpl : defaultFetch;

  async function fetchJson(url, options) {
    const res = await request(url, options);
    const payload = await res.json().catch(() => null);
    if (!res.ok) {
      const detail = errorDetail(payload);
      const error = new Error(detail || `HTTP ${res.status}`);
      error.status = res.status;
      error.detail = detail;
      throw error;
    }
    return payload;
  }

  return { fetchJson };
}

export const { fetchJson } = createJsonHttpClient();
