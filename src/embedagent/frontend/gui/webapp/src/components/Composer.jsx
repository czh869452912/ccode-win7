import React from "react";
import { useLang } from "../LangContext.js";
import { t } from "../strings.js";

export default function Composer({ value, onChange, onSend, onStop, isRunning }) {
  const lang = useLang();

  return (
    <footer className="composer">
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
