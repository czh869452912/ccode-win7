async function parseJson(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || payload.error || response.statusText || "");
  }
  return payload;
}

export async function listTerminals(sessionId) {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/terminals`);
  return parseJson(response);
}

export async function openTerminal(sessionId, terminalId, options = {}) {
  const response = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}/terminals/${encodeURIComponent(terminalId)}/open`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(options),
    },
  );
  return parseJson(response);
}

export async function getTerminalSnapshot(sessionId, terminalId) {
  const response = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}/terminals/${encodeURIComponent(terminalId)}/snapshot`,
  );
  return parseJson(response);
}

export async function writeTerminal(sessionId, terminalId, data) {
  const response = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}/terminals/${encodeURIComponent(terminalId)}/write`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data }),
    },
  );
  return parseJson(response);
}

export async function clearTerminal(sessionId, terminalId) {
  const response = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}/terminals/${encodeURIComponent(terminalId)}/clear`,
    { method: "POST" },
  );
  return parseJson(response);
}

export async function restartTerminal(sessionId, terminalId, options = {}) {
  const response = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}/terminals/${encodeURIComponent(terminalId)}/restart`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(options),
    },
  );
  return parseJson(response);
}

export async function resizeTerminal(sessionId, terminalId, cols, rows) {
  const response = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}/terminals/${encodeURIComponent(terminalId)}/resize`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cols, rows }),
    },
  );
  return parseJson(response);
}

export async function closeTerminal(sessionId, terminalId) {
  const response = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}/terminals/${encodeURIComponent(terminalId)}/close`,
    { method: "POST" },
  );
  return parseJson(response);
}
