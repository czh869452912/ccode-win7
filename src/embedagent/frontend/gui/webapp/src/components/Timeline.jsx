import React, { forwardRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import hljs from "highlight.js/lib/core";
import hljsC from "highlight.js/lib/languages/c";
import hljsCpp from "highlight.js/lib/languages/cpp";
import hljsBash from "highlight.js/lib/languages/bash";
import hljsJson from "highlight.js/lib/languages/json";
import hljsPython from "highlight.js/lib/languages/python";
import hljsMakefile from "highlight.js/lib/languages/makefile";
import hljsYaml from "highlight.js/lib/languages/yaml";
import { toolLabel, STATUS_ICON } from "../store.js";
import { useLang } from "../LangContext.js";
import { t } from "../strings.js";
import { describeProjectionBadge, describeTimelineProjectionNotice, summarizeTimelineProjection } from "../state-helpers.js";
import DiffView from "./DiffView.jsx";

hljs.registerLanguage("c", hljsC);
hljs.registerLanguage("cpp", hljsCpp);
hljs.registerLanguage("bash", hljsBash);
hljs.registerLanguage("sh", hljsBash);
hljs.registerLanguage("json", hljsJson);
hljs.registerLanguage("python", hljsPython);
hljs.registerLanguage("makefile", hljsMakefile);
hljs.registerLanguage("yaml", hljsYaml);

function ToolBlock({ item }) {
  const lang = useLang();
  const status = item.status || "running"; // "running" | "success" | "error"
  const errorKind = (item.data && item.data.error_kind) || "";
  const isInterrupted = errorKind === "interrupted";
  const isDiscarded = errorKind === "discarded";
  const isSynthetic = isInterrupted || isDiscarded;

  const [userToggled, setUserToggled] = React.useState(false);
  const [expanded, setExpanded] = React.useState(!isSynthetic && item.status === "error");

  React.useEffect(() => {
    if (!isSynthetic && status === "error" && !userToggled) setExpanded(true);
  }, [status, userToggled, isSynthetic]);

  // Build display args string from item.arguments
  const argsStr = React.useMemo(() => {
    const args = item.arguments || {};
    const skip = new Set(["_tool_label","_permission_category","_supports_diff_preview",
                          "_progress_renderer_key","_result_renderer_key"]);
    const vals = Object.entries(args)
      .filter(([k]) => !skip.has(k))
      .map(([, v]) => (typeof v === "string" ? v : JSON.stringify(v)));
    return vals.join("  ").slice(0, 80);
  }, [item.arguments]);

  const metaStr = React.useMemo(() => {
    if (isInterrupted) return t("timeline.toolInterrupted", lang);
    if (isDiscarded) return t("timeline.toolDiscarded", lang);
    if (status === "running") return "running...";
    if (status === "success") {
      const ms = item.executionTimeMs;
      const summary = item.resultSummary || "";
      return [summary, ms != null ? `${ms}ms` : ""].filter(Boolean).join(" · ").slice(0, 60) || "done";
    }
    // error
    const ms = item.executionTimeMs;
    return `error${ms != null ? ` · ${ms}ms` : ""}`;
  }, [status, item.executionTimeMs, item.resultSummary, isInterrupted, isDiscarded, lang]);

  const MAX_OUTPUT = 4000;
  const rawOutput = !isSynthetic
    ? (item.error ||
       (item.data != null
         ? (typeof item.data === "string"
             ? item.data
             : JSON.stringify(item.data, null, 2))
         : null))
    : null;
  const outputText = rawOutput && rawOutput.length > MAX_OUTPUT
    ? rawOutput.slice(0, MAX_OUTPUT) + "\n…[truncated]"
    : rawOutput;
  const hasOutput = Boolean(outputText);

  const effectiveStatus = isSynthetic ? (isInterrupted ? "interrupted" : "discarded") : status;

  return (
    <div data-testid="tool-block">
      <div
        className={`tool-block ${effectiveStatus}`}
        onClick={() => hasOutput && (setUserToggled(true), setExpanded((v) => !v))}
        title={item.toolName}
      >
        <span className={`tool-dot ${effectiveStatus}`} />
        <span className={`tool-name ${effectiveStatus}`}>{item.label || item.toolName}</span>
        {argsStr && <span className="tool-args">{argsStr}</span>}
        <span className="tool-meta">{metaStr}</span>
        {!isSynthetic && status === "error" && hasOutput && (
          <span className="tool-expand">{expanded ? "▾" : "▸"}</span>
        )}
      </div>
      {expanded && hasOutput && (
        <div className="tool-output">
          {outputText}
        </div>
      )}
    </div>
  );
}

function groupByTurn(items) {
  const groups = [];
  const turnMap = new Map();

  function getTurn(turnId, fallbackId) {
    const key = turnId || fallbackId;
    if (!turnMap.has(key)) {
      const turn = {
        turnId: key,
        userItem: null,
        steps: [],
        detachedItems: [],
        systemItems: [],
        _stepMap: new Map(),
      };
      turnMap.set(key, turn);
      groups.push(turn);
    }
    return turnMap.get(key);
  }

  function getStep(turn, item) {
    const key = item.stepId || `step-${turn.steps.length + 1}`;
    if (!turn._stepMap.has(key)) {
      const step = {
        stepId: key,
        stepIndex: item.stepIndex || turn.steps.length + 1,
        projectionSource: item.projectionSource || "",
        projectionKind: item.projectionKind || "",
        synthetic: Boolean(item.synthetic),
        activityItems: [],
        assistantItem: null,
      };
      turn._stepMap.set(key, step);
      turn.steps.push(step);
    }
    const step = turn._stepMap.get(key);
    if (item.projectionSource && !step.projectionSource) step.projectionSource = item.projectionSource;
    if (item.projectionKind && !step.projectionKind) step.projectionKind = item.projectionKind;
    if (item.synthetic) step.synthetic = true;
    return step;
  }

  for (const item of items) {
    const turn = getTurn(item.turnId || "", item.kind === "user" ? item.id : `detached-${item.id}`);
    if (item.kind === "user") {
      turn.userItem = item;
      continue;
    }
    if (item.stepId) {
      const step = getStep(turn, item);
      if (item.kind === "assistant") {
        step.assistantItem = item;
      } else {
        step.activityItems.push(item);
      }
      continue;
    }
    if (item.kind === "system" || item.kind === "compact") {
      turn.systemItems.push(item);
    } else {
      turn.detachedItems.push(item);
    }
  }

  return groups.map((turn) => ({
    turnId: turn.turnId,
    userItem: turn.userItem,
    steps: turn.steps.sort((a, b) => (a.stepIndex || 0) - (b.stepIndex || 0)),
    detachedItems: turn.detachedItems,
    systemItems: turn.systemItems,
  }));
}

const Timeline = forwardRef(function Timeline(
  {
    timeline, toolCatalog, thinkingActive, streamingReasoningId,
    terminationReason, terminationDisplayReason, terminationMessage,
    turnsUsed, maxTurns,
    onScroll,
  },
  ref,
) {
  const lang = useLang();
  const groups = groupByTurn(timeline);
  const projectionSummary = summarizeTimelineProjection(timeline);
  const projectionNotice = describeTimelineProjectionNotice(projectionSummary);
  const lastIdx = groups.length - 1;

  // Derive termination card props
  let terminationCard = null;
  if (terminationReason === "max_turns") {
    terminationCard = {
      tone: "context",
      content: t("timeline.maxTurnsReached", lang)
        .replace("{max}", maxTurns)
        .replace("{used}", turnsUsed),
    };
  } else if (terminationReason === "guard") {
    terminationCard = { tone: "error", content: t("timeline.guardStop", lang) };
  } else if (terminationReason === "aborted") {
    terminationCard = { tone: "context", content: t("timeline.cancelled", lang) };
  } else if (terminationReason && terminationReason !== "completed") {
    const label = terminationDisplayReason || terminationReason;
    terminationCard = {
      tone: "context",
      content: terminationMessage ? `${label}: ${terminationMessage}` : label,
    };
  }

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
      {projectionNotice ? (
        <div className={`system-card ${projectionNotice.tone || "context"}`} role="status">
          <strong>{projectionNotice.title}</strong>: {projectionNotice.detail}
        </div>
      ) : null}
      {groups.map((group, idx) => (
        <TurnGroup
          key={group.turnId || group.userItem?.id || `anon-${idx}`}
          group={group}
          toolCatalog={toolCatalog}
          isLast={idx === lastIdx}
          thinkingActive={thinkingActive}
          streamingReasoningId={streamingReasoningId}
          lang={lang}
        />
      ))}
      {terminationCard && (
        <div className={`system-card ${terminationCard.tone}`} role={terminationCard.tone === "error" ? "alert" : "status"}>
          {terminationCard.content}
        </div>
      )}
    </div>
  );
});

