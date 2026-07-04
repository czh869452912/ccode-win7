import { useLang } from "../LangContext.js";
import { t } from "../strings.js";

export default function InteractionPanel({
  interaction,
  notice,
}) {
  const lang = useLang();

  if (!interaction && !notice) {
    return <div className="empty-copy">{t("surface.noInteraction", lang)}</div>;
  }

  if (notice?.kind === "expired") {
    return (
      <div className="prompt-panel interaction-expired" role="status">
        <h3>{t("interaction.expiredTitle", lang)}</h3>
        <p>{t("interaction.expiredBody", lang)}</p>
      </div>
    );
  }

  if (notice?.kind === "conflict") {
    return (
      <div className="prompt-panel interaction-expired" role="status">
        <h3>{t("interaction.conflictTitle", lang)}</h3>
        <p>{t("interaction.conflictBody", lang)}</p>
      </div>
    );
  }

  if (!interaction) {
    return <div className="empty-copy">{t("surface.noInteraction", lang)}</div>;
  }

  if (interaction.kind === "permission") {
    return (
      <div className="prompt-panel" role="dialog" aria-label={t("modal.permissionRequired", lang)}>
        <h3>{t("modal.permissionRequired", lang)}</h3>
        {interaction.tool_name ? (
          <p><strong>{t("modal.tool", lang)}:</strong> <code>{interaction.tool_name}</code></p>
        ) : null}
        <p>{interaction.reason || ""}</p>
        {interaction.details && Object.keys(interaction.details).length > 0 ? (
          <details className="permission-details">
            <summary>{t("modal.showDetails", lang)}</summary>
            <pre>{JSON.stringify(interaction.details, null, 2)}</pre>
          </details>
        ) : null}
      </div>
    );
  }

  return (
    <div className="prompt-panel" role="dialog" aria-label={t("surface.inputRequired", lang)}>
      <h3>{t("surface.inputRequired", lang)}</h3>
      <p>{interaction.question || ""}</p>
      <div className="option-list">
        {(interaction.options || []).map((option) => (
          <div
            key={option.index}
            className="option-card"
          >
            <span>{option.text}</span>
            {option.mode ? <small>mode: {option.mode}</small> : null}
          </div>
        ))}
      </div>
    </div>
  );
}
