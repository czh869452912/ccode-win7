import React from "react";
import { useLang } from "../LangContext.js";
import { t } from "../strings.js";
import DiffView from "./DiffView.jsx";

export default function Inspector({
  inspectorTab,
  todos,
  artifacts,
  plan,
  review,
  permissionContext,
  preview,
  userInput,
  userAnswer,
  eventLog,
  onTabChange,
  onOpenArtifact,
  onUserAnswerChange,
  onSubmitUserInput,
}) {
  const lang = useLang();

  return (
    <aside className="inspector" role="complementary" aria-label="Inspector">
      <div className="inspector-tabs" role="tablist">
        {[
          ["todos", t("inspector.todos", lang)],
          ["artifacts", t("inspector.artifacts", lang)],
          ["plan", t("inspector.plan", lang)],
          ["review", t("inspector.review", lang)],
          ["permissions", t("inspector.permissions", lang)],
          ["preview", t("inspector.preview", lang)],
          ["log", t("inspector.log", lang)],
        ].map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={inspectorTab === id}
            className={inspectorTab === id ? "active" : ""}
            onClick={() => onTabChange(id)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="inspector-body">
        {inspectorTab === "todos" && <TodoPanel todos={todos} lang={lang} />}
        {inspectorTab === "artifacts" && (
          <ArtifactPanel artifacts={artifacts} onOpen={onOpenArtifact} lang={lang} />
        )}
        {inspectorTab === "plan" && <PlanPanel plan={plan} lang={lang} />}
        {inspectorTab === "review" && <ReviewPanel review={review} lang={lang} />}
        {inspectorTab === "permissions" && (
          <PermissionsPanel permissionContext={permissionContext} lang={lang} />
        )}
        {inspectorTab === "preview" && <PreviewPanel preview={preview} lang={lang} />}
        {inspectorTab === "log" && <LogPanel entries={eventLog} lang={lang} />}
        {userInput ? (
          <div className="prompt-panel" role="dialog" aria-label={t("inspector.inputRequired", lang)}>
            <h3>{t("inspector.inputRequired", lang)}</h3>
            <p>{userInput.question}</p>
            <div className="option-list">
              {(userInput.options || []).map((option) => (
                <button
                  key={option.index}
                  className="option-card"
                  onClick={() => onSubmitUserInput(option)}
                >
                  <span>{option.text}</span>
                  {option.mode ? <small>mode: {option.mode}</small> : null}
                </button>
              ))}
            </div>
            <textarea
              value={userAnswer}
              onChange={(e) => onUserAnswerChange(e.target.value)}
              placeholder={t("inspector.customAnswer", lang)}
              aria-label={t("inspector.customAnswer", lang)}
            />
            <button className="primary wide" onClick={() => onSubmitUserInput(null)}>
              {t("inspector.submit", lang)}
            </button>
          </div>
        ) : null}
      </div>
    </aside>
  );
}

function PlanPanel({ plan, lang }) {
  if (!plan) {
    return <div className="empty-copy">{t("inspector.noPlan", lang)}</div>;
  }
  return (
    <div className="panel-preview">
      <h3>{plan.title || t("inspector.plan", lang)}</h3>
      <pre>{plan.content}</pre>
    </div>
  );
}

function PermissionsPanel({ permissionContext, lang }) {
  if (!permissionContext) {
    return <div className="empty-copy">{t("inspector.noPermissions", lang)}</div>;
  }
  const remembered = Array.isArray(permissionContext.remembered_categories)
    ? permissionContext.remembered_categories
    : [];
  const rules = Array.isArray(permissionContext.rules) ? permissionContext.rules : [];
  return (
    <div className="panel-preview">
      <h3>{t("inspector.permissions", lang)}</h3>
      <div className="permission-context-summary">
        <div><strong>{t("inspector.rulesPath", lang)}:</strong> {permissionContext.rules_path || "-"}</div>
        <div><strong>{t("inspector.remembered", lang)}:</strong> {remembered.length || 0}</div>
        <div><strong>{t("inspector.ruleCount", lang)}:</strong> {rules.length}</div>
      </div>
      {remembered.length > 0 ? (
        <>
          <h3>{t("inspector.rememberedCategories", lang)}</h3>
          <div className="permission-chip-list">
            {remembered.map((item) => (
              <span key={item} className="permission-chip">{item}</span>
            ))}
          </div>
        </>
      ) : null}
      <h3>{t("inspector.permissionRules", lang)}</h3>
      {rules.length > 0 ? (
        <div className="permission-rule-list">
          {rules.map((rule, index) => (
            <details key={`${index}-${rule.category}-${rule.decision}`} className="permission-rule-card">
              <summary className="permission-rule-summary">
                <span className={`permission-rule-decision decision-${rule.decision}`}>{rule.decision}</span>
                <span>{rule.category || "all"}</span>
                <span className="permission-rule-reason">{rule.reason || "-"}</span>
              </summary>
              <pre>{JSON.stringify(rule, null, 2)}</pre>
            </details>
          ))}
        </div>
      ) : (
        <div className="empty-copy">{t("inspector.noPermissionRules", lang)}</div>
      )}
    </div>
  );
}

function ReviewPanel({ review, lang }) {
  if (!review) {
    return <div className="empty-copy">{t("inspector.noReview", lang)}</div>;
  }
  const findings = Array.isArray(review.findings) ? review.findings : [];
  const residualRisks = Array.isArray(review.residual_risks) ? review.residual_risks : [];
  const sections = review.sections || {};
  return (
    <div className="panel-preview">
      <h3>{t("inspector.review", lang)}</h3>
      <p>{review.summary || ""}</p>
      {findings.length > 0 ? (
        <div className="review-findings">
          {findings.map((finding) => (
            <details key={finding.id || `${finding.title}-${finding.priority}`} className={`review-finding severity-${finding.severity || "info"}`}>
              <summary className="review-finding-header">
                <span className="review-finding-severity">{finding.severity || "info"}</span>
                <span className="review-finding-priority">P{finding.priority || "-"}</span>
                <span className="review-finding-title">{finding.title || "Finding"}</span>
              </summary>
              <div className="review-finding-body">{finding.body || ""}</div>
              {Array.isArray(finding.evidence) && finding.evidence.length > 0 ? (
                <pre>{JSON.stringify(finding.evidence, null, 2)}</pre>
              ) : null}
            </details>
          ))}
        </div>
      ) : (
        <div className="empty-copy">{t("inspector.noReviewFindings", lang)}</div>
      )}
      {residualRisks.length > 0 ? (
        <>
          <h3>{t("timeline.residualRisks", lang)}</h3>
          <ul className="review-risk-list">
            {residualRisks.map((risk, index) => (
              <li key={`${index}-${risk}`}>{risk}</li>
            ))}
          </ul>
        </>
      ) : null}
      <h3>{t("inspector.reviewEvidence", lang)}</h3>
      <ReviewSections sections={sections} lang={lang} />
    </div>
  );
}

function ReviewSections({ sections, lang }) {
  const groups = [
    ["diagnostics", t("inspector.reviewDiagnostics", lang)],
    ["tests", t("inspector.reviewTests", lang)],
    ["coverage", t("inspector.reviewCoverage", lang)],
    ["quality", t("inspector.reviewQuality", lang)],
    ["git", t("inspector.reviewGit", lang)],
  ];
  const hasAny = groups.some(([key]) => Array.isArray(sections[key]) && sections[key].length > 0);
  if (!hasAny) {
    return <div className="empty-copy">{t("inspector.noReviewEvidence", lang)}</div>;
  }
  return (
    <div className="review-section-list">
      {groups.map(([key, label]) => {
        const items = Array.isArray(sections[key]) ? sections[key] : [];
        if (items.length === 0) return null;
        return (
          <details key={key} className="review-section-card">
            <summary>{label} ({items.length})</summary>
            <pre>{JSON.stringify(items, null, 2)}</pre>
          </details>
        );
      })}
    </div>
  );
}

function TodoPanel({ todos, lang }) {
  return (
    <div className="panel-list">
      <h3>{t("todos.title", lang)}</h3>
      {(todos || []).length ? (
        todos.map((todo) => (
          <div key={todo.id} className="todo-row" role="listitem">
            <span className={todo.done ? "todo-mark done" : "todo-mark"}>
              {todo.done ? t("todos.done", lang) : t("todos.todo", lang)}
            </span>
            <span>{todo.content}</span>
          </div>
        ))
      ) : (
        <div className="empty-copy">{t("inspector.noTodos", lang)}</div>
      )}
    </div>
  );
}

function ArtifactPanel({ artifacts, onOpen, lang }) {
  return (
    <div className="panel-list">
      <h3>{t("artifacts.title", lang)}</h3>
      {(artifacts || []).length ? (
        artifacts.map((item) => (
          <button
            key={item.path}
            className="artifact-row"
            onClick={() => onOpen(item.path)}
            aria-label={item.path}
          >
            <span>{item.path}</span>
            <small>{item.tool_name || item.kind}</small>
          </button>
        ))
      ) : (
        <div className="empty-copy">{t("inspector.noArtifacts", lang)}</div>
      )}
    </div>
  );
}

function PreviewPanel({ preview, lang }) {
  if (!preview) {
    return <div className="empty-copy">{t("inspector.noPreview", lang)}</div>;
  }
  return (
    <div className="panel-preview">
      <h3>{preview.title}</h3>
      {preview.diff ? (
        <DiffView diff={preview.diff} title={t("timeline.diffChanges", lang)} />
      ) : (
        <pre>{preview.content}</pre>
      )}
    </div>
  );
}

function LogPanel({ entries, lang }) {
  if (!entries || entries.length === 0) {
    return <div className="empty-copy">{t("inspector.noLog", lang)}</div>;
  }
  return (
    <div className="log-list" role="log" aria-live="off" aria-label="Event log">
      {[...entries].reverse().map((e, i) => (
        <div key={i} className="log-entry">
          <span className="log-time">
            {new Date(e.ts).toLocaleTimeString(undefined, {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })}
          </span>
          <span className="log-label">{e.label}</span>
          {e.detail ? <span className="log-detail">{e.detail}</span> : null}
        </div>
      ))}
    </div>
  );
}