export default Timeline;

function TurnGroup({ group, toolCatalog, isLast, thinkingActive, streamingReasoningId, lang }) {
  const { userItem, steps, detachedItems, systemItems } = group;

  return (
    <div className="turn-group">
      {userItem && (
        <div className="bubble user" role="article" data-testid="timeline-user-message">
          {userItem.content}
        </div>
      )}
      {detachedItems.map((item) => (
        <TimelineItem key={item.id} item={item} toolCatalog={toolCatalog} lang={lang} />
      ))}
      {steps.map((step, index) => (
        <StepGroup
          key={step.stepId || `${group.turnId}-step-${index + 1}`}
          step={step}
          stepNumber={step.stepIndex || index + 1}
          toolCatalog={toolCatalog}
          isActive={isLast && index === steps.length - 1}
          thinkingActive={thinkingActive}
          streamingReasoningId={streamingReasoningId}
          lang={lang}
        />
      ))}
      {systemItems.map((item) => (
        item.kind === "compact"
          ? <CompactCard key={item.id} item={item} lang={lang} />
          : <div key={item.id} className={`system-card ${item.tone || ""}`} role="alert">{item.content}</div>
      ))}
      {isLast && thinkingActive && !streamingReasoningId && steps.length === 0 && (
        <div className="thinking-placeholder" aria-live="polite">
          {t("timeline.thinking", lang)}
        </div>
      )}
    </div>
  );
}

