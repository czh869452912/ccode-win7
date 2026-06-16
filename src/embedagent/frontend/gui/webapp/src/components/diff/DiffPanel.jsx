import React from "react";

import DiffView from "../DiffView.jsx";

function DiffStatLabel({ additions = 0, deletions = 0 }) {
  return (
    <span className="diff-stat-label">
      <span className="diff-stat-add">+{additions || 0}</span>
      <span className="diff-stat-del">-{deletions || 0}</span>
    </span>
  );
}

export default function DiffPanel({ surface, onFocusFile }) {
  if (!surface) {
    return <div className="empty-copy">No diff selected.</div>;
  }
  const files = Array.isArray(surface.files) ? surface.files : [];
  const focusedFile = files.find((file) => file.path === surface.focusedFilePath) || files[0] || null;
  return (
    <section className="diff-panel" data-testid="diff-panel">
      <header className="diff-panel-header">
        <div className="diff-panel-title">
          <strong>{surface.title || "Diff"}</strong>
          <span>{focusedFile?.path || surface.source || "Unified diff"}</span>
        </div>
        <div className="diff-panel-meta">
          <span>{files.length} files</span>
          {files.length > 0 ? (
            <DiffStatLabel additions={surface.additions || 0} deletions={surface.deletions || 0} />
          ) : null}
        </div>
      </header>
      <div className="diff-panel-body">
        {files.length > 0 ? (
          <aside className="diff-file-rail" data-testid="diff-file-rail" aria-label="Changed files">
            <div className="diff-file-rail-label">Files</div>
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
                  <DiffStatLabel additions={file.additions || 0} deletions={file.deletions || 0} />
                </button>
              ))}
            </div>
          </aside>
        ) : null}
        <div className="diff-panel-viewport">
          <DiffView
            title={surface.focusedFilePath || surface.title}
            diff={surface.focusedDiff || surface.rawDiff}
          />
        </div>
      </div>
    </section>
  );
}
