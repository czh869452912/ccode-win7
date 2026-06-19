import React, { useMemo, useState } from "react";

import {
  buildPreviewEmptyStateModel,
  buildPreviewRuntimeState,
  formatPreviewUrlDisplay,
  normalizePreviewUrl,
  previewSnapshotFromApi,
} from "../../session-runtime/preview-surface-model.js";

const DEFAULT_LOCAL_SERVERS = [
  { label: "Vite dev server", url: "localhost:5173", port: 5173 },
  { label: "Local app", url: "127.0.0.1:8000", port: 8000 },
];

function PreviewChromeRow({
  url,
  onOpenUrl,
  onRefresh,
  onOpenExternal,
  loading = false,
  canRefresh = false,
  canOpenExternal = false,
}) {
  const [draft, setDraft] = useState(url || "");

  React.useEffect(() => {
    setDraft(url || "");
  }, [url]);

  function submit(event) {
    event.preventDefault();
    const next = normalizePreviewUrl(draft);
    if (!next) return;
    onOpenUrl(next);
  }

  return (
    <form className="preview-chrome-row" data-surface-subheader onSubmit={submit}>
      <button
        type="button"
        className="preview-chrome-button"
        title={loading ? "Loading..." : "Refresh"}
        aria-label={loading ? "Loading preview" : "Refresh preview"}
        disabled={!canRefresh}
        onClick={() => onRefresh && onRefresh()}
        data-testid="preview-refresh-action"
      >
        R
      </button>
      <div className="preview-url-field">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onFocus={(event) => event.currentTarget.select()}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              setDraft(url || "");
              event.currentTarget.blur();
            }
          }}
          placeholder="Search or enter URL"
          spellCheck={false}
          aria-label="Preview URL"
          data-testid="preview-url-input"
        />
      </div>
      <button
        type="button"
        className="preview-chrome-button"
        title="Open in system browser"
        aria-label="Open in system browser"
        disabled={!canOpenExternal}
        onClick={() => onOpenExternal && onOpenExternal()}
        data-testid="preview-open-external-action"
      >
        O
      </button>
      <button
        type="button"
        className="preview-chrome-button"
        title="Annotate preview"
        aria-label="Annotate preview"
        disabled
      >
        A
      </button>
      <button
        type="button"
        className="preview-chrome-button"
        title="More preview actions"
        aria-label="More preview actions"
        disabled
      >
        ...
      </button>
    </form>
  );
}

function PreviewLocalServerCard({ server, onOpen }) {
  return (
    <button
      type="button"
      className="preview-local-server-card"
      onClick={() => onOpen(server.url)}
      data-testid="preview-local-server-card"
    >
      <span className="preview-local-server-dot" aria-hidden="true" />
      <span className="preview-local-server-main">
        <strong>{server.label}</strong>
        <span>{server.displayUrl}</span>
      </span>
      {server.port ? <small>{server.port}</small> : null}
    </button>
  );
}

