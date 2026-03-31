import React, { forwardRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toolLabel, STATUS_ICON } from "../store.js";
import { useLang } from "../LangContext.js";
import { t } from "../strings.js";
import DiffView from "./DiffView.jsx";

const Timeline = forwardRef(function Timeline(
  { timeline, thinkingActive, streamingReasoningId, onScroll },
  ref,
) {
  const lang = useLang();

  return (
    <div
      className="timeline"
      ref={ref}
      onScroll={onScroll}
      role="log"
      aria-live="polite"
      aria-atomic="false"
      aria-label="Conversation"
    >
      {timeline.map((item) => (
        <TimelineItem key={item.id} item={item} lang={lang} />
      ))}
      {thinkingActive && !streamingReasoningId ? (
        <div className="thinking-placeholder" aria-live="polite">
          {t("timeline.thinking", lang)}
        </div>
      ) : null}
    </div>
  );
});

export default Timeline;

function TimelineItem({ item, lang }) {
  if (item.kind === "user") {
    return <div className="bubble user" role="article">{item.content}</div>;
  }
  if (item.kind === "assistant") {
    return (
      <div
        className={`bubble assistant ${item.streaming ? "streaming" : ""}`}
        role="article"
        aria-busy={item.streaming || undefined}
      >
        <Markdown content={item.content} />
      </div>
    );
  }
  if (item.kind === "reasoning") {
    const wordCount = (item.content || "").split(/\s+/).filter(Boolean).length;
    return (
      <details className="reasoning-card" open={item.streaming}>
        <summary>
          <span className="reasoning-label">{t("timeline.thinkingLabel", lang)}</span>
          {item.streaming ? (
            <span className="reasoning-status streaming" aria-live="polite">…</span>
          ) : (
            <span className="reasoning-status done">
              {t("timeline.thinkingWords", lang, { n: wordCount })}
            </span>
          )}
        </summary>
        <div className="reasoning-body">{item.content}</div>
      </details>
    );
  }
  if (item.kind === "tool") {
    const status = item.status || "running";
    const label = toolLabel(item.toolName, item.arguments);
    const hasData = status !== "running" && item.data && Object.keys(item.data).length > 0;
    const hasArgs = item.arguments && Object.keys(item.arguments).length > 0;
    const hasDiff = typeof item.data?.diff === "string" && item.data.diff.length > 0;
    return (
      <div className={`tool-card ${status}`} role="article" aria-label={label}>
        <div className="tool-header">
          <span className={`tool-status-icon ${status}`} aria-hidden="true">
            {STATUS_ICON[status] || "⋯"}
          </span>
          <span className="tool-title">{label}</span>
          <span className="tool-name-badge" aria-label={`Tool: ${item.toolName}`}>
            {item.toolName}
          </span>
        </div>
        {item.error ? <div className="tool-error" role="alert">{item.error}</div> : null}
        {hasDiff ? (
          <DiffView diff={item.data.diff} title={t("timeline.diffChanges", lang)} />
        ) : null}
        {(hasArgs || (hasData && !hasDiff)) ? (
          <details className="tool-details">
            <summary>{t("timeline.toolDetails", lang)}</summary>
            {hasArgs ? <pre>{JSON.stringify(item.arguments, null, 2)}</pre> : null}
            {hasData && !hasDiff ? <pre>{JSON.stringify(item.data, null, 2)}</pre> : null}
          </details>
        ) : null}
      </div>
    );
  }
  return (
    <div className={`system-card ${item.tone || ""}`} role="alert">
      {item.content}
    </div>
  );
}

function Markdown({ content }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code(props) {
          const { inline, className, children, ...rest } = props;
          if (inline) {
            return (
              <code className={className} {...rest}>
                {children}
              </code>
            );
          }
          return (
            <pre className="code-block">
              <code className={className} {...rest}>
                {children}
              </code>
            </pre>
          );
        },
      }}
    >
      {content || ""}
    </ReactMarkdown>
  );
}
