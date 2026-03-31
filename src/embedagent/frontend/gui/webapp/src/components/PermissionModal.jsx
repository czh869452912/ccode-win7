import React from "react";

export default function PermissionModal({ permission, onApprove, onDeny }) {
  if (!permission) return null;
  return (
    <div className="modal-backdrop">
      <div className="modal-card">
        <div className="modal-header">
          <span className="modal-icon">⚠</span>
          <h3>Permission Required</h3>
        </div>
        {permission.tool_name ? (
          <div className="modal-tool-row">
            <span className="modal-tool-label">Tool</span>
            <code>{permission.tool_name}</code>
          </div>
        ) : null}
        <p className="modal-reason">{permission.reason}</p>
        {permission.details && Object.keys(permission.details).length > 0 ? (
          <details className="modal-details">
            <summary>Show details</summary>
            <pre>{JSON.stringify(permission.details, null, 2)}</pre>
          </details>
        ) : null}
        <div className="modal-actions">
          <button className="ghost btn-deny" onClick={onDeny}>
            Deny
          </button>
          <button className="primary" onClick={onApprove}>
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}
