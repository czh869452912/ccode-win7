import React, { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  FILE_PREVIEW_MODES,
  defaultFilePreviewMode,
  fileBreadcrumbs,
  fileNameForPath,
  filePreviewMeta,
  fileRevealLine,
  isMarkdownPreviewFile,
  normalizeFilePath,
  numberFileLines,
} from "../../session-runtime/file-preview-model.js";

function statusForPreview(filePreview) {
  if (!filePreview || !filePreview.status) return "loading";
  return filePreview.status;
}

function FilePreviewBreadcrumbs({ projectName, filePath }) {
  const crumbs = fileBreadcrumbs(projectName, filePath);
  return (
    <nav className="file-preview-breadcrumbs" data-testid="file-preview-breadcrumbs" aria-label="File path">
      {crumbs.map((crumb, index) => (
        <span key={crumb.path || `crumb-${index}`} className={`file-preview-crumb ${crumb.kind}`}>
          {index > 0 ? <span className="file-preview-crumb-sep" aria-hidden="true">/</span> : null}
          <span className="file-preview-crumb-label">{crumb.label}</span>
        </span>
      ))}
    </nav>
  );
}

function FilePreviewCode({ content, revealLine, revealRequestId }) {
  const lines = numberFileLines(content);
  const revealRef = useRef(null);

  useEffect(() => {
    if (!revealLine || !revealRef.current) return;
    revealRef.current.scrollIntoView({ block: "center", inline: "nearest" });
  }, [revealLine, revealRequestId]);

  return (
    <div className="file-preview-code" data-testid="right-panel-file-content">
      <div className="file-preview-gutter" data-testid="file-preview-gutter" aria-hidden="true">
        {lines.map((line) => {
          const revealed = line.number === revealLine;
          return (
            <div
              key={line.number}
              className={`file-preview-gutter-row${revealed ? " revealed" : ""}`}
              data-file-line-number={line.number}
              {...(revealed ? { "data-file-link-reveal": "" } : {})}
            >
              {line.number}
            </div>
          );
        })}
      </div>
      <div className="file-preview-lines">
        {lines.map((line) => {
          const revealed = line.number === revealLine;
          return (
            <div
              key={line.number}
              ref={revealed ? revealRef : null}
              className={`file-preview-line${revealed ? " revealed" : ""}`}
              data-file-line={line.number}
              {...(revealed ? { "data-file-link-reveal": "" } : {})}
            >
              {line.text || " "}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function FilePreviewSurface({ surface, filePreview, projectName, onReload }) {
  const filePath = normalizeFilePath(surface?.filePath || surface?.resourceId);
  const status = statusForPreview(filePreview);
  const title = filePreview?.title || surface?.title || fileNameForPath(filePath);
  const markdown = isMarkdownPreviewFile(filePath);

  const [mode, setMode] = useState(() => defaultFilePreviewMode(filePath));
  useEffect(() => {
    setMode(defaultFilePreviewMode(filePath));
  }, [filePath]);

  const content = filePreview?.content || "";
  const meta = filePreviewMeta(content, filePath);
  const showPreview = markdown && mode === FILE_PREVIEW_MODES.PREVIEW;
  const revealLine = fileRevealLine(content, surface?.revealLine);
  const revealRequestId = surface?.revealRequestId || 0;

  return (
    <div className="right-panel-file-surface" data-testid="right-panel-file-surface" data-file-path={filePath}>
      <div className="right-panel-file-header">
        <FilePreviewBreadcrumbs projectName={projectName} filePath={filePath} />
        <div className="file-preview-header-row">
          <strong className="file-preview-title">{title}</strong>
          <span className="file-preview-meta">
            {meta.language} · {meta.lineCount} {meta.lineCount === 1 ? "line" : "lines"}
          </span>
        </div>
        {markdown ? (
          <div className="file-preview-mode-toggle" data-testid="file-preview-mode-toggle" role="group" aria-label="Preview mode">
            <button
              type="button"
              className={mode === FILE_PREVIEW_MODES.PREVIEW ? "active" : ""}
              aria-pressed={mode === FILE_PREVIEW_MODES.PREVIEW}
              onClick={() => setMode(FILE_PREVIEW_MODES.PREVIEW)}
            >
              Preview
            </button>
            <button
              type="button"
              className={mode === FILE_PREVIEW_MODES.CODE ? "active" : ""}
              aria-pressed={mode === FILE_PREVIEW_MODES.CODE}
              onClick={() => setMode(FILE_PREVIEW_MODES.CODE)}
            >
              Code
            </button>
          </div>
        ) : null}
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
        showPreview ? (
          <div className="file-preview-markdown markdown-body" data-testid="file-preview-markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        ) : (
          <FilePreviewCode
            content={content}
            revealLine={revealLine}
            revealRequestId={revealRequestId}
          />
        )
      ) : null}
    </div>
  );
}
