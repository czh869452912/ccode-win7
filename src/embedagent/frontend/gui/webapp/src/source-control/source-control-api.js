async function parseJson(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || payload.error || response.statusText || "");
  }
  return payload;
}

function unwrapStatus(payload) {
  return payload.source_control || payload.sourceControl || payload;
}

export async function getSourceControlStatus() {
  const response = await fetch("/api/app/source-control/status");
  return unwrapStatus(await parseJson(response));
}

export async function refreshSourceControlStatus() {
  const response = await fetch("/api/app/source-control/refresh", { method: "POST" });
  return unwrapStatus(await parseJson(response));
}

export async function getSourceControlDiff(path, scope = "") {
  const params = new URLSearchParams();
  params.set("path", path || "");
  if (scope) params.set("scope", scope);
  const response = await fetch(`/api/app/source-control/diff?${params.toString()}`);
  const payload = await parseJson(response);
  return payload.diff || {};
}
