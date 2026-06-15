import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

import ChangedFilesCard from "./ChangedFilesCard.jsx";
import WorkRow from "./WorkRow.jsx";

function MessageRow({ row, markdownComponents }) {
  if (row.role === "assistant") {
    return (
      <article
        className={`t3-message-row assistant${row.streaming ? " streaming" : ""}`}
        data-testid="timeline-assistant-message"
        data-row-kind="message"
        aria-busy={row.streaming || undefined}
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[rehypeKatex]}
          className="markdown-body"
          components={markdownComponents}
        >
          {row.content || ""}
        </ReactMarkdown>
        {row.streaming ? <span className="stream-cursor" aria-hidden="true" /> : null}
      </article>
    );
  }
  return (
    <article className="t3-message-row user" data-testid="timeline-user-message" data-row-kind="message">
      <div className="t3-user-bubble">{row.content || ""}</div>
    </article>
  );
}

function TurnFoldRow({ row }) {
  const entries = Array.isArray(row.entries) ? row.entries : [];
  const [open, setOpen] = React.useState(Boolean(row.defaultOpen));
  return (
    <section className="t3-turn-fold-row" data-testid="timeline-turn-fold" data-row-kind="turn_fold">
      <button
        type="button"
        className="t3-turn-fold-summary"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span>{row.label || "Worked for this turn"}</span>
        <span>{row.workCount || entries.length} steps</span>
      </button>
      {open ? (
        <div className="t3-turn-fold-body">
          {entries.map((entry) =>
            entry.kind === "interaction"
              ? <InteractionRow key={entry.id} row={entry} />
              : <WorkRow key={entry.id} row={entry} />,
          )}
        </div>
      ) : null}
    </section>
  );
}

function InteractionRow({ row }) {
  return (
    <div className={`t3-interaction-row ${row.status || "pending"}`} data-row-kind="interaction">
      <span className="t3-interaction-label">{row.label || row.interactionKind || "interaction"}</span>
      <span className="t3-interaction-status">{row.status || "pending"}</span>
      {row.detail ? <span className="t3-interaction-detail">{row.detail}</span> : null}
    </div>
  );
}

function SystemNoticeRow({ row }) {
  return (
    <div className={`system-card ${row.tone || "context"}`} role={row.tone === "error" ? "alert" : "status"} data-row-kind="system_notice">
      {row.content || row.label || ""}
    </div>
  );
}

export default function TimelineRows({ rows, onOpenDiff, markdownComponents }) {
  return (
    <>
      {(rows || []).map((row) => {
        if (row.kind === "message") {
          return <MessageRow key={row.id} row={row} markdownComponents={markdownComponents} />;
        }
        if (row.kind === "work") {
          return <WorkRow key={row.id} row={row} />;
        }
        if (row.kind === "turn_fold") {
          return <TurnFoldRow key={row.id} row={row} />;
        }
        if (row.kind === "interaction") {
          return <InteractionRow key={row.id} row={row} />;
        }
        if (row.kind === "diff_summary") {
          return <ChangedFilesCard key={row.id} row={row} onOpenDiff={onOpenDiff} />;
        }
        if (row.kind === "working") {
          return (
            <div key={row.id} className="t3-working-row" data-testid="timeline-working-row" data-row-kind="working">
              {row.label || "Working"}
            </div>
          );
        }
        return <SystemNoticeRow key={row.id} row={row} />;
      })}
    </>
  );
}
