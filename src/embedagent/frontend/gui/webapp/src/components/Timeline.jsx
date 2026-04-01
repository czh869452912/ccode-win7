import React, { forwardRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toolLabel, STATUS_ICON } from "../store.js";
import { useLang } from "../LangContext.js";
import { t } from "../strings.js";
import DiffView from "./DiffView.jsx";

function ToolBlock({ item }) {
  const status = item.status || "running"; // "running" | "success" | "error"
  const [userToggled, setUserToggled] = React.useState(false);
  const [expanded, setExpanded] = React.useState(item.status === "error");

  React.useEffect(() => {
    if (status === "error" && !userToggled) setExpanded(true);
  }, [status, userToggled]);

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
    if (status === "running") return "running...";
    if (status === "success") {
      const ms = item.executionTimeMs;
      const summary = item.resultSummary || "";
      return [summary, ms != null ? `${ms}ms` : ""].filter(Boolean).join(" · ").slice(0, 60) || "done";
    }
    // error
    const ms = item.executionTimeMs;
    return `error${ms != null ? ` · ${ms}ms` : ""}`;
  }, [status, item.executionTimeMs, item.resultSummary]);

  const MAX_OUTPUT = 4000;
  const rawOutput = item.error ||
    (item.data != null
      ? (typeof item.data === "string"
          ? item.data
          : JSON.stringify(item.data, null, 2))
      : null);
  const outputText = rawOutput && rawOutput.length > MAX_OUTPUT
    ? rawOutput.slice(0, MAX_OUTPUT) + "\n…[truncated]"
    : rawOutput;
  const hasOutput = Boolean(outputText);

  return (
    <div>
      <div
        className={`tool-block ${status}`}
        onClick={() => hasOutput && (setUserToggled(true), setExpanded((v) => !v))}
        title={item.toolName}
      >
        <span className={`tool-dot ${status}`} />
        <span className={`tool-name ${status}`}>{item.label || item.toolName}</span>
        {argsStr && <span className="tool-args">{argsStr}</span>}
        <span className="tool-meta">{metaStr}</span>
        {status === "error" && hasOutput && (
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
        activityItems: [],
        assistantItem: null,
      };
      turn._stepMap.set(key, step);
      turn.steps.push(step);
    }
    return turn._stepMap.get(key);
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
    if (item.kind === "system") {
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
    terminationReason, turnsUsed, maxTurns,
    userAnswer, onUserAnswerChange, onSubmitUserInput,
    onPermissionResponse,
    onScroll,
  },
  ref,
) {
  const lang = useLang();
  const groups = groupByTurn(timeline);
  const lastIdx = groups.length - 1;

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
      {groups.map((group, idx) => (
        <TurnGroup
          key={group.userItem?.id || `anon-${idx}`}
          group={group}
          toolCatalog={toolCatalog}
          isLast={idx === lastIdx}
          thinkingActive={thinkingActive}
          streamingReasoningId={streamingReasoningId}
          userAnswer={userAnswer}
          onUserAnswerChange={onUserAnswerChange}
          onSubmitUserInput={onSubmitUserInput}
          onPermissionResponse={onPermissionResponse}
          lang={lang}
        />
      ))}
      {terminationReason === "max_turns" && (
        <div className="system-card context" role="status">
          已达到 {maxTurns} 轮上限（已用 {turnsUsed} 轮）。如需继续，请继续输入。
        </div>
      )}
      {terminationReason === "guard" && (
        <div className="system-card error" role="alert">
          连续操作失败，Agent 已停止。请描述问题或调整方向后重新提交。
        </div>
      )}
    </div>
  );
});

export default Timeline;

function TurnGroup({ group, toolCatalog, isLast, thinkingActive, streamingReasoningId, userAnswer, onUserAnswerChange, onSubmitUserInput, onPermissionResponse, lang }) {
  const { userItem, steps, detachedItems, systemItems } = group;

  return (
    <div className="turn-group">
      {userItem && (
        <div className="bubble user" role="article">
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
          userAnswer={userAnswer}
          onUserAnswerChange={onUserAnswerChange}
          onSubmitUserInput={onSubmitUserInput}
          onPermissionResponse={onPermissionResponse}
          lang={lang}
        />
      ))}
      {systemItems.map((item) => (
        <div key={item.id} className={`system-card ${item.tone || ""}`} role="alert">
          {item.content}
        </div>
      ))}
      {isLast && thinkingActive && !streamingReasoningId && steps.length === 0 && (
        <div className="thinking-placeholder" aria-live="polite">
          {t("timeline.thinking", lang)}
        </div>
      )}
    </div>
  );
}

