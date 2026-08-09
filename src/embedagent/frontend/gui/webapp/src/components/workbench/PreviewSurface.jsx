import React, { useMemo, useState } from "react";

import {
  buildPreviewEmptyStateModel,
  buildPreviewRuntimeState,
  formatPreviewUrlDisplay,
  normalizePreviewUrl,
  previewSnapshotFromApi,
} from "../../session-runtime/preview-surface-model.js";

function previewChromeText(chrome, key) {
  return String((chrome && chrome[key]) || "");
}

function PreviewChromeRow({
  chrome = {},
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
        title={
          loading
            ? previewChromeText(chrome, "loadingLabel")
            : previewChromeText(chrome, "refreshLabel")
        }
        aria-label={
          loading
            ? previewChromeText(chrome, "loadingAriaLabel")
            : previewChromeText(chrome, "refreshAriaLabel")
        }
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
          placeholder={previewChromeText(chrome, "urlPlaceholder")}
          spellCheck={false}
          aria-label={previewChromeText(chrome, "urlAriaLabel")}
          data-testid="preview-url-input"
        />
      </div>
      <button
        type="button"
        className="preview-chrome-button"
        title={previewChromeText(chrome, "openExternalLabel")}
        aria-label={previewChromeText(chrome, "openExternalLabel")}
        disabled={!canOpenExternal}
        onClick={() => onOpenExternal && onOpenExternal()}
        data-testid="preview-open-external-action"
      >
        O
      </button>
      <button
        type="button"
        className="preview-chrome-button"
        title={previewChromeText(chrome, "annotateLabel")}
        aria-label={previewChromeText(chrome, "annotateLabel")}
        disabled
      >
        A
      </button>
      <button
        type="button"
        className="preview-chrome-button"
        title={previewChromeText(chrome, "moreActionsLabel")}
        aria-label={previewChromeText(chrome, "moreActionsLabel")}
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

function PreviewEmptyState({ servers, previewChrome, onOpenUrl }) {
  const model = useMemo(
    () => buildPreviewEmptyStateModel({ servers, chrome: previewChrome }),
    [servers, previewChrome],
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

function PreviewViewport({ url, previewChrome }) {
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
        <h3>{previewChromeText(previewChrome, "unavailableTitle")}</h3>
        <p>{previewChromeText(previewChrome, "unavailableBody")}</p>
      </div>
    </div>
  );
}

function PreviewUnreachable({ snapshot, previewChrome, onRefresh }) {
  const displayUrl = formatPreviewUrlDisplay(snapshot?.url || "");
  const description =
    snapshot?.errorDescription || previewChromeText(previewChrome, "unreachableBody");
  return (
    <div className="preview-unreachable" data-testid="preview-unreachable">
      <h3>{previewChromeText(previewChrome, "unavailableTitle")}</h3>
      <p>
        <strong>{displayUrl}</strong>: {description}
      </p>
      <button
        type="button"
        className="preview-unreachable-action"
        onClick={() => onRefresh && onRefresh()}
      >
        {previewChromeText(previewChrome, "reloadLabel")}
      </button>
    </div>
  );
}

function previewErrorMessage(error, fallback) {
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

function failedPreviewSnapshot(url, error, base = {}, previewChrome = {}) {
  return previewSnapshotFromApi({
    ...base,
    url,
    status: "failed",
    title: base.title || "",
    canGoBack: false,
    canGoForward: false,
    errorCode: base.errorCode || -1,
    errorDescription: previewErrorMessage(
      error,
      previewChromeText(previewChrome, "failedNotice"),
    ),
    updatedAt: base.updatedAt || "",
  });
}

export default function PreviewSurface({
  surface,
  servers = [],
  previewChrome = {},
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
      setSnapshot(failedPreviewSnapshot(next, error, {}, previewChrome));
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
      setSnapshot(failedPreviewSnapshot(activeUrl || snapshot.url, error, snapshot, previewChrome));
    } finally {
      setLoading(false);
    }
  }

  function openExternal() {
    if (onOpenExternal && activeUrl) {
      void Promise.resolve(onOpenExternal(activeUrl)).catch(() => {});
    }
  }

  const runtime = buildPreviewRuntimeState({ snapshot, chrome: previewChrome });
  const effectiveLoading = loading || runtime.loading;
  const effectiveUrl = snapshot?.url || activeUrl;

  return (
    <section className="preview-contribution" data-testid="preview-contribution">
      <PreviewChromeRow
        chrome={previewChrome}
        url={effectiveUrl}
        onOpenUrl={openUrl}
        onRefresh={refresh}
        onOpenExternal={openExternal}
        loading={effectiveLoading}
        canRefresh={runtime.canRefresh || Boolean(activeUrl)}
        canOpenExternal={runtime.canOpenExternal || Boolean(activeUrl)}
      />
      {runtime.unreachable ? (
        <PreviewUnreachable
          snapshot={snapshot}
          previewChrome={previewChrome}
          onRefresh={refresh}
        />
      ) : effectiveUrl ? (
        <PreviewViewport url={effectiveUrl} previewChrome={previewChrome} />
      ) : (
        <PreviewEmptyState
          servers={servers}
          previewChrome={previewChrome}
          onOpenUrl={openUrl}
        />
      )}
    </section>
  );
}
