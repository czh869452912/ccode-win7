import { createAgentAppProtocolAdapter } from "../client-runtime/protocol-adapter.js";

function defaultFetch(url, options) {
  return fetch(url, options);
}

function errorDetail(payload) {
  if (typeof payload?.detail === "string") return payload.detail;
  return JSON.stringify(payload?.detail || "");
}

export function createJsonHttpClient({ fetchImpl } = {}) {
  const request = typeof fetchImpl === "function" ? fetchImpl : defaultFetch;

  async function rawFetchJson(url, options) {
    const res = await request(url, options);
    const payload = await res.json().catch(() => null);
    if (!res.ok) {
      const detail = errorDetail(payload);
      const error = new Error(detail || "HTTP " + res.status);
      error.status = res.status;
      error.detail = detail;
      throw error;
    }
    return payload;
  }

  const protocolAdapter = createAgentAppProtocolAdapter({
    fetchJson: rawFetchJson,
  });
  return {
    fetchJson: protocolAdapter.fetchJson,
    protocolAdapter,
  };
}

const defaultClient = createJsonHttpClient();
export const { fetchJson } = defaultClient;
export const protocolAdapter = defaultClient.protocolAdapter;