function StepGroup({ step, stepNumber, toolCatalog, isActive, thinkingActive, streamingReasoningId, lang }) {
  const tools = step.activityItems.filter((item) => item.kind === "tool");
  const hasRunningTool = tools.some((item) => item.status === "running");
  const hasErrorTool = tools.some((item) => item.status === "error");
  const hasActivity = step.activityItems.length > 0;
  const projectionBadge = describeProjectionBadge(step);
  const activitySummary = (() => {
    if (hasRunningTool) return `Step ${stepNumber} · running…`;
    const toolCount = tools.length;
    if (toolCount === 0) return `Step ${stepNumber}`;
    const icon = hasErrorTool ? "✗" : "✓";
    return `Step ${stepNumber} · ${icon} ${toolCount} tools`;
  })();

  return (
    <section className={`step-group${isActive ? " active" : ""}`} aria-label={`Agent step ${stepNumber}`}>
      <div className="step-header">
        <div className="step-header-left">
          <span className="step-label">{t("timeline.stepLabel", lang, { n: stepNumber })}</span>
          {projectionBadge ? (
            <span className="rule-chip monospace step-projection-chip" title={projectionBadge.detail || projectionBadge.label}>
              {projectionBadge.label}
            </span>
          ) : null}
        </div>
        <div className="step-header-right">
          {projectionBadge?.detail ? (
            <span className="step-status">{projectionBadge.detail}</span>
          ) : null}
          {step.assistantItem?.streaming ? <span className="step-status">streaming</span> : null}
        </div>
      </div>
      {hasActivity ? (
        <details className="turn-activity" open={isActive}>
          <summary className="turn-activity-summary">{activitySummary}</summary>
          <div className="turn-activity-body">
            {step.activityItems.map((item) => (
              <TimelineItem key={item.id} item={item} toolCatalog={toolCatalog} lang={lang} />
            ))}
          </div>
        </details>
      ) : null}
      {step.assistantItem ? (
        <div
          className={`bubble assistant ${step.assistantItem.streaming ? "streaming" : ""}`}
          role="article"
          aria-busy={step.assistantItem.streaming || undefined}
          data-testid="timeline-assistant-message"
        >
          <Markdown content={step.assistantItem.content} />
          {step.assistantItem.streaming && (
            <span className="stream-cursor" aria-hidden="true" />
          )}
        </div>
      ) : null}
      {isActive && thinkingActive && !streamingReasoningId && !step.assistantItem ? (
        <div className="thinking-placeholder" aria-live="polite">
          {t("timeline.thinking", lang)}
        </div>
      ) : null}
    </section>
  );
}

