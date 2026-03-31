import React from "react";
import { Tree } from "react-arborist";

export default function Sidebar({
  sidebarTab,
  sessions,
  currentSessionId,
  fileTree,
  treeHeight,
  currentMode,
  onTabChange,
  onLoadSession,
  onCreateSession,
  onOpenFile,
  onLoadFileChildren,
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">EmbedAgent</div>
        <div className="brand-sub">Codex-grade local shell</div>
      </div>
      <div className="sidebar-tabs">
        <button
          className={sidebarTab === "chats" ? "active" : ""}
          onClick={() => onTabChange("chats")}
        >
          Chats
        </button>
        <button
          className={sidebarTab === "files" ? "active" : ""}
          onClick={() => onTabChange("files")}
        >
          Files
        </button>
      </div>
      {sidebarTab === "chats" ? (
        <div className="thread-panel">
          <button className="primary wide" onClick={() => onCreateSession(currentMode)}>
            New Session
          </button>
          <div className="thread-list">
            {sessions.map((session) => (
              <button
                key={session.id}
                className={`thread-card ${currentSessionId === session.id ? "selected" : ""}`}
                onClick={() => onLoadSession(session.id)}
              >
                <span className="thread-title">{session.title}</span>
                <span className="thread-meta">
                  <span className={`thread-mode mode-${session.mode}`}>{session.mode}</span>
                  {session.updated ? (
                    <span className="thread-detail">{session.updated}</span>
                  ) : null}
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="files-panel">
          <Tree
            data={fileTree}
            width={300}
            height={treeHeight}
            rowHeight={30}
            indent={18}
            onActivate={(node) => {
              if (node.data.kind === "file") {
                onOpenFile(node.data.path);
              } else if (!node.data.childrenLoaded && node.data.hasChildren) {
                onLoadFileChildren(node.data.path);
              }
            }}
          >
            {({ node, style }) => (
              <div
                style={style}
                className={`tree-row ${node.data.kind}`}
                onClick={() => {
                  if (node.data.kind === "dir") {
                    if (!node.data.childrenLoaded && node.data.hasChildren) {
                      onLoadFileChildren(node.data.path);
                    }
                    node.toggle();
                  } else {
                    onOpenFile(node.data.path);
                  }
                }}
              >
                <span className="tree-icon">
                  {node.data.kind === "dir" ? (node.isOpen ? "▾" : "▸") : "·"}
                </span>
                <span className="tree-label">{node.data.name}</span>
              </div>
            )}
          </Tree>
        </div>
      )}
    </aside>
  );
}
