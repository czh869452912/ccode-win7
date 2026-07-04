import React from "react";

export default function ComposerPrimaryActions({
  isRunning,
  disabled,
  canSend,
  onSend,
  onStop,
  sendLabel = "",
  stopLabel = "",
}) {
  if (isRunning) {
    return (
      <button
        className="composer-stop-action"
        type="button"
        onClick={onStop}
        aria-label={stopLabel}
        title={stopLabel}
        data-testid="composer-stop-action"
      >
        <span aria-hidden="true">■</span>
      </button>
    );
  }

  return (
    <button
      className="composer-primary-action"
      type="button"
      onClick={onSend}
      disabled={Boolean(disabled || !canSend)}
      aria-label={sendLabel}
      title={sendLabel}
      data-testid="composer-primary-action"
    >
      <span aria-hidden="true">↑</span>
    </button>
  );
}
