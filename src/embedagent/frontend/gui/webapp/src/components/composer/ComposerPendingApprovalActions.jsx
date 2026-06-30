import { buildPermissionResponse } from "../../session-runtime/interaction-model.js";

export default function ComposerPendingApprovalActions({ approval, busy = false, onRespond }) {
  if (!approval) return null;
  const send = (decision) => {
    if (busy || !onRespond) return;
    onRespond(buildPermissionResponse(approval, decision));
  };
  return (
    <div className="composer-interaction-actions">
      <button type="button" className="ghost" disabled={busy} onClick={() => send("cancel")}>
        Cancel turn
      </button>
      <button
        type="button"
        className="ghost btn-deny"
        disabled={busy}
        onClick={() => send("decline")}
        data-testid="permission-deny-button"
      >
        {approval.secondaryLabel || "Decline"}
      </button>
      <button
        type="button"
        className="ghost"
        disabled={busy}
        onClick={() => send("acceptForSession")}
      >
        Always allow this session
      </button>
      <button
        type="button"
        className="primary"
        disabled={busy}
        onClick={() => send("accept")}
        data-testid="permission-approve-button"
      >
        {approval.primaryLabel || "Approve once"}
      </button>
    </div>
  );
}
