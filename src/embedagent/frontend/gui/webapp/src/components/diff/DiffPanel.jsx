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
  const [diffRenderMode, setDiffRenderMode] = React.useState("stacked");
  const [diffWordWrap, setDiffWordWrap] = React.useState(false);
  const [diffIgnoreWhitespace, setDiffIgnoreWhitespace] = React.useState(false);
  const [collapsedDiffFilePaths, setCollapsedDiffFilePaths] = React.useState(() => new Set());
  const patchViewportRef = React.useRef(null);

  React.useEffect(() => {
    if (!surface?.focusedFilePath || !patchViewportRef.current) return;
    const target = Array.from(
      patchViewportRef.current.querySelectorAll("[data-diff-file-path]"),
    ).find((element) => element.dataset.diffFilePath === surface.focusedFilePath);
    target?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [surface?.focusedFilePath, surface?.focusedDiff]);

  if (!surface) {
    return <div className="empty-copy">No diff selected.</div>;
  }
  const files = Array.isArray(surface.files) ? surface.files : [];
  const focusedFile = files.find((file) => file.path === surface.focusedFilePath) || files[0] || null;
  const focusedPath = focusedFile?.path || surface.focusedFilePath || "";
  const focusedCollapsed = focusedPath ? collapsedDiffFilePaths.has(focusedPath) : false;
  const toggleCollapsedFile = (path) => {
    setCollapsedDiffFilePaths((current) => {
      const next = new Set(current);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };
  const viewportClassName = [
    "diff-panel-viewport",
    diffRenderMode === "split" ? "split" : "stacked",
    diffWordWrap ? "word-wrap" : "",
    diffIgnoreWhitespace ? "ignore-whitespace" : "",
  ].filter(Boolean).join(" ");
  return (
    <section className="diff-panel" data-testid="diff-panel">
      <header className="surface-subheader diff-panel-subheader" data-surface-subheader>
        <div className="diff-selection-chip-strip" aria-label="Diff selection">
          <button type="button" className="diff-selection-chip active" title={surface.title || "Diff"}>
            <span>{surface.title || "Diff"}</span>
          </button>
          {focusedPath ? (
            <button type="button" className="diff-selection-chip" title={focusedPath}>
              <span>{focusedPath}</span>
            </button>
          ) : null}
        </div>
        <div className="diff-panel-controls" aria-label="Diff controls">
          <button
            type="button"
            className={`diff-panel-control${diffRenderMode === "stacked" ? " active" : ""}`}
            data-testid="diff-mode-toggle--stacked"
            aria-pressed={diffRenderMode === "stacked"}
            title="Stacked diff view"
            onClick={() => setDiffRenderMode("stacked")}
          >
            S
          </button>
          <button
            type="button"
            className={`diff-panel-control${diffRenderMode === "split" ? " active" : ""}`}
            data-testid="diff-mode-toggle--split"
            aria-pressed={diffRenderMode === "split"}
            title="Split diff view"
            onClick={() => setDiffRenderMode("split")}
          >
            ||
          </button>
          <button
            type="button"
            className={`diff-panel-control${diffWordWrap ? " active" : ""}`}
            data-testid="diff-wrap-toggle"
            aria-pressed={diffWordWrap}
            title={diffWordWrap ? "Disable line wrapping" : "Enable line wrapping"}
            onClick={() => setDiffWordWrap((value) => !value)}
          >
            W
          </button>
          <button
            type="button"
            className={`diff-panel-control${diffIgnoreWhitespace ? " active" : ""}`}
            data-testid="diff-whitespace-toggle"
            aria-pressed={diffIgnoreWhitespace}
            title={diffIgnoreWhitespace ? "Show whitespace changes" : "Hide whitespace changes"}
            onClick={() => setDiffIgnoreWhitespace((value) => !value)}
          >
            ¶
          </button>
        </div>
      </header>
      <div className="diff-panel-body">
        {files.length > 0 ? (
          <aside className="diff-file-rail" data-testid="diff-file-rail" aria-label="Changed files">
            <div className="diff-file-rail-label">
              <span>Files</span>
              <span>{files.length}</span>
            </div>
            <div className="diff-file-list">
              {files.map((file) => {
                const collapsed = collapsedDiffFilePaths.has(file.path);
                return (
                  <div
                    key={file.path}
                    className={`diff-file-row${file.path === surface.focusedFilePath ? " active" : ""}${collapsed ? " collapsed" : ""}`}
                  >
                    <button
                      type="button"
                      className="diff-file-collapse"
                      data-testid={`diff-file-collapse--${file.path}`}
                      aria-label={collapsed ? `Expand ${file.path}` : `Collapse ${file.path}`}
                      aria-expanded={!collapsed}
                      onClick={(event) => {
                        event.stopPropagation();
                        toggleCollapsedFile(file.path);
                      }}
                    >
                      {collapsed ? ">" : "v"}
                    </button>
                    <button
                      type="button"
                      className="diff-file-main"
                      onClick={() => onFocusFile && onFocusFile(file.path)}
                      data-testid={`diff-file--${file.path}`}
                    >
                      <span>{file.path}</span>
                      <DiffStatLabel additions={file.additions || 0} deletions={file.deletions || 0} />
                    </button>
                  </div>
                );
              })}
            </div>
          </aside>
        ) : null}
        <div className={viewportClassName} ref={patchViewportRef}>
          {focusedCollapsed ? (
            <div className="diff-collapsed-placeholder" data-diff-file-path={focusedPath}>
              <span>{focusedPath}</span>
              <button type="button" onClick={() => toggleCollapsedFile(focusedPath)}>
                Expand diff
              </button>
            </div>
          ) : (
            <div data-diff-file-path={focusedPath || "raw"}>
              <DiffView
                title={surface.focusedFilePath || surface.title}
                diff={surface.focusedDiff || surface.rawDiff}
              />
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
