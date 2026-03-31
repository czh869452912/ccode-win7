import React from "react";
import { useLang } from "../LangContext.js";
import { t } from "../strings.js";
import DiffView from "./DiffView.jsx";

export default function Inspector({
  inspectorTab,
  todos,
  artifacts,
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
