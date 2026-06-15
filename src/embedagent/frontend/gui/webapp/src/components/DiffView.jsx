import React from "react";
import { html as diffHtml } from "diff2html";

/**
 * Renders a unified-diff string using diff2html.
 * Only renders when `diff` is a non-empty string.
 */
export default function DiffView({ diff, title }) {
  if (!diff || typeof diff !== "string") return null;

  let rendered = "";
  try {
    rendered = diffHtml(diff, {
      drawFileList: false,
      matching: "lines",
      outputFormat: "line-by-line",
      highlight: false,
    });
  } catch (_) {
    rendered = "";
  }

  if (!rendered) {
    return (
      <div className="diff-view">
        {title ? <div className="diff-view-title">{title}</div> : null}
        <pre className="diff-raw-fallback">{diff}</pre>
      </div>
    );
  }

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
