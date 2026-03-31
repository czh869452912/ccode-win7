import React, { forwardRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toolLabel, STATUS_ICON } from "../store.js";
import { useLang } from "../LangContext.js";
import { t } from "../strings.js";
import DiffView from "./DiffView.jsx";

// Split flat timeline into turn groups.
// A new group starts at every "user" item.
function groupByTurn(items) {
  const groups = [];
  let current = null;
  for (const item of items) {
    if (item.kind === "user") {
      current = { userItem: item, activityItems: [], assistantItem: null, systemItems: [] };
      groups.push(current);
    } else if (!current) {
      // Items before any user message — create an anonymous group.
      current = { userItem: null, activityItems: [], assistantItem: null, systemItems: [] };
      groups.push(current);
      current.activityItems.push(item);
    } else if (item.kind === "assistant") {
      // The final assistant bubble for this turn.
      current.assistantItem = item;
    } else if (item.kind === "system") {
      current.systemItems.push(item);
    } else {
      // reasoning, tool → activity section
      current.activityItems.push(item);
    }
  }
  return groups;
}

const Timeline = forwardRef(function Timeline(
  {
    timeline, thinkingActive, streamingReasoningId,
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

function TurnGroup({ group, isLast, thinkingActive, streamingReasoningId, userAnswer, onUserAnswerChange, onSubmitUserInput, onPermissionResponse, lang }) {
  const { userItem, activityItems, assistantItem, systemItems } = group;
  const tools = activityItems.filter((i) => i.kind === "tool");
  const hasRunningTool = tools.some((i) => i.status === "running");
  const hasErrorTool = tools.some((i) => i.status === "error");
  const hasActivity = activityItems.length > 0;

  // Summary line for the collapsible activity section.
  const activitySummary = (() => {
    if (hasRunningTool) return `⋯ 正在执行…`;
    const toolCount = tools.length;
    if (toolCount === 0) return null;
    const icon = hasErrorTool ? "✗" : "✓";
    return `${icon} ${toolCount} 次工具调用`;
  })();

  // The activity section is open when this is the last (active) turn.
  const activityOpen = isLast;

  return (
    <div className="turn-group">
      {userItem && (
        <div className="bubble user" role="article">
          {userItem.content}
        </div>
      )}
      {hasActivity && (
        <details className="turn-activity" open={activityOpen}>
          <summary className="turn-activity-summary">
            {activitySummary || `${activityItems.length} 次活动`}
          </summary>
          <div className="turn-activity-body">
            {activityItems.map((item) =>
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
              <TimelineItem key={item.id} item={item} lang={lang} />
            )
          )}
          </div>
        </details>
      )}
      {assistantItem && (
        <div
          className={`bubble assistant ${assistantItem.streaming ? "streaming" : ""}`}
          role="article"
          aria-busy={assistantItem.streaming || undefined}
        >
          <Markdown content={assistantItem.content} />
        </div>
      )}
      {systemItems.map((item) => (
        <div key={item.id} className={`system-card ${item.tone || ""}`} role="alert">
          {item.content}
        </div>
      ))}
      {isLast && thinkingActive && !streamingReasoningId && (
        <div className="thinking-placeholder" aria-live="polite">
          {t("timeline.thinking", lang)}
        </div>
      )}
    </div>
  );
}

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
  if (item.kind === "command_result") {
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
    const status = item.status || "running";
    const label = item.label || toolLabel(item.toolName, item.arguments);
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
