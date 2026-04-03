import React from "react";
import { useLang } from "../LangContext.js";
import { t } from "../strings.js";

export default function Composer({
  value,
  onChange,
  onSend,
  onStop,
  isRunning,
  currentMode,
  commandHints = [],
}) {
  const lang = useLang();
  const showHints = !isRunning && value.trim().startsWith("/");
  const hints = showHints
    ? commandHints
        .filter((item) =>
          item.startsWith(value.trim().slice(1) ? `/${value.trim().slice(1)}` : "/")
        )
        .slice(0, 6)
    : [];

  return (
    <footer className="composer">
      <div className="composer-inner" style={{ position: "relative" }}>
        {currentMode && (
          <span className={`composer-mode-badge mode-${currentMode}`}>
            {currentMode}
          </span>
        )}
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
          rows={1}
          data-testid="composer-input"
        />
        {hints.length > 0 && (
          <div className="composer-hints" role="listbox" aria-label="Slash command suggestions">
            {hints.map((item) => (
              <button
                key={item}
                className="composer-hint"
                onClick={() => onChange(`${item} `)}
              >
                {item}
              </button>
            ))}
          </div>
        )}
        {isRunning ? (
          <button className="stop" onClick={onStop} aria-label={t("composer.stop", lang)} data-testid="stop-button">
            {t("composer.stop", lang)}
          </button>
        ) : (
          <button
            className="send"
            onClick={onSend}
            disabled={!value.trim()}
            aria-label={t("composer.send", lang)}
            data-testid="send-button"
          >
            ↵
          </button>
        )}
      </div>
      <div className="composer-hint-bar" aria-hidden="true">
        <span className="hint-text">/ 命令</span>
        <span className="hint-text">↑↓ 历史</span>
        <span className="hint-text">Shift+Enter 换行</span>
        {isRunning && (
          <span className="hint-text running-hint">● running 时禁用</span>
        )}
      </div>
    </footer>
  );
}
