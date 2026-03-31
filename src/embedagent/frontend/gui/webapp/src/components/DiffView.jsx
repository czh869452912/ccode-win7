import React from "react";
import { html as diffHtml } from "diff2html";

/**
 * Renders a unified-diff string using diff2html.
 * Only renders when `diff` is a non-empty string.
 */
export default function DiffView({ diff, title }) {
  if (!diff || typeof diff !== "string") return null;

  const rendered = diffHtml(diff, {
    drawFileList: false,
    matching: "lines",
    outputFormat: "line-by-line",
    highlight: false,
  });

  return (
    <div className="diff-view">
      {title ? <div className="diff-view-title">{title}</div> : null}
      <div
        className="diff-view-body"
        dangerouslySetInnerHTML={{ __html: rendered }}
      />
    </div>
  );
}
