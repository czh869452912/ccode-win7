import React from "react";
import { useLang } from "../LangContext.js";
import { t } from "../strings.js";
import DiffView from "./DiffView.jsx";

const PRIMARY_TABS = ["todos", "plan", "artifacts"];
const OVERFLOW_TABS = ["run", "problems", "review", "permissions", "runtime", "preview", "log"];

function InspectorTabs({ active, onChange, todosCount, artifactsCount }) {
  const lang = useLang();
  const [overflowOpen, setOverflowOpen] = React.useState(false);
  const overflowRef = React.useRef(null);

  // Close overflow menu when clicking outside
  React.useEffect(() => {
    if (!overflowOpen) return;
    function onDoc(e) {
      if (overflowRef.current && !overflowRef.current.contains(e.target)) {
        setOverflowOpen(false);
      }
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [overflowOpen]);

  const badges = { todos: todosCount, artifacts: artifactsCount };

  return (
    <div className="inspector-tabs" role="tablist">
      {PRIMARY_TABS.map((id) => (
        <button
          key={id}
          role="tab"
          aria-selected={active === id}
          className={`insp-tab${active === id ? " active" : ""}`}
          onClick={() => onChange(id)}
        >
          {t(`inspector.${id}`, lang)}
          {badges[id] > 0 && <span className="tab-badge">{badges[id]}</span>}
        </button>
      ))}
      <div ref={overflowRef} style={{ marginLeft: "auto", position: "relative" }}>
        <button
          className="more-tab-btn"
          onClick={() => setOverflowOpen((v) => !v)}
          aria-label="More tabs"
        >
          {OVERFLOW_TABS.includes(active)
            ? t(`inspector.${active}`, lang) + " ···"
            : "···"}
        </button>
        {overflowOpen && (
          <div className="tab-overflow-menu" role="menu">
            {OVERFLOW_TABS.map((id) => (
              <button
                key={id}
                role="menuitem"
                className="overflow-menu-item"
                onClick={() => { onChange(id); setOverflowOpen(false); }}
              >
                {t(`inspector.${id}`, lang)}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function Inspector({
  inspectorTab,
  todos,
  artifacts,
  plan,
  review,
  recipes,
  timeline,
  permissionContext,
  preview,
  snapshot,
  userInput,
  userAnswer,
  eventLog,
  onTabChange,
  onOpenArtifact,
  onOpenReviewEvidence,
  onRunRecipe,
  onUserAnswerChange,
  onSubmitUserInput,
}) {
  const lang = useLang();

  return (
    <aside className="inspector" role="complementary" aria-label="Inspector">
      <InspectorTabs
        active={inspectorTab}
        onChange={onTabChange}
        todosCount={todos.length}
        artifactsCount={artifacts.length}
      />
      <div className="inspector-body">
        {inspectorTab === "todos" && <TodoPanel todos={todos} lang={lang} />}
        {inspectorTab === "artifacts" && (
          <ArtifactPanel artifacts={artifacts} onOpen={onOpenArtifact} lang={lang} />
        )}
        {inspectorTab === "plan" && <PlanPanel plan={plan} lang={lang} />}
        {inspectorTab === "run" && <RunPanel recipes={recipes} lang={lang} onRunRecipe={onRunRecipe} />}
        {inspectorTab === "problems" && <ProblemsPanel timeline={timeline} lang={lang} />}
        {inspectorTab === "review" && <ReviewPanel review={review} lang={lang} onOpenReviewEvidence={onOpenReviewEvidence} />}
        {inspectorTab === "permissions" && (
          <PermissionsPanel permissionContext={permissionContext} lang={lang} />
        )}
        {inspectorTab === "runtime" && (
          <RuntimePanel snapshot={snapshot} lang={lang} />
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

function RunPanel({ recipes, lang, onRunRecipe }) {
  const items = Array.isArray(recipes) ? recipes : [];
  return (
    <div className="panel-preview">
      <h3>{t("inspector.run", lang)}</h3>
      {items.length > 0 ? (
        <div className="recipe-list">
          {items.map((recipe) => (
            <RecipeCard key={recipe.id} recipe={recipe} lang={lang} onRunRecipe={onRunRecipe} />
          ))}
        </div>
      ) : (
        <div className="empty-copy">{t("inspector.noRecipes", lang)}</div>
      )}
    </div>
  );
}

function RecipeCard({ recipe, lang, onRunRecipe }) {
  const [target, setTarget] = React.useState("");
  const [profile, setProfile] = React.useState("");
  const supportsTarget = Boolean(recipe.supports_target);
  const supportsProfile = Boolean(recipe.supports_profile);

  return (
    <div className="recipe-card">
      <div className="recipe-header">
        <span className="recipe-label">{recipe.label || recipe.id}</span>
        <span className="recipe-tool">{recipe.tool_name}</span>
      </div>
      <div className="recipe-meta">
        <span className="rule-chip monospace">{recipe.id}</span>
        <span className="rule-chip monospace">{recipe.source || "detected"}</span>
      </div>
      <code className="recipe-command">{recipe.command || "-"}</code>
      {(supportsTarget || supportsProfile) ? (
        <div className="recipe-inputs">
          {supportsTarget ? (
            <input
              className="recipe-input"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              placeholder={t("inspector.runTarget", lang)}
            />
          ) : null}
          {supportsProfile ? (
            <input
              className="recipe-input"
              value={profile}
              onChange={(e) => setProfile(e.target.value)}
              placeholder={t("inspector.runProfile", lang)}
            />
          ) : null}
        </div>
      ) : null}
      <button
        className="primary"
        onClick={() => onRunRecipe && onRunRecipe(recipe.id, { target, profile })}
      >
        {t("inspector.runRecipe", lang)}
      </button>
    </div>
  );
}

function ProblemsPanel({ timeline, lang }) {
  const items = collectProblems(timeline || []);
  return (
    <div className="panel-preview">
      <h3>{t("inspector.problems", lang)}</h3>
      {items.length > 0 ? (
        <div className="problem-list">
          {items.map((item, index) => (
            <div key={`${index}-${item.title}-${item.detail}`} className={`review-finding severity-${item.severity}`}>
              <div className="review-finding-header">
                <span className="review-finding-severity">{item.severity}</span>
                <span className="review-finding-title">{item.title}</span>
              </div>
              <div className="review-finding-body">{item.detail}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-copy">{t("inspector.noProblems", lang)}</div>
      )}
    </div>
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
                <span className="permission-rule-category">{rule.category || "all"}</span>
                <span className="permission-rule-reason">{rule.reason || "-"}</span>
              </summary>
              <div className="permission-rule-body">
                <RuleField
                  label={t("inspector.ruleTools", lang)}
                  values={Array.isArray(rule.tool_names) ? rule.tool_names : []}
                />
                <RuleField
                  label={t("inspector.rulePaths", lang)}
                  values={Array.isArray(rule.path_globs) ? rule.path_globs : []}
                />
                <RuleField
                  label={t("inspector.ruleCwds", lang)}
                  values={Array.isArray(rule.cwd_globs) ? rule.cwd_globs : []}
                />
                <RuleField
                  label={t("inspector.ruleCommands", lang)}
                  values={Array.isArray(rule.command_patterns) ? rule.command_patterns : []}
                  monospace={true}
                />
              </div>
            </details>
          ))}
        </div>
      ) : (
        <div className="empty-copy">{t("inspector.noPermissionRules", lang)}</div>
      )}
    </div>
  );
}

function RuntimePanel({ snapshot, lang }) {
  const runtime = snapshot?.runtimeEnvironment || {};
  const warnings = Array.isArray(snapshot?.fallbackWarnings)
    ? snapshot.fallbackWarnings
    : Array.isArray(runtime?.fallback_warnings)
      ? runtime.fallback_warnings
      : [];
  const recentTransitions = Array.isArray(snapshot?.recentTransitions)
    ? snapshot.recentTransitions
    : [];
  const resolvedRoots = runtime?.resolved_tool_roots || {};
  const toolSources = runtime?.tool_sources || {};
  if (!snapshot) {
    return <div className="empty-copy">{t("inspector.noRuntime", lang)}</div>;
  }
  return (
    <div className="panel-preview">
      <h3>{t("inspector.runtime", lang)}</h3>
      <div className="runtime-summary">
        <div><strong>{t("inspector.sessionStatus", lang)}:</strong> {snapshot.status || "-"}</div>
        <div><strong>{t("inspector.lastState", lang)}:</strong> {snapshot.lastTransitionDisplayReason || snapshot.lastTransitionReason || "-"}</div>
        <div><strong>{t("inspector.lastStateMessage", lang)}:</strong> {snapshot.lastTransitionMessage || "-"}</div>
        <div><strong>{t("inspector.runtimeSource", lang)}:</strong> {snapshot.runtimeSource || "-"}</div>
        <div><strong>{t("inspector.runtimeReady", lang)}:</strong> {snapshot.bundledToolsReady ? t("inspector.yes", lang) : t("inspector.no", lang)}</div>
      </div>
      <h3>{t("inspector.recentTransitions", lang)}</h3>
      {recentTransitions.length > 0 ? (
        <ul className="review-risk-list">
          {recentTransitions.map((entry, index) => (
            <li key={`${index}-${entry.reason || entry.displayReason || "transition"}`}>
              <strong>{entry.displayReason || entry.display_reason || entry.reason || "-"}</strong>
              {entry.message ? `: ${entry.message}` : ""}
            </li>
          ))}
        </ul>
      ) : (
        <div className="empty-copy">{t("inspector.noRecentTransitions", lang)}</div>
      )}
      <h3>{t("inspector.runtimeResolvedRoots", lang)}</h3>
      <div className="runtime-grid">
        {Object.entries(resolvedRoots).map(([key, value]) => (
          <div key={key} className="runtime-row">
            <span className="runtime-key">{key}</span>
            <code className="runtime-value">{value || "-"}</code>
          </div>
        ))}
      </div>
      <h3>{t("inspector.runtimeToolSources", lang)}</h3>
      <div className="rule-chip-list">
        {Object.keys(toolSources).length > 0 ? (
          Object.entries(toolSources).map(([key, value]) => (
            <span key={key} className="rule-chip monospace">{key}: {value}</span>
          ))
        ) : (
          <div className="empty-copy">-</div>
        )}
      </div>
      <h3>{t("inspector.runtimeWarnings", lang)}</h3>
      {warnings.length > 0 ? (
        <ul className="review-risk-list">
          {warnings.map((warning, index) => (
            <li key={`${index}-${warning}`}>{warning}</li>
          ))}
        </ul>
      ) : (
        <div className="empty-copy">{t("inspector.noRuntimeWarnings", lang)}</div>
      )}
    </div>
  );
}

function collectProblems(timeline) {
  const results = [];
  for (const item of [...timeline].reverse()) {
    if (item.kind !== "tool") continue;
    const data = item.data || {};
    const diagnostics = Array.isArray(data.diagnostics) ? data.diagnostics : [];
    for (const diagnostic of diagnostics) {
      results.push({
        severity: diagnostic.level || "warning",
        title: diagnostic.file || item.label || item.toolName || "Diagnostic",
        detail: `${diagnostic.line || 1}:${diagnostic.column || 1} ${diagnostic.message || ""}`.trim(),
      });
    }
    const summary = data.test_summary || {};
    if (summary.failed > 0) {
      results.push({
        severity: "high",
        title: item.label || item.toolName || "Tests",
        detail: `${summary.failed} failing tests (${summary.total || 0} total)`,
      });
    }
    const qualityReasons = Array.isArray(data.reasons) ? data.reasons : [];
    for (const reason of qualityReasons) {
      results.push({
        severity: "medium",
        title: item.label || item.toolName || "Quality",
        detail: reason,
      });
    }
  }
  return results.slice(0, 20);
}

function ReviewPanel({ review, lang, onOpenReviewEvidence }) {
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
      <ReviewSections sections={sections} lang={lang} onOpenReviewEvidence={onOpenReviewEvidence} />
    </div>
  );
}

function ReviewSections({ sections, lang, onOpenReviewEvidence }) {
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
            <div className="review-section-body">
              {key === "diagnostics" && items.map((item, index) => (
                <DiagnosticEvidenceCard key={`${key}-${index}`} item={item} lang={lang} onOpenReviewEvidence={onOpenReviewEvidence} />
              ))}
              {key === "tests" && items.map((item, index) => (
                <TestEvidenceCard key={`${key}-${index}`} item={item} lang={lang} />
              ))}
              {key === "coverage" && items.map((item, index) => (
                <CoverageEvidenceCard key={`${key}-${index}`} item={item} lang={lang} />
              ))}
              {key === "quality" && items.map((item, index) => (
                <QualityEvidenceCard key={`${key}-${index}`} item={item} lang={lang} />
              ))}
              {key === "git" && items.map((item, index) => (
                <GitEvidenceCard key={`${key}-${index}`} item={item} lang={lang} onOpenReviewEvidence={onOpenReviewEvidence} />
              ))}
            </div>
          </details>
        );
      })}
    </div>
  );
}

function RuleField({ label, values, monospace = false }) {
  return (
    <div className="rule-field">
      <div className="rule-field-label">{label}</div>
      {values.length > 0 ? (
        <div className="rule-chip-list">
          {values.map((value) => (
            <span key={`${label}-${value}`} className={`rule-chip${monospace ? " monospace" : ""}`}>
              {value}
            </span>
          ))}
        </div>
      ) : (
        <div className="rule-field-empty">-</div>
      )}
    </div>
  );
}

function DiagnosticEvidenceCard({ item, lang, onOpenReviewEvidence }) {
  const diagnostics = Array.isArray(item.diagnostics) ? item.diagnostics : [];
  return (
    <div className="evidence-card">
      <div className="evidence-header">
        <span className="evidence-title">{item.tool_name || t("inspector.reviewDiagnostics", lang)}</span>
        <span className="evidence-meta">
          E{item.error_count || 0} / W{item.warning_count || 0}
        </span>
      </div>
      {diagnostics.length > 0 ? (
        <div className="evidence-list">
          {diagnostics.map((diag, index) => (
            <button
              key={`${item.call_id || item.tool_name}-${index}`}
              className="evidence-row monospace evidence-link"
              onClick={() => onOpenReviewEvidence && onOpenReviewEvidence({
                kind: "diagnostic",
                title: `${diag.file || "?"}:${diag.line || 1}:${diag.column || 1}`,
                content: `${diag.file || "?"}:${diag.line || 1}:${diag.column || 1} ${diag.message || ""}`,
              })}
            >
              {diag.file || "?"}:{diag.line || 1}:{diag.column || 1} {diag.message || ""}
            </button>
          ))}
        </div>
      ) : (
        <div className="rule-field-empty">-</div>
      )}
    </div>
  );
}

function TestEvidenceCard({ item, lang }) {
  const summary = item.summary || {};
  return (
    <div className="evidence-card">
      <div className="evidence-header">
        <span className="evidence-title">{item.tool_name || t("inspector.reviewTests", lang)}</span>
      </div>
      <div className="evidence-grid">
        <span>{t("inspector.testPassed", lang)}: {summary.passed || 0}</span>
        <span>{t("inspector.testFailed", lang)}: {summary.failed || 0}</span>
        <span>{t("inspector.testSkipped", lang)}: {summary.skipped || 0}</span>
        <span>{t("inspector.testTotal", lang)}: {summary.total || 0}</span>
      </div>
    </div>
  );
}

function CoverageEvidenceCard({ item, lang }) {
  const summary = item.summary || {};
  const rows = [
    ["line", summary.line_coverage],
    ["function", summary.function_coverage],
    ["branch", summary.branch_coverage],
    ["region", summary.region_coverage],
  ];
  return (
    <div className="evidence-card">
      <div className="evidence-header">
        <span className="evidence-title">{item.tool_name || t("inspector.reviewCoverage", lang)}</span>
      </div>
      <div className="evidence-grid">
        {rows.map(([label, value]) => (
          <span key={label}>
            {label}: {value == null ? "-" : `${Number(value).toFixed(2)}%`}
          </span>
        ))}
      </div>
    </div>
  );
}

function QualityEvidenceCard({ item, lang }) {
  const reasons = Array.isArray(item.reasons) ? item.reasons : [];
  return (
    <div className="evidence-card">
      <div className="evidence-header">
        <span className="evidence-title">{item.tool_name || t("inspector.reviewQuality", lang)}</span>
        <span className={`quality-pill ${item.passed ? "passed" : "failed"}`}>
          {item.passed ? t("inspector.qualityPassed", lang) : t("inspector.qualityFailed", lang)}
        </span>
      </div>
      {reasons.length > 0 ? (
        <ul className="review-risk-list">
          {reasons.map((reason, index) => (
            <li key={`${index}-${reason}`}>{reason}</li>
          ))}
        </ul>
      ) : (
        <div className="rule-field-empty">-</div>
      )}
    </div>
  );
}

function GitEvidenceCard({ item, lang, onOpenReviewEvidence }) {
  const hasArtifact = Boolean(item.diff_artifact_ref);
  const hasDiff = Boolean(item.diff_preview);
  const available = item.available !== false;
  return (
    <div className="evidence-card">
      <div className="evidence-header">
        <span className="evidence-title">{t("inspector.reviewGit", lang)}</span>
      </div>
      <div className="evidence-grid">
        <span>{t("inspector.gitAvailable", lang)}: {available ? t("inspector.yes", lang) : t("inspector.no", lang)}</span>
        <span>{t("inspector.gitFiles", lang)}: {item.file_count || 0}</span>
        <span>{t("inspector.gitLines", lang)}: {item.line_count || 0}</span>
      </div>
      {!available && item.error ? <div className="rule-field-empty">{item.error}</div> : null}
      {hasArtifact || hasDiff ? (
        <button
          className="ghost evidence-action"
          onClick={() => onOpenReviewEvidence && onOpenReviewEvidence({
            kind: "git",
            title: t("inspector.reviewGit", lang),
            diff: item.diff_preview || "",
            artifactRef: item.diff_artifact_ref || "",
            content: JSON.stringify(item, null, 2),
          })}
        >
          {t("inspector.openDiff", lang)}
        </button>
      ) : (
        <button
          className="ghost evidence-action"
          onClick={() => onOpenReviewEvidence && onOpenReviewEvidence({
            kind: "git",
            title: t("inspector.reviewGit", lang),
            content: JSON.stringify(item, null, 2),
          })}
        >
          {t("inspector.openEvidence", lang)}
        </button>
      )}
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
