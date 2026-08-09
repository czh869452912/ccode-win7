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

function formatChromeTemplate(template, values = {}) {
  return String(template || "").replace(/\{title\}/g, String(values.title || ""));
}

function lineCountLabel(count, chrome = {}) {
  const label = count === 1 ? chrome.lineSingularLabel : chrome.linePluralLabel;
  return `${count} ${label || ""}`.trim();
}

function FilePreviewBreadcrumbs({ projectName, filePath, filePreviewChrome }) {
  const crumbs = fileBreadcrumbs(projectName, filePath, filePreviewChrome);
  return (
    <nav
      className="file-preview-breadcrumbs"
      data-testid="file-preview-breadcrumbs"
      aria-label={filePreviewChrome.breadcrumbAriaLabel || ""}
    >
      {crumbs.map((crumb, index) => (
        <span
          key={crumb.path || `crumb-${index}`}
          className={`file-preview-crumb ${crumb.kind}`}
          data-current-file-crumb={crumb.kind === "file" ? "true" : "false"}
        >
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
    <div className="file-preview-code" data-testid="file-preview-content">
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

export default function FilePreviewSurface({
  surface,
  filePreview,
  filePreviewChrome = {},
  projectName,
  onReload,
  onOpenFilesSurface,
}) {
  const filePath = normalizeFilePath(surface?.filePath || surface?.resourceId);
  const status = statusForPreview(filePreview);
  const title = filePreview?.title || surface?.title || fileNameForPath(filePath, filePreviewChrome);
  const markdown = isMarkdownPreviewFile(filePath);
  const breadcrumbRef = useRef(null);

  const [mode, setMode] = useState(() => defaultFilePreviewMode(filePath));
  useEffect(() => {
    setMode(defaultFilePreviewMode(filePath));
  }, [filePath]);

  useEffect(() => {
    const currentCrumb = breadcrumbRef.current?.querySelector("[data-current-file-crumb='true']");
    currentCrumb?.scrollIntoView({ block: "nearest", inline: "end" });
  }, [filePath]);

  const content = filePreview?.content || "";
  const meta = filePreviewMeta(content, filePath, filePreviewChrome);
  const metaSeparator = filePreviewChrome.metadataSeparator || "";
  const lineText = lineCountLabel(meta.lineCount, filePreviewChrome);
  const metaTitle = [meta.language, lineText].filter(Boolean).join(metaSeparator);
  const metaLabel = [meta.language, String(meta.lineCount)].filter(Boolean).join(metaSeparator);
  const showPreview = markdown && mode === FILE_PREVIEW_MODES.PREVIEW;
  const markdownToggleLabel = showPreview
    ? filePreviewChrome.showMarkdownSourceLabel
    : filePreviewChrome.showRenderedMarkdownLabel;
  const markdownToggleGlyph = showPreview
    ? filePreviewChrome.markdownSourceGlyph
    : filePreviewChrome.markdownPreviewGlyph;
  const revealLine = fileRevealLine(content, surface?.revealLine);
  const revealRequestId = surface?.revealRequestId || 0;
  const handleCopyPath = () => {
    if (!filePath || !navigator?.clipboard?.writeText) return;
    void navigator.clipboard.writeText(filePath).catch(() => {});
  };

  return (
    <div className="file-preview-surface" data-testid="file-preview-surface" data-file-path={filePath}>
      <div className="surface-subheader file-preview-subheader" data-surface-subheader>
        <div ref={breadcrumbRef} className="file-preview-breadcrumb-scroll" data-file-breadcrumbs>
          <FilePreviewBreadcrumbs
            projectName={projectName}
            filePath={filePath}
            filePreviewChrome={filePreviewChrome}
          />
        </div>
        <span className="file-preview-meta" title={metaTitle}>
          {metaLabel}
        </span>
        <button
          type="button"
          className="file-preview-action-icon"
          data-testid="file-preview-open-action"
          title={formatChromeTemplate(filePreviewChrome.copyPathTitleTemplate, { title })}
          aria-label={formatChromeTemplate(filePreviewChrome.copyPathTitleTemplate, { title })}
          onClick={handleCopyPath}
        >
          O
        </button>
        {markdown ? (
          <button
            type="button"
            className={`file-preview-action-icon file-preview-mode-toggle${showPreview ? " active" : ""}`}
            data-testid="file-preview-mode-toggle"
            aria-pressed={showPreview}
            title={markdownToggleLabel}
            aria-label={markdownToggleLabel}
            onClick={() =>
              setMode(showPreview ? FILE_PREVIEW_MODES.CODE : FILE_PREVIEW_MODES.PREVIEW)
            }
          >
            {markdownToggleGlyph}
          </button>
        ) : null}
        <button
          type="button"
          className="file-preview-action-icon"
          data-testid="file-preview-explorer-toggle"
          title={filePreviewChrome.showFileExplorerLabel}
          aria-label={filePreviewChrome.showFileExplorerLabel}
          onClick={() => onOpenFilesSurface && onOpenFilesSurface()}
        >
          F
        </button>
      </div>
      {status === "loading" ? (
        <div className="file-preview-loading">{filePreviewChrome.loadingMessage}</div>
      ) : null}
      {status === "error" ? (
        <div className="file-preview-error" role="alert">
          <span>{filePreview?.error || filePreviewChrome.unavailableMessage}</span>
          {onReload ? (
            <button type="button" onClick={() => onReload(filePath)}>
              {filePreviewChrome.retryLabel}
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