function PreviewEmptyState({ servers, onOpenUrl }) {
  const model = useMemo(
    () => buildPreviewEmptyStateModel({ servers }),
    [servers],
  );
  return (
    <div className="preview-empty-state" data-testid="preview-empty-state">
      <div className="preview-empty-copy">
        <h3>{model.title}</h3>
        <p>{model.description}</p>
      </div>
      {model.hasServers ? (
        <div className="preview-local-server-list">
          {model.servers.map((server) => (
            <PreviewLocalServerCard
              key={server.id}
              server={server}
              onOpen={onOpenUrl}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function PreviewViewport({ url }) {
  if (!url) return null;
  return (
    <div className="preview-viewport" data-testid="preview-viewport">
      <div className="preview-browser-mock">
        <span className="preview-browser-dot" />
        <span className="preview-browser-dot" />
        <span className="preview-browser-dot" />
        <strong>{formatPreviewUrlDisplay(url)}</strong>
      </div>
      <div className="preview-unavailable">
        <h3>Preview unavailable</h3>
        <p>This local page cannot be rendered in the embedded preview.</p>
      </div>
    </div>
  );
}

function PreviewUnreachable({ snapshot, onRefresh }) {
  const displayUrl = formatPreviewUrlDisplay(snapshot?.url || "");
  const description = snapshot?.errorDescription || "The local preview target did not respond.";
  return (
    <div className="preview-unreachable" data-testid="preview-unreachable">
      <h3>Preview unavailable</h3>
      <p>
        <strong>{displayUrl}</strong>: {description}
      </p>
      <button
        type="button"
        className="preview-unreachable-action"
        onClick={() => onRefresh && onRefresh()}
      >
        Reload
      </button>
    </div>
  );
}

function previewErrorMessage(error, fallback) {
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

function failedPreviewSnapshot(url, error, base = {}) {
  return previewSnapshotFromApi({
    ...base,
    url,
    status: "failed",
    title: base.title || "",
    canGoBack: false,
    canGoForward: false,
    errorCode: base.errorCode || -1,
    errorDescription: previewErrorMessage(error, "Preview failed"),
    updatedAt: base.updatedAt || "",
  });
}

export default function PreviewSurface({
  surface,
  servers = DEFAULT_LOCAL_SERVERS,
  onOpenUrl,
  onRefresh,
  onOpenExternal,
}) {
  const initialUrl = normalizePreviewUrl(surface?.resourceId || "");
  const [activeUrl, setActiveUrl] = useState(initialUrl);
  const [snapshot, setSnapshot] = useState(surface?.previewSnapshot || null);
  const [loading, setLoading] = useState(false);

  React.useEffect(() => {
    setActiveUrl(initialUrl);
  }, [initialUrl]);

  React.useEffect(() => {
    setSnapshot(surface?.previewSnapshot || null);
  }, [surface?.previewSnapshot]);

  async function openUrl(url) {
    const next = normalizePreviewUrl(url);
    if (!next) return;
    setActiveUrl(next);
    setLoading(true);
    try {
      const result = onOpenUrl ? await onOpenUrl(next) : null;
      const nextSnapshot = result?.preview || result || null;
      if (nextSnapshot) setSnapshot(previewSnapshotFromApi(nextSnapshot));
    } catch (error) {
      setSnapshot(failedPreviewSnapshot(next, error));
    } finally {
      setLoading(false);
    }
  }

  async function refresh() {
    if (!snapshot || !onRefresh) {
      await openUrl(activeUrl);
      return;
    }
    setLoading(true);
    try {
      const result = await onRefresh(snapshot);
      const nextSnapshot = result?.preview || result || null;
      if (nextSnapshot) setSnapshot(previewSnapshotFromApi(nextSnapshot));
    } catch (error) {
      setSnapshot(failedPreviewSnapshot(activeUrl || snapshot.url, error, snapshot));
    } finally {
      setLoading(false);
    }
  }

  function openExternal() {
    if (onOpenExternal && activeUrl) {
      void Promise.resolve(onOpenExternal(activeUrl)).catch(() => {});
    }
  }

  const runtime = buildPreviewRuntimeState({ snapshot });
  const effectiveLoading = loading || runtime.loading;
  const effectiveUrl = snapshot?.url || activeUrl;

  return (
    <section className="right-panel-preview-surface" data-testid="right-panel-preview-surface">
      <PreviewChromeRow
        url={effectiveUrl}
        onOpenUrl={openUrl}
        onRefresh={refresh}
        onOpenExternal={openExternal}
        loading={effectiveLoading}
        canRefresh={runtime.canRefresh || Boolean(activeUrl)}
        canOpenExternal={runtime.canOpenExternal || Boolean(activeUrl)}
      />
      {runtime.unreachable ? (
        <PreviewUnreachable snapshot={snapshot} onRefresh={refresh} />
      ) : effectiveUrl ? (
        <PreviewViewport url={effectiveUrl} />
      ) : (
        <PreviewEmptyState servers={servers} onOpenUrl={openUrl} />
      )}
    </section>
  );
}
