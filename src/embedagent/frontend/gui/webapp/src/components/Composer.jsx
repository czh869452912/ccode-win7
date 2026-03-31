import React from "react";
import { useLang } from "../LangContext.js";
import { t } from "../strings.js";

export default function Composer({ value, onChange, onSend, onStop, isRunning, commandHints = [] }) {
  const lang = useLang();
  const showHints = !isRunning && value.trim().startsWith("/");
  const hints = showHints
    ? commandHints.filter((item) => item.startsWith(value.trim().slice(1) ? `/${value.trim().slice(1)}` : "/")).slice(0, 6)
    : [];

  return (
    <footer className="composer">
      <div className="composer-input">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (!isRunning) onSend();
            }
          }}
          placeholder={t("composer.placeholder", lang)}
          aria-label={t("composer.placeholder", lang)}
          disabled={isRunning}
        />
        {hints.length > 0 ? (
          <div className="composer-hints" role="listbox" aria-label="Slash command suggestions">
            {hints.map((item) => (
              <button key={item} className="composer-hint" onClick={() => onChange(`${item} `)}>
                {item}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      {isRunning ? (
        <button
          className="stop"
          onClick={onStop}
          aria-label={t("composer.stop", lang)}
        >
          {t("composer.stop", lang)}
        </button>
      ) : (
        <button
          className="primary send"
          onClick={onSend}
          aria-label={t("composer.send", lang)}
        >
          {t("composer.send", lang)}
        </button>
      )}
    </footer>
  );
}
