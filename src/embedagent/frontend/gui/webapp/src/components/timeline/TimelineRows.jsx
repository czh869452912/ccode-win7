import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

import { rowUiKey as defaultRowUiKey } from "../../session-runtime/timeline-ui-state.js";
import ChangedFilesCard from "./ChangedFilesCard.jsx";
import WorkRow from "./WorkRow.jsx";

const MAX_VISIBLE_WORK_LOG_ENTRIES = 1;

function findNearestVerticalScroller(element) {
  let parent = element?.parentElement || null;
  while (parent) {
    const { overflowY } = window.getComputedStyle(parent);
    if (
      (overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay") &&
      parent.scrollHeight > parent.clientHeight
    ) {
      return parent;
    }
    parent = parent.parentElement;
  }
  return null;
}

function splitRowsIntoSections(rows = []) {
  const sections = [];
  for (const row of rows || []) {
    const previous = sections[sections.length - 1];
    if (row?.kind === "work") {
      if (previous?.kind === "work_group") {
        previous.rows.push(row);
      } else {
        sections.push({ kind: "work_group", id: `work-group-${row.id}`, rows: [row] });
      }
      continue;
    }
    sections.push({ kind: "row", id: row?.id || `row-${sections.length}`, row });
  }
  return sections;
}

function workGroupLabel(rows) {
  const count = rows.length;
  if (count === 1) return "1 tool call";
  return `${count} tool calls`;
}

function WorkGroupSection({ rows, rowUiState, onToggleRow, rowKeyFor }) {
  const sectionRef = React.useRef(null);
  const anchorBottomBeforeToggleRef = React.useRef(null);
  const [isExpanded, setIsExpanded] = React.useState(false);
  const hasOverflow = rows.length > MAX_VISIBLE_WORK_LOG_ENTRIES;
  const visibleRows =
    hasOverflow && !isExpanded
      ? rows.slice(-MAX_VISIBLE_WORK_LOG_ENTRIES)
      : rows;
  const hiddenCount = rows.length - visibleRows.length;

  React.useLayoutEffect(() => {
    const before = anchorBottomBeforeToggleRef.current;
    anchorBottomBeforeToggleRef.current = null;
    if (before == null) return;
    const section = sectionRef.current;
    if (!section) return;
    const delta = section.getBoundingClientRect().bottom - before;
    if (Math.abs(delta) < 0.5) return;
    const scroller = findNearestVerticalScroller(section);
    if (scroller) {
      scroller.scrollTop += delta;
    } else {
      window.scrollBy(0, delta);
    }
  }, [isExpanded]);

  function toggleExpanded() {
    anchorBottomBeforeToggleRef.current =
      sectionRef.current?.getBoundingClientRect().bottom ?? null;
    setIsExpanded((value) => !value);
  }

  if (!Array.isArray(rows) || rows.length === 0) return null;

  return (
    <section
      ref={sectionRef}
      className="timeline-work-group"
      data-testid="timeline-work-group"
      aria-label={workGroupLabel(rows)}
    >
      <div className="timeline-work-group-items">
        {visibleRows.map((row) => {
          const key = rowKeyFor(row);
          return (
            <WorkRow
              key={row.id}
              row={row}
              rowKey={key}
              expanded={Boolean(rowUiState?.expanded?.[key])}
              onToggle={onToggleRow}
            />
          );
        })}
      </div>
      {hasOverflow ? (
        <button
          type="button"
          className="timeline-work-overflow-toggle"
          data-testid="timeline-work-overflow-toggle"
          aria-expanded={isExpanded}
          onClick={toggleExpanded}
        >
          <span aria-hidden="true">{isExpanded ? "^" : "v"}</span>
          <span>
            {isExpanded
              ? "Show fewer tool calls"
              : `+${hiddenCount} previous tool ${hiddenCount === 1 ? "call" : "calls"}`}
          </span>
        </button>
      ) : null}
    </section>
  );
}

function formatWorkingTimer(startIso, endIso = new Date().toISOString()) {
  const start = Date.parse(startIso);
  const end = Date.parse(endIso);
  if (!Number.isFinite(start) || !Number.isFinite(end)) return "0s";
  const totalSeconds = Math.max(0, Math.floor((end - start) / 1000));
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes < 60) return `${minutes}m ${seconds}s`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}

function WorkingTimer({ createdAt }) {
  const textRef = React.useRef(null);
  const initialText = createdAt ? formatWorkingTimer(createdAt) : "0s";

  React.useEffect(() => {
    if (!createdAt) return undefined;
    function updateText() {
      if (textRef.current) {
        textRef.current.textContent = formatWorkingTimer(createdAt);
      }
    }
    updateText();
    const timerId = window.setInterval(updateText, 1000);
    return () => window.clearInterval(timerId);
  }, [createdAt]);

  return (
    <span ref={textRef} className="timeline-working-timer">
      {initialText}
    </span>
  );
}

function WorkingRow({ row }) {
  return (
    <div className="t3-working-row" data-testid="timeline-working-row" data-row-kind="working">
      <span className="timeline-working-dots" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <span>
        {row.createdAt ? (
          <>
            Working for <WorkingTimer createdAt={row.createdAt} />
          </>
        ) : (
          "Working..."
        )}
      </span>
    </div>
  );
}

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
    return <WorkingRow row={row} />;
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
  const sections = React.useMemo(() => splitRowsIntoSections(rows || []), [rows]);
  return (
    <>
      {sections.map((section) => {
        if (section.kind === "work_group") {
          return (
            <WorkGroupSection
              key={section.id}
              rows={section.rows}
              rowUiState={rowUiState}
              onToggleRow={onToggleRow}
              rowKeyFor={rowKeyFor}
            />
          );
        }
        return (
          <TimelineRowSwitch
            key={section.id}
            row={section.row}
            onOpenDiff={onOpenDiff}
            markdownComponents={markdownComponents}
            rowUiState={rowUiState}
            onToggleRow={onToggleRow}
            rowKeyFor={rowKeyFor}
          />
        );
      })}
    </>
  );
}
