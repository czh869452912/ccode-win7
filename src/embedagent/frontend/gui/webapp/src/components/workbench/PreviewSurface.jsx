import React, { useMemo, useState } from "react";

import {
  buildPreviewEmptyStateModel,
  formatPreviewUrlDisplay,
  normalizePreviewUrl,
} from "../../session-runtime/preview-surface-model.js";

const DEFAULT_LOCAL_SERVERS = [
  { label: "Vite dev server", url: "localhost:5173", port: 5173 },
  { label: "Local app", url: "127.0.0.1:8000", port: 8000 },
];

function PreviewChromeRow({
  url,
  onOpenUrl,
  loading = false,
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
        disabled={!url}
        onClick={() => url && onOpenUrl(url)}
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
        disabled={!url}
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

export default function PreviewSurface({
  surface,
  servers = DEFAULT_LOCAL_SERVERS,
  onOpenUrl,
}) {
  const initialUrl = normalizePreviewUrl(surface?.resourceId || "");
  const [activeUrl, setActiveUrl] = useState(initialUrl);

  React.useEffect(() => {
    setActiveUrl(initialUrl);
  }, [initialUrl]);

  function openUrl(url) {
    const next = normalizePreviewUrl(url);
    if (!next) return;
    setActiveUrl(next);
    if (onOpenUrl) onOpenUrl(next);
  }

  return (
    <section className="right-panel-preview-surface" data-testid="right-panel-preview-surface">
      <PreviewChromeRow url={activeUrl} onOpenUrl={openUrl} />
      {activeUrl ? (
        <PreviewViewport url={activeUrl} />
      ) : (
        <PreviewEmptyState servers={servers} onOpenUrl={openUrl} />
      )}
    </section>
  );
}
