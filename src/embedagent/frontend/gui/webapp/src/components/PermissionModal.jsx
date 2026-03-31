import React from "react";
import { useLang } from "../LangContext.js";
import { t } from "../strings.js";

export default function PermissionModal({ permission, onApprove, onDeny }) {
  const lang = useLang();

  if (!permission) return null;
  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={t("modal.permissionRequired", lang)}
    >
      <div className="modal-card">
        <div className="modal-header">
          <span className="modal-icon" aria-hidden="true">⚠</span>
          <h3>{t("modal.permissionRequired", lang)}</h3>
        </div>
        {permission.tool_name ? (
          <div className="modal-tool-row">
            <span className="modal-tool-label">{t("modal.tool", lang)}</span>
            <code>{permission.tool_name}</code>
          </div>
        ) : null}
        <p className="modal-reason">{permission.reason}</p>
        {permission.details && Object.keys(permission.details).length > 0 ? (
          <details className="modal-details">
            <summary>{t("modal.showDetails", lang)}</summary>
            <pre>{JSON.stringify(permission.details, null, 2)}</pre>
          </details>
        ) : null}
        <div className="modal-actions">
          <button className="ghost btn-deny" onClick={onDeny}>
            {t("modal.deny", lang)}
          </button>
          <button className="primary" onClick={onApprove}>
            {t("modal.approve", lang)}
          </button>
        </div>
      </div>
    </div>
  );
}
