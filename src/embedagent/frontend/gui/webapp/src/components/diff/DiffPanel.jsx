import React from "react";

import DiffView from "../DiffView.jsx";

export default function DiffPanel({ surface, onFocusFile }) {
  if (!surface) {
    return <div className="empty-copy">No diff selected.</div>;
  }
  const files = Array.isArray(surface.files) ? surface.files : [];
  return (
    <section className="diff-panel" data-testid="diff-panel">
      <header className="diff-panel-header">
        <strong>{surface.title || "Diff"}</strong>
        <span>
          {files.length} files
          {files.length > 0 ? `  +${surface.additions || 0} -${surface.deletions || 0}` : ""}
        </span>
      </header>
      {files.length > 0 ? (
        <div className="diff-file-list">
          {files.map((file) => (
            <button
              key={file.path}
              type="button"
              className={file.path === surface.focusedFilePath ? "active" : ""}
              onClick={() => onFocusFile && onFocusFile(file.path)}
              data-testid={`diff-file--${file.path}`}
            >
              <span>{file.path}</span>
              <small>+{file.additions || 0} -{file.deletions || 0}</small>
            </button>
          ))}
        </div>
      ) : null}
      <DiffView
        title={surface.focusedFilePath || surface.title}
        diff={surface.focusedDiff || surface.rawDiff}
      />
    </section>
  );
}
