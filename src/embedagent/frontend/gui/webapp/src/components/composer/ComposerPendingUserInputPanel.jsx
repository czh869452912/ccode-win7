import { useEffect, useState } from "react";

import { buildUserInputResponse } from "../../session-runtime/interaction-model.js";

export default function ComposerPendingUserInputPanel({ prompt, busy = false, onRespond }) {
  const [answer, setAnswer] = useState("");
  useEffect(() => {
    setAnswer("");
  }, [prompt?.interactionId]);
  if (!prompt) return null;
  const submit = (payload) => {
    if (busy || !onRespond) return;
    onRespond(payload);
  };
  return (
    <div className="composer-interaction-user-input">
      <div className="composer-interaction-heading">
        <span className="composer-interaction-kicker">{prompt.kicker}</span>
        <span className="composer-interaction-summary">{prompt.question || prompt.summary}</span>
      </div>
      {(prompt.options || []).length > 0 ? (
        <div className="composer-option-list">
          {(prompt.options || []).map((option) => (
            <button
              key={`${option.index || ""}:${option.label || option.text}`}
              type="button"
              className="composer-option"
              disabled={busy}
              onClick={() => submit(buildUserInputResponse(prompt, { option }))}
              data-testid={`user-input-option-${option.index}`}
            >
              {option.shortcut ? <kbd>{option.shortcut}</kbd> : null}
              <span>
                <strong>{option.label || option.text}</strong>
                {option.description ? <small>{option.description}</small> : null}
              </span>
              {option.mode ? <em>{prompt.modeLabelPrefix} {option.mode}</em> : null}
            </button>
          ))}
        </div>
      ) : null}
      <div className="composer-custom-answer">
        <textarea
          value={answer}
          onChange={(event) => setAnswer(event.target.value)}
          placeholder={prompt.customPlaceholder}
          aria-label={prompt.customPlaceholder}
          disabled={busy}
          rows={2}
          data-testid="user-input-custom-answer"
        />
        <button
          type="button"
          className="primary"
          disabled={busy || !answer.trim()}
          onClick={() => submit(buildUserInputResponse(prompt, { answer }))}
          data-testid="user-input-submit-button"
        >
          {prompt.submitLabel}
        </button>
      </div>
    </div>
  );
}
