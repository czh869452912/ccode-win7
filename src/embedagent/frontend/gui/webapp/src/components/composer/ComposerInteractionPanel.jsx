import { normalizeComposerInteraction } from "../../session-runtime/interaction-model.js";
import ComposerPendingApprovalActions from "./ComposerPendingApprovalActions.jsx";
import ComposerPendingApprovalPanel from "./ComposerPendingApprovalPanel.jsx";
import ComposerPendingUserInputPanel from "./ComposerPendingUserInputPanel.jsx";

export default function ComposerInteractionPanel({
  interaction,
  notice,
  chrome = {},
  busy = false,
  onRespond,
}) {
  const view = normalizeComposerInteraction(interaction, notice, chrome);

  if (!view) return null;
  if (view.kind === "notice") {
    return <NoticePanel view={view} />;
  }
  if (view.kind === "permission") {
    return (
      <section
        className="composer-interaction-panel permission"
        role="dialog"
        aria-label={view.summary}
        data-testid="composer-interaction-panel"
      >
        <ComposerPendingApprovalPanel approval={view} />
        <ComposerPendingApprovalActions approval={view} busy={busy} onRespond={onRespond} />
      </section>
    );
  }
  return (
    <section
      className="composer-interaction-panel user-input"
      role="dialog"
      aria-label={view.summary}
      data-testid="composer-interaction-panel"
    >
      <ComposerPendingUserInputPanel prompt={view} busy={busy} onRespond={onRespond} />
    </section>
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
