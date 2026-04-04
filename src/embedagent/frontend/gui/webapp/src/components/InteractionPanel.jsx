import React from "react";
import { useLang } from "../LangContext.js";
import { t } from "../strings.js";

export default function InteractionPanel({
  interaction,
  answerValue,
  onAnswerChange,
  onRespond,
}) {
  const lang = useLang();
  const [remember, setRemember] = React.useState(false);

  React.useEffect(() => {
    setRemember(false);
  }, [interaction?.interaction_id]);

  if (!interaction) return null;

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
        <label className="permission-remember">
          <input
            type="checkbox"
            checked={remember}
            onChange={(event) => setRemember(event.target.checked)}
          />
          {t("modal.remember", lang)}
        </label>
        <div className="permission-actions">
          <button
            className="ghost btn-deny"
            onClick={() => onRespond && onRespond({ response_kind: "deny", decision: false, remember: false })}
          >
            {t("modal.deny", lang)}
          </button>
          <button
            className="primary"
            onClick={() => onRespond && onRespond({ response_kind: "approve", decision: true, remember })}
          >
            {t("modal.approve", lang)}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="prompt-panel" role="dialog" aria-label={t("inspector.inputRequired", lang)}>
      <h3>{t("inspector.inputRequired", lang)}</h3>
      <p>{interaction.question || ""}</p>
      <div className="option-list">
        {(interaction.options || []).map((option) => (
          <button
            key={option.index}
            className="option-card"
            onClick={() =>
              onRespond &&
              onRespond({
                response_kind: "answer",
                answer: option.text || "",
                selected_index: option.index || null,
                selected_mode: option.mode || "",
                selected_option_text: option.text || "",
              })
            }
          >
            <span>{option.text}</span>
            {option.mode ? <small>mode: {option.mode}</small> : null}
          </button>
        ))}
      </div>
      <textarea
        value={answerValue || ""}
        onChange={(event) => onAnswerChange && onAnswerChange(event.target.value)}
        placeholder={t("inspector.customAnswer", lang)}
        aria-label={t("inspector.customAnswer", lang)}
      />
      <button
        className="primary wide"
        onClick={() => onRespond && onRespond({ response_kind: "answer", answer: answerValue || "" })}
        disabled={!String(answerValue || "").trim()}
      >
        {t("inspector.submit", lang)}
      </button>
    </div>
  );
}
