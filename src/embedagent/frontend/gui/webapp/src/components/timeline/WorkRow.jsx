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

function statusLabel(row, workRowChrome = {}) {
  const indicator = row.presentation?.statusIndicator || "";
  const labels = workRowChrome.statusLabels || {};
  if (indicator === "failure") return labels.failure || "";
  if (indicator === "success") return labels.success || "";
  if (indicator === "neutral") return labels.neutral || "";
  if (row.tone === "interrupted") return labels.interrupted || "";
  if (row.tone === "discarded") return labels.discarded || "";
  if (row.status === "success") return labels.success || "";
  if (row.status === "error") return labels.failure || "";
  return row.status || "";
}

function WorkEntryIcon({ name }) {
  const path = WORK_ENTRY_ICONS[name];
  if (!path) return null;
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

export default function WorkRow({
  row,
  density = "compact",
  expanded = false,
  onToggle = null,
  rowKey = "",
  onOpenFile = null,
  toolDetailChrome = {},
  workRowChrome = {},
}) {
  const presentation = row.presentation || {
    heading: row.label || row.toolName || workRowChrome.defaultHeading || "",
    preview: row.commandPreview || "",
    iconName: workRowChrome.defaultIconName || "",
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
      className={`tool-activity-row ${row.tone || "neutral"} density-${density || "compact"}`}
      data-testid="timeline-work-row"
      data-row-kind="work"
      data-row-key={rowKey}
      data-density={density || "compact"}
      data-icon-name={presentation.iconName}
      data-status-indicator={presentation.statusIndicator}
    >
      <button
        className="tool-activity-summary"
        type="button"
        onClick={handleToggle}
        aria-expanded={expanded}
        title={presentation.preview ? `${presentation.heading} - ${presentation.preview}` : presentation.heading}
      >
        <span className={`tool-activity-icon ${presentation.iconTone || "normal"}`} aria-hidden="true">
          <WorkEntryIcon name={presentation.iconName} />
        </span>
        <span className={`tool-activity-label ${presentation.headingTone || "normal"}`}>{presentation.heading}</span>
        {presentation.preview ? <span className="tool-activity-preview">{presentation.preview}</span> : <span />}
        <span className="tool-activity-status-slot" aria-label={statusLabel(row, workRowChrome) || undefined}>
          {hasDetail ? <span className={`tool-activity-chevron${expanded ? " expanded" : ""}`} aria-hidden="true">v</span> : null}
          <span className={`tool-activity-status-indicator ${presentation.statusIndicator || "none"}`} aria-hidden="true">
            <StatusIndicator indicator={presentation.statusIndicator} />
          </span>
        </span>
      </button>
      {expanded && hasDetail ? (
        <div className="tool-activity-detail timeline-work-detail" data-testid="timeline-work-detail">
          {row.detailModel ? (
            <ToolDetail
              model={row.detailModel}
              onOpenFile={onOpenFile}
              chrome={toolDetailChrome}
            />
          ) : null}
          {presentation.expandedBody ? <pre className="tool-activity-detail-text">{presentation.expandedBody}</pre> : null}
          {!row.detailModel && !presentation.expandedBody && row.detail ? (
            <pre className="tool-activity-detail-text">{row.detail}</pre>
          ) : null}
          {Array.isArray(row.changedFiles) && row.changedFiles.length > 0 ? (
            <div className="tool-activity-file-list">
              {row.changedFiles.map((file) => (
                <span key={file.path} className="tool-activity-file">{file.path}</span>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
