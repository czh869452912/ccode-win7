import React, { forwardRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toolLabel, STATUS_ICON } from "../store.js";

const Timeline = forwardRef(function Timeline(
  { timeline, thinkingActive, streamingReasoningId, onScroll },
  ref,
) {
  return (
    <div className="timeline" ref={ref} onScroll={onScroll}>
      {timeline.map((item) => (
        <TimelineItem key={item.id} item={item} />
      ))}
      {thinkingActive && !streamingReasoningId ? (
        <div className="thinking-placeholder">Thinking…</div>
      ) : null}
    </div>
  );
});

export default Timeline;

function TimelineItem({ item }) {
  if (item.kind === "user") {
    return <div className="bubble user">{item.content}</div>;
  }
  if (item.kind === "assistant") {
    return (
      <div className={`bubble assistant ${item.streaming ? "streaming" : ""}`}>
        <Markdown content={item.content} />
      </div>
    );
  }
  if (item.kind === "reasoning") {
    const wordCount = (item.content || "").split(/\s+/).filter(Boolean).length;
    return (
      <details className="reasoning-card" open={item.streaming}>
        <summary>
          <span className="reasoning-label">Thinking</span>
          {item.streaming ? (
            <span className="reasoning-status streaming">…</span>
          ) : (
            <span className="reasoning-status done">{wordCount} words</span>
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
    return (
      <div className={`tool-card ${status}`}>
        <div className="tool-header">
          <span className={`tool-status-icon ${status}`}>{STATUS_ICON[status] || "⋯"}</span>
          <span className="tool-title">{label}</span>
          <span className="tool-name-badge">{item.toolName}</span>
        </div>
        {item.error ? <div className="tool-error">{item.error}</div> : null}
        {hasArgs || hasData ? (
          <details className="tool-details">
            <summary>Details</summary>
            {hasArgs ? <pre>{JSON.stringify(item.arguments, null, 2)}</pre> : null}
            {hasData ? <pre>{JSON.stringify(item.data, null, 2)}</pre> : null}
          </details>
        ) : null}
      </div>
    );
  }
  return <div className={`system-card ${item.tone || ""}`}>{item.content}</div>;
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
