import React from "react";

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
  return (
    <aside className="inspector">
      <div className="inspector-tabs">
        <button
          className={inspectorTab === "todos" ? "active" : ""}
          onClick={() => onTabChange("todos")}
        >
          Todos
        </button>
        <button
          className={inspectorTab === "artifacts" ? "active" : ""}
          onClick={() => onTabChange("artifacts")}
        >
          Artifacts
        </button>
        <button
          className={inspectorTab === "preview" ? "active" : ""}
          onClick={() => onTabChange("preview")}
        >
          Preview
        </button>
        <button
          className={inspectorTab === "log" ? "active" : ""}
          onClick={() => onTabChange("log")}
        >
          Log
        </button>
      </div>
      <div className="inspector-body">
        {inspectorTab === "todos" && <TodoPanel todos={todos} />}
        {inspectorTab === "artifacts" && (
          <ArtifactPanel artifacts={artifacts} onOpen={onOpenArtifact} />
        )}
        {inspectorTab === "preview" && <PreviewPanel preview={preview} />}
        {inspectorTab === "log" && <LogPanel entries={eventLog} />}
        {userInput ? (
          <div className="prompt-panel">
            <h3>Input Required</h3>
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
              placeholder="Or type a custom answer…"
            />
            <button className="primary wide" onClick={() => onSubmitUserInput(null)}>
              Submit
            </button>
          </div>
        ) : null}
      </div>
    </aside>
  );
}

function TodoPanel({ todos }) {
  return (
    <div className="panel-list">
      <h3>Session Todos</h3>
      {(todos || []).length ? (
        todos.map((todo) => (
          <div key={todo.id} className="todo-row">
            <span className={todo.done ? "todo-mark done" : "todo-mark"}>
              {todo.done ? "done" : "todo"}
            </span>
            <span>{todo.content}</span>
          </div>
        ))
      ) : (
        <div className="empty-copy">No todos in this session.</div>
      )}
    </div>
  );
}

function ArtifactPanel({ artifacts, onOpen }) {
  return (
    <div className="panel-list">
      <h3>Artifacts</h3>
      {(artifacts || []).length ? (
        artifacts.map((item) => (
          <button key={item.path} className="artifact-row" onClick={() => onOpen(item.path)}>
            <span>{item.path}</span>
            <small>{item.tool_name || item.kind}</small>
          </button>
        ))
      ) : (
        <div className="empty-copy">No artifacts yet.</div>
      )}
    </div>
  );
}

function PreviewPanel({ preview }) {
  if (!preview) {
    return <div className="empty-copy">Select a file or artifact to preview.</div>;
  }
  return (
    <div className="panel-preview">
      <h3>{preview.title}</h3>
      <pre>{preview.content}</pre>
    </div>
  );
}

function LogPanel({ entries }) {
  if (!entries || entries.length === 0) {
    return <div className="empty-copy">No events yet.</div>;
  }
  return (
    <div className="log-list">
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
