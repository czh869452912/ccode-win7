import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

import { rowUiKey as defaultRowUiKey } from "../../session-runtime/timeline-ui-state.js";
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

function TurnFoldRow({ row, rowUiState, onToggleRow, rowKeyFor }) {
  const entries = Array.isArray(row.entries) ? row.entries : [];
  const key = rowKeyFor(row);
  const open = Boolean(rowUiState?.expanded?.[key]);
  return (
    <section
      className="t3-turn-fold-row"
      data-testid="timeline-turn-fold"
      data-row-kind="turn_fold"
      data-row-key={key}
    >
      <button
        type="button"
        className="t3-turn-fold-summary"
        aria-expanded={open}
        onClick={() => onToggleRow && onToggleRow(key)}
      >
        <span>{row.label || "Worked for this turn"}</span>
        <span>{row.workCount || entries.length} steps</span>
      </button>
      {open ? (
        <div className="t3-turn-fold-body">
          {entries.map((entry) => (
            <TimelineRowSwitch
              key={entry.id}
              row={entry}
              rowUiState={rowUiState}
              onToggleRow={onToggleRow}
              rowKeyFor={rowKeyFor}
            />
          ))}
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

function ExpandableShell({ row, rowKeyFor, rowUiState, onToggleRow, className, label, meta, children, ...domProps }) {
  const key = rowKeyFor(row);
  const open = Boolean(rowUiState?.expanded?.[key]);
  return (
    <section {...domProps} className={className} data-row-kind={row.kind} data-row-key={key}>
      <button
        type="button"
        className="t3-rich-row-summary"
        aria-expanded={open}
        onClick={() => onToggleRow && onToggleRow(key)}
      >
        <span className="t3-rich-row-label">{label}</span>
        {meta ? <span className="t3-rich-row-meta">{meta}</span> : null}
      </button>
      {open ? <div className="t3-rich-row-body">{children}</div> : null}
    </section>
  );
}

function ReasoningRow({ row, rowUiState, onToggleRow, rowKeyFor }) {
  const meta = row.streaming ? "streaming" : `${row.wordCount || 0} words`;
  return (
    <ExpandableShell
      row={row}
      rowUiState={rowUiState}
      onToggleRow={onToggleRow}
      rowKeyFor={rowKeyFor}
      className={`t3-reasoning-row${row.streaming ? " streaming" : ""}`}
      data-testid="timeline-reasoning-row"
      label={row.label || "Thinking"}
      meta={meta}
    >
      <pre>{row.content || ""}</pre>
    </ExpandableShell>
  );
}

function ThinkingRow({ row }) {
  return (
    <div className="t3-thinking-row" data-testid="timeline-thinking-row" data-row-kind="thinking" aria-live="polite">
      <span className="t3-thinking-pulse" aria-hidden="true" />
      <span>{row.label || "Thinking"}</span>
    </div>
  );
}

function CompactRow({ row }) {
  const parts = [];
  if (row.summarizedTurns !== undefined) parts.push(`${row.summarizedTurns} summarized`);
  if (row.recentTurns !== undefined) parts.push(`${row.recentTurns} retained`);
  if (row.approxTokensAfter !== undefined) parts.push(`~${Number(row.approxTokensAfter).toLocaleString()} tokens`);
  return (
    <div className="t3-compact-row system-card context" data-testid="timeline-compact-row" data-row-kind="compact" role="status">
      <span>{row.content || "Context compacted"}</span>
      {parts.length > 0 ? <span className="t3-rich-row-meta">{parts.join(" / ")}</span> : null}
    </div>
  );
}

function CommandResultRow({ row, markdownComponents, rowUiState, onToggleRow, rowKeyFor }) {
  return (
    <ExpandableShell
      row={row}
      rowUiState={rowUiState}
      onToggleRow={onToggleRow}
      rowKeyFor={rowKeyFor}
      className={`t3-command-result-row ${row.success === false ? "error" : "success"}`}
      data-testid="timeline-command-result-row"
      label={row.label || `/${row.commandName || "command"}`}
      meta={row.success === false ? "failed" : "completed"}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        className="markdown-body"
        components={markdownComponents}
      >
        {row.content || ""}
      </ReactMarkdown>
    </ExpandableShell>
  );
}

function ReviewResultRow({ row, markdownComponents, rowUiState, onToggleRow, rowKeyFor }) {
  const findingCount = Array.isArray(row.findings) ? row.findings.length : 0;
  return (
    <ExpandableShell
      row={row}
      rowUiState={rowUiState}
      onToggleRow={onToggleRow}
      rowKeyFor={rowKeyFor}
      className={`t3-review-result-row ${row.success === false ? "error" : "success"}`}
      data-testid="timeline-review-result-row"
      label="/review"
      meta={findingCount === 1 ? "1 finding" : `${findingCount} findings`}
    >
      {row.content ? (
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[rehypeKatex]}
          className="markdown-body"
          components={markdownComponents}
        >
          {row.content}
        </ReactMarkdown>
      ) : null}
      {findingCount > 0 ? (
        <div className="t3-review-findings">
          {row.findings.map((finding) => (
            <article key={finding.id} className="t3-review-finding">
              <div className="t3-review-finding-title">{finding.title}</div>
              <div className="t3-review-finding-meta">
                {[finding.severity, finding.file, finding.line ? `:${finding.line}` : ""].filter(Boolean).join(" ")}
              </div>
              {finding.body ? <p>{finding.body}</p> : null}
            </article>
          ))}
        </div>
      ) : null}
      {Array.isArray(row.residualRisks) && row.residualRisks.length > 0 ? (
        <ul className="t3-review-risks">
          {row.residualRisks.map((risk) => <li key={risk}>{risk}</li>)}
        </ul>
      ) : null}
    </ExpandableShell>
  );
}

function SystemNoticeRow({ row }) {
  return (
    <div className={`system-card ${row.tone || "context"}`} role={row.tone === "error" ? "alert" : "status"} data-row-kind="system_notice">
      {row.content || row.label || ""}
    </div>
  );
}

function TimelineRowSwitch({
  row,
  onOpenDiff,
  markdownComponents,
  rowUiState,
  onToggleRow,
  rowKeyFor,
}) {
  if (row.kind === "message") {
    return <MessageRow row={row} markdownComponents={markdownComponents} />;
  }
  if (row.kind === "work") {
    const key = rowKeyFor(row);
    return (
      <WorkRow
        row={row}
        rowKey={key}
        expanded={Boolean(rowUiState?.expanded?.[key])}
        onToggle={onToggleRow}
      />
    );
  }
  if (row.kind === "turn_fold") {
    return (
      <TurnFoldRow
        row={row}
        rowUiState={rowUiState}
        onToggleRow={onToggleRow}
        rowKeyFor={rowKeyFor}
      />
    );
  }
  if (row.kind === "interaction") return <InteractionRow row={row} />;
  if (row.kind === "diff_summary") return <ChangedFilesCard row={row} onOpenDiff={onOpenDiff} />;
  if (row.kind === "reasoning") {
    return <ReasoningRow row={row} rowUiState={rowUiState} onToggleRow={onToggleRow} rowKeyFor={rowKeyFor} />;
  }
  if (row.kind === "thinking") return <ThinkingRow row={row} />;
  if (row.kind === "compact") return <CompactRow row={row} />;
  if (row.kind === "command_result") {
    return (
      <CommandResultRow
        row={row}
        markdownComponents={markdownComponents}
        rowUiState={rowUiState}
        onToggleRow={onToggleRow}
        rowKeyFor={rowKeyFor}
      />
    );
  }
  if (row.kind === "review_result") {
    return (
      <ReviewResultRow
        row={row}
        markdownComponents={markdownComponents}
        rowUiState={rowUiState}
        onToggleRow={onToggleRow}
        rowKeyFor={rowKeyFor}
      />
    );
  }
  if (row.kind === "working") {
    return (
      <div className="t3-working-row" data-testid="timeline-working-row" data-row-kind="working">
        {row.label || "Working"}
      </div>
    );
  }
  return <SystemNoticeRow row={row} />;
}

export default function TimelineRows({
  rows,
  onOpenDiff,
  markdownComponents,
  rowUiState = null,
  onToggleRow = null,
  rowKeyFor = defaultRowUiKey,
}) {
  return (
    <>
      {(rows || []).map((row) => (
        <TimelineRowSwitch
          key={row.id}
          row={row}
          onOpenDiff={onOpenDiff}
          markdownComponents={markdownComponents}
          rowUiState={rowUiState}
          onToggleRow={onToggleRow}
          rowKeyFor={rowKeyFor}
        />
      ))}
    </>
  );
}
