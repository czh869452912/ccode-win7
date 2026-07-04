import React from "react";

function ToolbarButton({ children, title, disabled = false, onClick, testId }) {
  return (
    <button
      type="button"
      className="branch-toolbar-button"
      title={title}
      disabled={disabled}
      onClick={onClick}
      data-testid={testId}
    >
      {children}
    </button>
  );
}

export default function BranchToolbar({ model, onRefresh }) {
  if (!model?.visible) return null;

  const disabledTitle = model.disabledReason || model.readOnlyActionTitle || "";

  return (
    <div
      className={`branch-toolbar repo-${model.repoState || "unknown"}`}
      data-testid="branch-toolbar"
    >
      <div className="branch-toolbar-context" data-testid="branch-toolbar-mode">
        <span className="branch-toolbar-icon" aria-hidden="true">
          ⌁
        </span>
        <span className="branch-toolbar-main">
          <span className="branch-toolbar-label">{model.modeLabel}</span>
          <span className="branch-toolbar-subtle">{model.workspaceLabel}</span>
        </span>
      </div>
      <div className="branch-toolbar-spacer" />
      <div
        className={`branch-toolbar-branch tone-${model.branchTone || "muted"}`}
        data-testid="branch-toolbar-branch"
        title={model.disabled ? disabledTitle : model.branchLabel}
      >
        <span className="branch-toolbar-icon" aria-hidden="true">
          ⑂
        </span>
        <span className="branch-toolbar-main">
          <span className="branch-toolbar-label">{model.branchLabel}</span>
          <span className="branch-toolbar-subtle">{model.branchMetaLabel}</span>
        </span>
      </div>
      <ToolbarButton title={disabledTitle} disabled testId="branch-toolbar-worktree">
        {model.worktreeLabel}
      </ToolbarButton>
      <ToolbarButton title={disabledTitle} disabled testId="branch-toolbar-actions">
        {model.branchActionLabel}
      </ToolbarButton>
      {model.canRefresh ? (
        <ToolbarButton
          title={model.refreshTitle}
          onClick={onRefresh}
          testId="branch-toolbar-refresh"
        >
          {model.refreshLabel}
        </ToolbarButton>
      ) : null}
    </div>
  );
}