function StepGroup({ step, stepNumber, toolCatalog, isActive, thinkingActive, streamingReasoningId, userAnswer, onUserAnswerChange, onSubmitUserInput, onPermissionResponse, lang }) {
  const tools = step.activityItems.filter((item) => item.kind === "tool");
  const hasRunningTool = tools.some((item) => item.status === "running");
  const hasErrorTool = tools.some((item) => item.status === "error");
  const hasActivity = step.activityItems.length > 0;
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
        <span className="step-label">{t("timeline.stepLabel", lang, { n: stepNumber })}</span>
        {step.assistantItem?.streaming ? <span className="step-status">streaming</span> : null}
      </div>
      {hasActivity ? (
        <details className="turn-activity" open={isActive}>
          <summary className="turn-activity-summary">{activitySummary}</summary>
          <div className="turn-activity-body">
            {step.activityItems.map((item) =>
              item.kind === "mode_switch_proposal" ? (
                <ModeSwitchCard
                  key={item.id}
                  item={item}
                  onSubmitUserInput={onSubmitUserInput}
                  lang={lang}
                />
              ) : item.kind === "user_input" ? (
                <UserInputCard
                  key={item.id}
                  item={item}
                  userAnswer={userAnswer}
                  onUserAnswerChange={onUserAnswerChange}
                  onSubmitUserInput={onSubmitUserInput}
                  lang={lang}
                />
              ) : item.kind === "permission" ? (
                <PermissionCard
                  key={item.id}
                  item={item}
                  onPermissionResponse={onPermissionResponse}
                  lang={lang}
                />
              ) : (
                <TimelineItem key={item.id} item={item} toolCatalog={toolCatalog} lang={lang} />
              )
            )}
          </div>
        </details>
      ) : null}
      {step.assistantItem ? (
        <div
          className={`bubble assistant ${step.assistantItem.streaming ? "streaming" : ""}`}
          role="article"
          aria-busy={step.assistantItem.streaming || undefined}
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
  return (
    <div className={`system-card ${item.tone || ""}`} role="alert">
      {item.content}
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

function UserInputCard({ item, userAnswer, onUserAnswerChange, onSubmitUserInput, lang }) {
  const { request, answered, answerText } = item;
  if (answered) {
    return (
      <div className="user-input-card answered" role="article">
        <div className="user-input-question">{request?.question}</div>
        <div className="user-input-answer">✓ {answerText || t("inspector.submit", lang)}</div>
      </div>
    );
  }
  return (
    <div className="user-input-card" role="dialog" aria-label={t("inspector.inputRequired", lang)}>
      <div className="user-input-question">{request?.question}</div>
      <div className="option-list">
        {(request?.options || []).map((option) => (
          <button
            key={option.index}
            className="option-card"
            onClick={() => onSubmitUserInput && onSubmitUserInput(option)}
          >
            <span>{option.text}</span>
            {option.mode ? <small className="option-mode">→ {option.mode}</small> : null}
          </button>
        ))}
      </div>
      <textarea
        className="user-input-textarea"
        value={userAnswer || ""}
        onChange={(e) => onUserAnswerChange && onUserAnswerChange(e.target.value)}
        placeholder={t("inspector.customAnswer", lang)}
        aria-label={t("inspector.customAnswer", lang)}
      />
      <button
        className="primary wide"
        onClick={() => onSubmitUserInput && onSubmitUserInput(null, userAnswer)}
        disabled={!userAnswer?.trim()}
      >
        {t("inspector.submit", lang)}
      </button>
    </div>
  );
}

function PermissionCard({ item, onPermissionResponse, lang }) {
  const [remember, setRemember] = React.useState(false);
  const { permission, resolved, approved } = item;

  if (resolved) {
    return (
      <div className="permission-card resolved" role="article">
        <span className="permission-icon" aria-hidden="true">{approved ? "✓" : "✗"}</span>
        <span className="permission-action">{permission?.tool_name || "permission"}</span>
        <span className="permission-verdict">{approved ? "Approved" : "Denied"}</span>
      </div>
    );
  }

  return (
    <div className="permission-card" role="dialog" aria-label="Permission request">
      <div className="permission-header">
        <span className="permission-icon" aria-hidden="true">🔐</span>
        <span className="permission-tool">{permission?.tool_name || ""}</span>
        <span className="permission-category">{permission?.category || ""}</span>
      </div>
      <p className="permission-reason">{permission?.reason || ""}</p>
      {permission?.details && Object.keys(permission.details).length > 0 && (
        <details className="permission-details">
          <summary>Details</summary>
          <pre>{JSON.stringify(permission.details, null, 2)}</pre>
        </details>
      )}
      <label className="permission-remember">
        <input
          type="checkbox"
          checked={remember}
          onChange={(e) => setRemember(e.target.checked)}
        />
        Remember for this session
      </label>
      <div className="permission-actions">
        <button
          className="ghost btn-deny"
          onClick={() => onPermissionResponse && onPermissionResponse(item.id, false, false, permission?.category)}
        >
          Deny
        </button>
        <button
          className="primary"
          onClick={() => onPermissionResponse && onPermissionResponse(item.id, true, remember, permission?.category)}
        >
          Approve
        </button>
      </div>
    </div>
  );
}

function ModeSwitchCard({ item, onSubmitUserInput }) {
  const { request, answered, answerText } = item;
  const targetMode = request?.details?.target_mode || "";
  const reason = request?.question || "";

  if (answered) {
    return (
      <div className={`mode-switch-card resolved mode-${targetMode}`} role="article">
        <span className="mode-switch-icon">⇄</span>
        <span className="mode-switch-verdict">{answerText}</span>
      </div>
    );
  }
  return (
    <div className={`mode-switch-card mode-${targetMode}`} role="dialog" aria-label="Mode switch proposal">
      <div className="mode-switch-header">
        <span className="mode-switch-icon">⇄</span>
        <span className="mode-switch-target">→ {targetMode}</span>
      </div>
      {reason && <p className="mode-switch-reason">{reason}</p>}
      <div className="mode-switch-actions">
        <button
          className="ghost"
          onClick={() => onSubmitUserInput && onSubmitUserInput({ index: 2, text: "取消：保持当前模式", mode: "" })}
        >
          Cancel
        </button>
        <button
          className="primary"
          onClick={() => onSubmitUserInput && onSubmitUserInput({ index: 1, text: `确认：切换到 ${targetMode} 模式`, mode: targetMode })}
        >
          Switch to {targetMode}
        </button>
      </div>
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
