async function parseJson(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || payload.error || response.statusText || "Preview request failed");
  }
  return payload;
}

function apiFetch(options = {}) {
  return options.fetch || fetch;
}

export async function listPreviewSessions(sessionId, options = {}) {
  const response = await apiFetch(options)(
    `/api/sessions/${encodeURIComponent(sessionId)}/preview`,
  );
  return parseJson(response);
}

export async function openPreviewSession(sessionId, url, options = {}) {
  const response = await apiFetch(options)(
    `/api/sessions/${encodeURIComponent(sessionId)}/preview/open`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    },
  );
  return parseJson(response);
}

export async function refreshPreviewSession(sessionId, tabId, options = {}) {
  const response = await apiFetch(options)(
    `/api/sessions/${encodeURIComponent(sessionId)}/preview/${encodeURIComponent(tabId)}/refresh`,
    { method: "POST" },
  );
  return parseJson(response);
}

export async function closePreviewSession(sessionId, tabId, options = {}) {
  const response = await apiFetch(options)(
    `/api/sessions/${encodeURIComponent(sessionId)}/preview/${encodeURIComponent(tabId)}/close`,
    { method: "POST" },
  );
  return parseJson(response);
}

export async function openPreviewExternal(url, options = {}) {
  const response = await apiFetch(options)(
    "/api/app/preview/open-external",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    },
  );
  return parseJson(response);
}
