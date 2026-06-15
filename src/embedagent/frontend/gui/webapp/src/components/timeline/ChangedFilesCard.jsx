import React from "react";

export default function ChangedFilesCard({ row, onOpenDiff }) {
  const files = row.files || row.changedFiles || [];
  if (!files.length) return null;
  return (
    <section className="t3-changed-files-card" data-testid="changed-files-card" data-row-kind="diff_summary">
      <button
        className="t3-changed-files-title"
        type="button"
        onClick={() => onOpenDiff && onOpenDiff({ turnId: row.turnId || "", filePath: "" })}
      >
        <span>{files.length} files changed</span>
        <span className="t3-diff-stats">+{row.additions || 0} -{row.deletions || 0}</span>
      </button>
      <div className="t3-changed-files-list">
        {files.map((file) => (
          <button
            key={file.path}
            type="button"
            className="t3-changed-file"
            onClick={() => onOpenDiff && onOpenDiff({ turnId: row.turnId || "", filePath: file.path })}
          >
            <span>{file.path}</span>
            <span className="t3-diff-stats">+{file.additions || 0} -{file.deletions || 0}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
