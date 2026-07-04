export default function ComposerPendingApprovalPanel({ approval }) {
  if (!approval) return null;
  return (
    <>
      <div className="composer-interaction-heading">
        <span className="composer-interaction-kicker">{approval.kicker}</span>
        <span className="composer-interaction-summary">{approval.summary}</span>
      </div>
      <div className="composer-interaction-body">
        {approval.toolName ? <code>{approval.toolName}</code> : null}
        {approval.reason ? <span>{approval.reason}</span> : null}
      </div>
      {approval.detailRows?.length > 0 ? (
        <div className="composer-interaction-details">
          {approval.detailRows.slice(0, 4).map((row) => (
            <span key={row.label}>
              <strong>{row.label}</strong>
              <code>{row.value}</code>
            </span>
          ))}
        </div>
      ) : null}
    </>
  );
}
