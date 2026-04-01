import React from "react";
import { Tree } from "react-arborist";
import { useLang } from "../LangContext.js";
import { t } from "../strings.js";

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
  const lang = useLang();

  return (
    <aside className="sidebar" role="navigation" aria-label="Sidebar">
      <div className="brand">
        <div className="brand-mark">EmbedAgent</div>
        <div className="brand-sub">{t("brand.sub", lang)}</div>
      </div>
      <div className="sidebar-tabs" role="tablist">
        <button
          role="tab"
          aria-selected={sidebarTab === "chats"}
          className={`sidebar-tab${sidebarTab === "chats" ? " active" : ""}`}
          onClick={() => onTabChange("chats")}
        >
          {t("sidebar.chats", lang)}
        </button>
        <button
          role="tab"
          aria-selected={sidebarTab === "files"}
          className={`sidebar-tab${sidebarTab === "files" ? " active" : ""}`}
          onClick={() => onTabChange("files")}
        >
          {t("sidebar.files", lang)}
        </button>
      </div>
      {sidebarTab === "chats" ? (
        <div className="thread-panel" role="tabpanel" aria-label={t("sidebar.chats", lang)}>
          <button
            className="primary wide"
            onClick={() => onCreateSession(currentMode)}
          >
            {t("sidebar.newSession", lang)}
          </button>
          <div className="thread-list" role="list">
            {sessions.map((session) => (
              <button
                key={session.id}
                role="listitem"
                className={`thread-card ${currentSessionId === session.id ? "selected" : ""}`}
                aria-pressed={currentSessionId === session.id}
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
        <div className="files-panel" role="tabpanel" aria-label={t("sidebar.files", lang)}>
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
                role="treeitem"
                aria-expanded={node.data.kind === "dir" ? node.isOpen : undefined}
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
                <span className="tree-icon" aria-hidden="true">
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
