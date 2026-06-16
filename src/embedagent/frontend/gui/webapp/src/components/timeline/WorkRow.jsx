const TOOL_ICONS = {
  read_file: "R",
  list_dir: "L",
  glob_files: "G",
  grep_text: "S",
  write_file: "W",
  edit_file: "E",
  run_recipe: ">",
  report_quality_v2: "Q",
  record_failing_evidence: "!",
  task_status: "T",
  ask_user: "?",
};

function statusLabel(row) {
  if (row.tone === "interrupted") return "cancelled";
  if (row.tone === "discarded") return "skipped";
  if (row.status === "success") return "done";
  if (row.status === "error") return "error";
  return row.status || "running";
}

export default function WorkRow({ row, expanded = false, onToggle = null, rowKey = "" }) {
  const hasDetail = Boolean(
    row.detail || row.commandPreview || (Array.isArray(row.changedFiles) && row.changedFiles.length > 0),
  );
  const icon = TOOL_ICONS[row.toolName] || "*";

  function handleToggle() {
    if (hasDetail && onToggle) onToggle(rowKey);
  }

  return (
    <div
      className={`t3-work-row ${row.tone || "neutral"}`}
      data-testid="timeline-work-row"
      data-row-kind="work"
      data-row-key={rowKey}
    >
      <button
        className="t3-work-summary"
        type="button"
        onClick={handleToggle}
        aria-expanded={expanded}
        title={row.toolName || row.label}
      >
        <span className="t3-work-icon" aria-hidden="true">{icon}</span>
        <span className="t3-work-label">{row.label || row.toolName || "Work"}</span>
        {row.commandPreview ? <code className="t3-work-preview">{row.commandPreview}</code> : <span />}
        {Array.isArray(row.changedFiles) && row.changedFiles.length > 0 ? (
          <span className="t3-work-changes">+{row.additions || 0} -{row.deletions || 0}</span>
        ) : null}
        <span className={`t3-work-status ${row.status || "running"}`}>{statusLabel(row)}</span>
      </button>
      {expanded && hasDetail ? (
        <div className="t3-work-detail timeline-work-detail" data-testid="timeline-work-detail">
          {row.detail ? <pre>{row.detail}</pre> : null}
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
