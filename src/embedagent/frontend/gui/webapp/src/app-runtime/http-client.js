import { createHttpTransport } from "../client-runtime/http-transport.js";
import { createAgentAppProtocolAdapter } from "../client-runtime/protocol-adapter.js";

function parseBody(body) {
  if (body === undefined) return undefined;
  if (typeof body !== "string") return body;
  return JSON.parse(body);
}

export function createJsonHttpClient({ fetchImpl } = {}) {
  const http = createHttpTransport({ fetchImpl });
  const fetchJson = (path, options = {}) =>
    http.request({
      path,
      method: options.method || "GET",
      body: parseBody(options.body),
      signal: options.signal,
    });
  return {
    fetchJson,
    protocolAdapter: createAgentAppProtocolAdapter({ http }),
  };
}

const defaultClient = createJsonHttpClient();
export const { fetchJson } = defaultClient;
export const protocolAdapter = defaultClient.protocolAdapter;
