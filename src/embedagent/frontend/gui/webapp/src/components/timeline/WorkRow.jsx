import ToolDetail from "./ToolDetail.jsx";

const WORK_ENTRY_ICONS = {
  bot: "M11 3a8 8 0 0 0-8 8v4a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3v-4a8 8 0 0 0-8-8Zm-3 9h.01M14 12h.01M9 16h4",
  check: "M4 11l4 4 8-9",
  "circle-alert": "M11 3a8 8 0 1 0 0 16 8 8 0 0 0 0-16Zm0 4v5M11 15h.01",
  eye: "M2 11s3-5 9-5 9 5 9 5-3 5-9 5-9-5-9-5Zm9 2a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
  globe: "M11 3a8 8 0 1 0 0 16 8 8 0 0 0 0-16Zm-8 8h16M11 3c2 2 3 5 3 8s-1 6-3 8M11 3c-2 2-3 5-3 8s1 6 3 8",
  hammer: "M13 4l5 5-2 2-2-2-6 6-3-3 6-6-2-2 2-2 2 2Zm-8 9l4 4-2 2-4-4 2-2Z",
  "message-circle": "M4 5a8 8 0 0 1 13 9l1 4-4-1A8 8 0 1 1 4 5Z",
  "square-pen": "M4 5h8M4 17h12a1 1 0 0 0 1-1v-5M13 4l4 4-7 7H6v-4l7-7Z",
  terminal: "M4 6h14v11H4V6Zm3 3 3 2-3 2M11 14h4",
  wrench: "M14 4a4 4 0 0 0 4 5l-8 8a3 3 0 1 1-4-4l8-8Zm-8 11h.01",
  x: "M6 6l10 10M16 6 6 16",
  zap: "M12 2 5 12h6l-1 8 7-11h-6l1-7Z",
};

function statusLabel(row) {
  const indicator = row.presentation?.statusIndicator || "";
  if (indicator === "failure") return "failed";
  if (indicator === "success") return "completed";
  if (indicator === "neutral") return "empty";
  if (row.tone === "interrupted") return "cancelled";
  if (row.tone === "discarded") return "skipped";
  if (row.status === "success") return "completed";
  if (row.status === "error") return "failed";
  return row.status || "";
}

function WorkEntryIcon({ name }) {
  const path = WORK_ENTRY_ICONS[name] || WORK_ENTRY_ICONS.zap;
  return (
    <svg viewBox="0 0 22 22" aria-hidden="true" focusable="false">
      <path d={path} />
    </svg>
  );
}

function StatusIndicator({ indicator }) {
  if (indicator === "failure") return <WorkEntryIcon name="x" />;
  if (indicator === "success") return <WorkEntryIcon name="check" />;
  if (indicator === "neutral") return <span aria-hidden="true">-</span>;
  return null;
}

export default function WorkRow({ row, expanded = false, onToggle = null, rowKey = "" }) {
  const presentation = row.presentation || {
    heading: row.label || row.toolName || "Work",
    preview: row.commandPreview || "",
    iconName: "zap",
    statusIndicator: row.status === "error" ? "failure" : row.status === "success" ? "success" : "",
    headingTone: row.status === "error" ? "error" : "normal",
    iconTone: row.status === "error" ? "error" : "normal",
    canExpand: Boolean(row.detailModel || row.detail || row.commandPreview),
    expandedBody: row.detail || row.commandPreview || "",
  };
  const hasDetail = Boolean(
    row.detailModel ||
      presentation.expandedBody ||
      row.detail ||
      row.commandPreview ||
      (Array.isArray(row.changedFiles) && row.changedFiles.length > 0),
  );

  function handleToggle() {
    if (hasDetail && onToggle) onToggle(rowKey);
  }

  return (
    <div
      className={`t3-work-row ${row.tone || "neutral"}`}
      data-testid="timeline-work-row"
      data-row-kind="work"
      data-row-key={rowKey}
      data-icon-name={presentation.iconName}
      data-status-indicator={presentation.statusIndicator}
    >
      <button
        className="t3-work-summary"
        type="button"
        onClick={handleToggle}
        aria-expanded={expanded}
        title={presentation.preview ? `${presentation.heading} - ${presentation.preview}` : presentation.heading}
      >
        <span className={`t3-work-icon ${presentation.iconTone || "normal"}`} aria-hidden="true">
          <WorkEntryIcon name={presentation.iconName} />
        </span>
        <span className={`t3-work-label ${presentation.headingTone || "normal"}`}>{presentation.heading}</span>
        {presentation.preview ? <span className="t3-work-preview">{presentation.preview}</span> : <span />}
        <span className="t3-work-status-slot" aria-label={statusLabel(row) || undefined}>
          {hasDetail ? <span className={`t3-work-chevron${expanded ? " expanded" : ""}`} aria-hidden="true">v</span> : null}
          <span className={`t3-work-status-indicator ${presentation.statusIndicator || "none"}`} aria-hidden="true">
            <StatusIndicator indicator={presentation.statusIndicator} />
          </span>
        </span>
      </button>
      {expanded && hasDetail ? (
        <div className="t3-work-detail timeline-work-detail" data-testid="timeline-work-detail">
          {row.detailModel ? <ToolDetail model={row.detailModel} /> : null}
          {presentation.expandedBody ? <pre className="t3-work-detail-text">{presentation.expandedBody}</pre> : null}
          {!row.detailModel && !presentation.expandedBody && row.detail ? (
            <pre className="t3-work-detail-text">{row.detail}</pre>
          ) : null}
          {Array.isArray(row.changedFiles) && row.changedFiles.length > 0 ? (
            <div className="t3-work-file-list">
              {row.changedFiles.map((file) => (
                <span key={file.path} className="t3-work-file">{file.path}</span>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