function TimelineItem({ item, toolCatalog, lang }) {
  if (item.kind === "user") {
    return <div className="bubble user" role="article" data-testid="timeline-user-message">{item.content}</div>;
  }
  if (item.kind === "assistant") {
    return (
      <div
        className={`bubble assistant ${item.streaming ? "streaming" : ""}`}
        role="article"
        aria-busy={item.streaming || undefined}
        data-testid="timeline-assistant-message"
      >
        <Markdown content={item.content} />
      </div>
    );
  }
  if (item.kind === "command_result") {
    if (item.commandName === "review" && item.data?.review) {
      return <ReviewResultCard item={item} lang={lang} />;
    }
    return (
      <div className={`bubble assistant command-result ${item.success === false ? "error" : ""}`} role="article">
        <div className="command-result-label">/{item.commandName}</div>
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
    return <ToolBlock item={item} />;
  }
  if (item.kind === "interaction_requested" || item.kind === "interaction_resolved") {
    return (
      <div className={`permission-card ${item.kind === "interaction_resolved" ? "resolved" : ""}`} role="article">
        <span className="permission-action">{item.label || item.interactionKind || "interaction"}</span>
        <span className="permission-verdict">
          {item.kind === "interaction_resolved" ? "Resolved" : "Pending in Inspector"}
        </span>
        {item.detail ? <span className="permission-reason">{item.detail}</span> : null}
      </div>
    );
  }
  if (item.kind === "compact") {
    return <CompactCard item={item} lang={lang} />;
  }
  return (
    <div className={`system-card ${item.tone || ""}`} role="alert">
      {item.content}
    </div>
  );
}

function CompactCard({ item, lang }) {
  const hasStats = item.recentTurns !== undefined || item.summarizedTurns !== undefined;
  const parts = [];
  if (item.summarizedTurns !== undefined) parts.push(`${t("timeline.compactSummarized", lang)} ${item.summarizedTurns}`);
  if (item.recentTurns !== undefined) parts.push(`${t("timeline.compactRetained", lang)} ${item.recentTurns}`);
  if (item.approxTokensAfter !== undefined) parts.push(`~${item.approxTokensAfter.toLocaleString()} tokens`);
  const summary = hasStats ? parts.join(" · ") : (item.content || t("timeline.compacted", lang));
  return (
    <div className="system-card compact-card context" role="status">
      <span className="compact-icon" aria-hidden="true">⊙</span>
      <span className="compact-summary">{t("timeline.compacted", lang)}: {summary}</span>
    </div>
  );
}

function ReviewResultCard({ item, lang }) {
  const review = item.data?.review || {};
  const findings = Array.isArray(review.findings) ? review.findings : [];
  const residualRisks = Array.isArray(review.residual_risks) ? review.residual_risks : [];
  return (
    <div className={`bubble assistant command-result review-result ${item.success === false ? "error" : ""}`} role="article">
      <div className="command-result-label">/{item.commandName}</div>
      <div className="review-summary">{review.summary || item.content}</div>
      {findings.length > 0 ? (
        <div className="review-findings">
          {findings.map((finding) => (
            <div key={finding.id || `${finding.title}-${finding.priority}`} className={`review-finding severity-${finding.severity || "info"}`}>
              <div className="review-finding-header">
                <span className="review-finding-severity">{finding.severity || "info"}</span>
                <span className="review-finding-priority">P{finding.priority || "-"}</span>
                <span className="review-finding-title">{finding.title || "Finding"}</span>
              </div>
              <div className="review-finding-body">{finding.body || ""}</div>
            </div>
          ))}
        </div>
      ) : (
        <Markdown content={item.content} />
      )}
      {residualRisks.length > 0 ? (
        <details className="tool-details">
          <summary>{t("timeline.residualRisks", lang)}</summary>
          <ul className="review-risk-list">
            {residualRisks.map((risk, index) => (
              <li key={`${index}-${risk}`}>{risk}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

function CodeBlock({ className, children }) {
  const [copied, setCopied] = React.useState(false);
  const lang = (className || "").replace("language-", "") || "";
  const codeText = String(children || "").replace(/\n$/, "");

  const highlighted = React.useMemo(() => {
    try {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(codeText, { language: lang }).value;
      }
      return hljs.highlightAuto(codeText).value;
    } catch {
      return null;
    }
  }, [codeText, lang]);

  function handleCopy() {
    navigator.clipboard?.writeText(codeText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div className="code-block-wrapper">
      <div className="code-block-header">
        {lang && <span className="code-lang">{lang}</span>}
        <button className="code-copy-btn" onClick={handleCopy} aria-label="Copy code">
          {copied ? "✓" : "Copy"}
        </button>
      </div>
      <pre className="code-block">
        {highlighted
          ? <code className={className} dangerouslySetInnerHTML={{ __html: highlighted }} />
          : <code className={className}>{codeText}</code>
        }
      </pre>
    </div>
  );
}

function Markdown({ content }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeKatex]}
      className="markdown-body"
      components={{
        code(props) {
          const { node, inline, className, children, ...rest } = props;
          if (inline) {
            return <code className={`inline-code ${className || ""}`} {...rest}>{children}</code>;
          }
          return <CodeBlock className={className}>{children}</CodeBlock>;
        },
        a(props) {
          return <a {...props} target="_blank" rel="noopener noreferrer" />;
        },
      }}
    >
      {content || ""}
    </ReactMarkdown>
  );
}
