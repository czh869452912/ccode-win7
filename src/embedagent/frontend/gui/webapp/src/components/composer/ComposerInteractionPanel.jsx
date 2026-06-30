import React from "react";

import {
  buildPermissionResponse,
  buildUserInputResponse,
  normalizeComposerInteraction,
} from "../../session-runtime/interaction-model.js";

export default function ComposerInteractionPanel({
  interaction,
  notice,
  busy = false,
  answerValue = "",
  onAnswerChange,
  onRespond,
}) {
  const view = normalizeComposerInteraction(interaction, notice);
  const [remember, setRemember] = React.useState(false);

  React.useEffect(() => {
    setRemember(false);
  }, [view?.interactionId]);

  if (!view) return null;
  if (view.kind === "notice") {
    return <NoticePanel view={view} />;
  }
  if (view.kind === "permission") {
    return (
      <PermissionPanel
        view={view}
        remember={remember}
        onRememberChange={setRemember}
        busy={busy}
        onRespond={onRespond}
      />
    );
  }
  return (
    <UserInputPanel
      view={view}
      busy={busy}
      answerValue={answerValue}
      onAnswerChange={onAnswerChange}
      onRespond={onRespond}
    />
  );
}

function NoticePanel({ view }) {
  return (
    <section
      className={`composer-interaction-panel notice ${view.tone || ""}`}
      role="status"
      data-testid="composer-interaction-notice"
    >
      <div className="composer-interaction-kicker">{view.title}</div>
      <div className="composer-interaction-text">{view.detail || view.body}</div>
    </section>
  );
}

function PermissionPanel({ view, remember, onRememberChange, busy = false, onRespond }) {
  return (
    <section
      className="composer-interaction-panel permission"
      role="dialog"
      aria-label={view.summary}
      data-testid="composer-interaction-panel"
    >
      <div className="composer-interaction-heading">
        <span className="composer-interaction-kicker">PENDING APPROVAL</span>
        <span className="composer-interaction-summary">{view.summary}</span>
      </div>
      <div className="composer-interaction-body">
        {view.toolName ? <code>{view.toolName}</code> : null}
        {view.reason ? <span>{view.reason}</span> : null}
      </div>
      {view.detailRows.length > 0 ? (
        <div className="composer-interaction-details">
          {view.detailRows.slice(0, 4).map((row) => (
            <span key={row.label}>
              <strong>{row.label}</strong>
              <code>{row.value}</code>
            </span>
          ))}
        </div>
      ) : null}
      <div className="composer-interaction-actions">
        <label className="composer-remember">
          <input
            type="checkbox"
            checked={remember}
            disabled={busy}
            onChange={(event) => onRememberChange(event.target.checked)}
          />
          <span>{view.rememberLabel}</span>
        </label>
        <button
          type="button"
          className="ghost btn-deny"
          disabled={busy}
          onClick={() => onRespond && onRespond(buildPermissionResponse(view, { decision: false }))}
          data-testid="permission-deny-button"
        >
          {view.secondaryLabel}
        </button>
        <button
          type="button"
          className="primary"
          disabled={busy}
          onClick={() => onRespond && onRespond(buildPermissionResponse(view, { decision: true, remember }))}
          data-testid="permission-approve-button"
        >
          {view.primaryLabel}
        </button>
      </div>
    </section>
  );
}

function UserInputPanel({ view, busy = false, answerValue, onAnswerChange, onRespond }) {
  const hasAnswer = String(answerValue || "").trim().length > 0;
  return (
    <section
      className="composer-interaction-panel user-input"
      role="dialog"
      aria-label={view.summary}
      data-testid="composer-interaction-panel"
    >
      <div className="composer-interaction-heading">
        <span className="composer-interaction-kicker">INPUT REQUIRED</span>
        <span className="composer-interaction-summary">{view.question || view.summary}</span>
      </div>
      {view.options.length > 0 ? (
        <div className="composer-option-list">
          {view.options.map((option) => (
            <button
              key={`${option.index}-${option.text}`}
              type="button"
              className="composer-option"
              disabled={busy}
              onClick={() => onRespond && onRespond(buildUserInputResponse(view, { option }))}
              data-testid={`user-input-option-${option.index}`}
            >
              {option.shortcut ? <kbd>{option.shortcut}</kbd> : null}
              <span>
                <strong>{option.text}</strong>
                {option.description ? <small>{option.description}</small> : null}
              </span>
              {option.mode ? <em>mode: {option.mode}</em> : null}
            </button>
          ))}
        </div>
      ) : null}
      <div className="composer-custom-answer">
        <textarea
          value={answerValue || ""}
          onChange={(event) => onAnswerChange && onAnswerChange(event.target.value)}
          placeholder={view.customPlaceholder}
          aria-label={view.customPlaceholder}
          disabled={busy}
          rows={2}
          data-testid="user-input-custom-answer"
        />
        <button
          type="button"
          className="primary"
          disabled={busy || !hasAnswer}
          onClick={() => onRespond && onRespond(buildUserInputResponse(view, { answer: answerValue }))}
          data-testid="user-input-submit-button"
        >
          {view.submitLabel}
        </button>
      </div>
    </section>
  );
}
