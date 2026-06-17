import React from "react";

import { groupSourceControlFiles } from "../../source-control/source-control-state.js";
import {
  changeSummary,
  fileStatusLabel,
  groupLabel,
  providerLabel,
} from "../../source-control/source-control-presentation.js";

function EmptyState({ children }) {
  return <div className="source-control-empty">{children}</div>;
}

function FileRow({ file, active, onSelectFile }) {
  const scope = file.diffScopes?.[0] || (file.group === "staged" ? "staged" : "unstaged");
  return (
    <button
      type="button"
      className={`source-control-file${active ? " active" : ""}`}
      onClick={() => onSelectFile && onSelectFile(file, scope)}
      data-testid={`source-control-file--${file.path}`}
    >
      <span className={`source-control-status status-${String(file.status || "").toLowerCase()}`}>
        {fileStatusLabel(file)}
      </span>
      <span className="source-control-path">{file.displayPath || file.path}</span>
      <span className="source-control-stats">{changeSummary(file)}</span>
    </button>
  );
}

function FileGroup({ group, files, selectedPath, onSelectFile }) {
  if (!files.length) return null;
  return (
    <section className="source-control-group">
      <div className="source-control-group-title">
        <span>{groupLabel(group)}</span>
        <span>{files.length}</span>
      </div>
      <div className="source-control-files">
        {files.map((file) => (
          <FileRow
            key={`${file.group}-${file.path}`}
            file={file}
            active={file.path === selectedPath}
            onSelectFile={onSelectFile}
          />
        ))}
      </div>
    </section>
  );
}

export default function SourceControlPanel({
  sourceControl,
  onRefresh,
  onSelectFile,
}) {
  const state = sourceControl || {};
  const data = state.data || {};
  const counts = data.counts || {};
  const grouped = groupSourceControlFiles(data.files || []);
  const busy = state.status === "loading";
  let body = null;

  if (state.status === "error") {
    body = <EmptyState>{state.error || "Source control unavailable."}</EmptyState>;
  } else if (busy) {
    body = <EmptyState>Loading changes...</EmptyState>;
  } else if (!data.gitAvailable) {
    body = <EmptyState>Git runtime is not available for this workspace.</EmptyState>;
  } else if (!data.isRepo) {
    body = <EmptyState>The active workspace is not a Git repository.</EmptyState>;
  } else if (!counts.total) {
    body = <EmptyState>No local changes.</EmptyState>;
  } else {
    body = (
      <div className="source-control-list">
        {["conflicted", "staged", "unstaged", "untracked"].map((group) => (
          <FileGroup
            key={group}
            group={group}
            files={grouped[group] || []}
            selectedPath={state.selectedPath}
            onSelectFile={onSelectFile}
          />
        ))}
      </div>
    );
  }

  return (
    <section className="source-control-panel" data-testid="source-control-panel">
      <header className="source-control-header">
        <div className="source-control-title">
          <strong>Source Control</strong>
          <div className="source-control-meta">
            <span className="source-control-branch">{data.branch || data.head || "No branch"}</span>
            <span>{providerLabel(data.provider)}</span>
            <span>{data.runtimeSource || (data.gitAvailable ? "git" : "missing")}</span>
          </div>
        </div>
        <div className="source-control-actions">
          <button
            type="button"
            className="ghost"
            onClick={() => onRefresh && onRefresh()}
            disabled={busy}
            data-testid="source-control-refresh"
          >
            Refresh
          </button>
        </div>
      </header>
      {data.isRepo && data.gitAvailable ? (
        <div className="source-control-counts">
          <span>{counts.total || 0} files</span>
          <span>{counts.staged || 0} staged</span>
          <span>{counts.unstaged || 0} changed</span>
          <span>{counts.untracked || 0} untracked</span>
        </div>
      ) : null}
      {state.diffStatus === "error" && state.diffError ? (
        <div className="source-control-warning">{state.diffError}</div>
      ) : null}
      {body}
    </section>
  );
}
