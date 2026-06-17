import React from "react";

function normalizePath(path) {
  return String(path || "").replace(/\\/g, "/").replace(/^\/+/, "");
}

function titleForPath(path) {
  const normalized = normalizePath(path);
  if (!normalized) return "File";
  const parts = normalized.split("/");
  return parts[parts.length - 1] || normalized;
}

function statusForPreview(filePreview) {
  if (!filePreview || !filePreview.status) return "loading";
  return filePreview.status;
}

export default function FilePreviewSurface({ surface, filePreview, onReload }) {
  const filePath = normalizePath(surface?.filePath || surface?.resourceId);
  const status = statusForPreview(filePreview);
  const title = filePreview?.title || surface?.title || titleForPath(filePath);
  return (
    <div className="right-panel-file-surface" data-testid="right-panel-file-surface" data-file-path={filePath}>
      <div className="right-panel-file-header">
        <strong>{title}</strong>
        <span>{filePath}</span>
      </div>
      {status === "loading" ? (
        <div className="right-panel-file-loading">Loading file...</div>
      ) : null}
      {status === "error" ? (
        <div className="right-panel-file-error" role="alert">
          <span>{filePreview?.error || "File unavailable"}</span>
          {onReload ? (
            <button type="button" onClick={() => onReload(filePath)}>
              Retry
            </button>
          ) : null}
        </div>
      ) : null}
      {status === "loaded" ? (
        <pre className="right-panel-file-content" data-testid="right-panel-file-content">
          {filePreview?.content || ""}
        </pre>
      ) : null}
    </div>
  );
}
