import React, { forwardRef } from "react";

import {
  createTimelineUiState,
  restoreAnchorScroll,
  rowUiKey,
  shouldPinToBottom,
  toggleTimelineRow,
} from "../session-runtime/timeline-ui-state.js";
import TimelineRows from "./timeline/TimelineRows.jsx";

function parseTimelineFileHref(href) {
  const value = String(href || "").trim();
  if (!value || /^[a-z][a-z0-9+.-]*:/i.test(value) || value.startsWith("#")) return null;
  const [pathPart, hashPart = ""] = value.split("#", 2);
  const normalizedPath = pathPart.replace(/\\/g, "/").replace(/^\/+/, "");
  if (!normalizedPath) return null;
  const lineMatch = hashPart.match(/(?:^|[&?])L?(\d+)\b/i) || hashPart.match(/^L?(\d+)$/i);
  const line = lineMatch ? Number(lineMatch[1]) : undefined;
  return { path: normalizedPath, line: Number.isFinite(line) ? line : undefined };
}

function formatTemplate(template = "", values = {}) {
  return String(template || "").replace(/\{(\w+)\}/g, (_match, key) =>
    String(values[key] ?? ""),
  );
}

function terminationCardFor({
  terminationReason,
  terminationDisplayReason,
  terminationMessage,
  turnsUsed,
  maxTurns,
  chrome = {},
}) {
  if (terminationReason === "max_turns") {
    if (maxTurns == null) {
      return {
        tone: "context",
        content: chrome.explicitLoopLimitReached || "",
      };
    }
    return {
      tone: "context",
      content: formatTemplate(chrome.maxTurnLimitTemplate, { turnsUsed, maxTurns }),
    };
  }
  if (terminationReason === "guard") {
    return { tone: "error", content: chrome.guardStopped || "" };
  }
  if (terminationReason === "aborted") {
    return { tone: "context", content: chrome.cancelled || "" };
  }
  if (terminationReason && terminationReason !== "completed") {
    const label = terminationDisplayReason || terminationReason;
    return {
      tone: "context",
      content: terminationMessage ? `${label}: ${terminationMessage}` : label,
    };
  }
  return null;
}

const Timeline = forwardRef(function Timeline(
  {
    rows,
    historyIntegrity,
    terminationReason,
    terminationDisplayReason,
    terminationMessage,
    turnsUsed,
    maxTurns,
    onScroll,
    onOpenDiff,
    onOpenFile,
    chrome = {},
  },
  ref,
) {
  const timelineNodeRef = React.useRef(null);
  const pendingAnchorRef = React.useRef(null);
  const t3Rows = Array.isArray(rows) ? rows : [];
  const [timelineUiState, setTimelineUiState] = React.useState(() => createTimelineUiState(t3Rows));

  React.useEffect(() => {
    setTimelineUiState((previous) => createTimelineUiState(t3Rows, previous));
  }, [t3Rows]);

  React.useLayoutEffect(() => {
    const pending = pendingAnchorRef.current;
    const node = timelineNodeRef.current;
    if (!pending || !node) return;
    pendingAnchorRef.current = null;
    window.requestAnimationFrame(() => {
      const target = node.querySelector(`[data-row-key="${pending.rowKey}"]`);
      if (!target) return;
      const after = target.getBoundingClientRect();
      node.scrollTop = restoreAnchorScroll({
        before: pending.rect,
        after,
        scrollTop: pending.scrollTop,
      });
    });
  });

  function setTimelineNode(node) {
    timelineNodeRef.current = node;
    if (typeof ref === "function") ref(node);
    else if (ref) ref.current = node;
  }

  function handleToggleTimelineRow(rowKey) {
    const node = timelineNodeRef.current;
    if (node && !shouldPinToBottom(node)) {
      const target = node.querySelector(`[data-row-key="${rowKey}"]`);
      if (target) {
        pendingAnchorRef.current = {
          rowKey,
          rect: target.getBoundingClientRect(),
          scrollTop: node.scrollTop,
        };
      }
    }
    setTimelineUiState((previous) => toggleTimelineRow(previous, rowKey));
  }

  function handleTimelineFileLink(event, href) {
    const target = parseTimelineFileHref(href);
    if (!target || !onOpenFile) return false;
    event.preventDefault();
    onOpenFile(target.path, target.line);
    return true;
  }

  const markdownComponents = {
    a(props) {
      const target = parseTimelineFileHref(props.href);
      if (target) {
        return (
          <button
            type="button"
            className="timeline-file-link"
            data-testid={`timeline-file-link--${target.path}`}
            onClick={(event) => handleTimelineFileLink(event, props.href)}
          >
            {props.children}
          </button>
        );
      }
      return <a {...props} target="_blank" rel="noopener noreferrer" />;
    },
  };
  const terminationCard = terminationCardFor({
    terminationReason,
    terminationDisplayReason,
    terminationMessage,
    turnsUsed,
    maxTurns,
    chrome,
  });

  return (
    <div
      className="timeline t3-timeline"
      ref={setTimelineNode}
      onScroll={onScroll}
      role="log"
      aria-live="polite"
      aria-atomic="false"
      aria-label={chrome.ariaLabel || ""}
      data-testid="timeline-root"
    >
      <div className="timeline-shell">
        {historyIntegrity?.status === "partial" ? (
          <div className="system-card context" role="status">
            <strong>{chrome.historyPartialLabel || ""}</strong>: {historyIntegrity.restoreStopReason || historyIntegrity.restore_stop_reason || chrome.historyPartialFallback || ""}
          </div>
        ) : null}
        {historyIntegrity?.status === "unavailable" ? (
          <div className="system-card error" role="alert">
            {chrome.historyUnavailable || ""}
          </div>
        ) : null}
        {t3Rows.length > 0 ? (
          <TimelineRows
            rows={t3Rows}
            onOpenDiff={onOpenDiff}
            onOpenFile={onOpenFile}
            markdownComponents={markdownComponents}
            rowUiState={timelineUiState}
            onToggleRow={handleToggleTimelineRow}
            rowKeyFor={rowUiKey}
            chrome={chrome}
          />
        ) : (
          <div className="timeline-empty-state" role="status">{chrome.emptyState || ""}</div>
        )}
        {terminationCard ? (
          <div className={`system-card ${terminationCard.tone}`} role={terminationCard.tone === "error" ? "alert" : "status"}>
            {terminationCard.content}
          </div>
        ) : null}
      </div>
    </div>
  );
});

export default Timeline;
