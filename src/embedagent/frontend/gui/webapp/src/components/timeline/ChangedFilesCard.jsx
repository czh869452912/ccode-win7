import React from "react";

import { buildChangedFilesTree, summarizeDiffStats } from "../../session-runtime/t3-timeline.js";

function DiffStatLabel({ additions = 0, deletions = 0 }) {
  return (
    <span className="t3-diff-stats">
      <span className="t3-diff-add">+{additions || 0}</span>
      <span className="t3-diff-del">-{deletions || 0}</span>
    </span>
  );
}

function formatTemplate(template = "", values = {}) {
  return String(template || "").replace(/\{(\w+)\}/g, (_match, key) =>
    String(values[key] ?? ""),
  );
}

function TreeNode({ node, depth, turnId, onOpenDiff, allExpanded }) {
  const [expanded, setExpanded] = React.useState(allExpanded);
  React.useEffect(() => {
    setExpanded(allExpanded);
  }, [allExpanded]);

  if (node.kind === "directory") {
    return (
      <div className="t3-changed-tree-node directory" data-testid={`changed-dir--${node.path}`}>
        <button
          type="button"
          className="t3-changed-tree-row"
          style={{ paddingLeft: `${7 + depth * 14}px` }}
          aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}
        >
          <span className={`t3-tree-chevron${expanded ? " expanded" : ""}`} aria-hidden="true">{">"}</span>
          <span className="t3-tree-icon" aria-hidden="true">{expanded ? "v" : ">"}</span>
          <span className="t3-tree-name">{node.name}</span>
          {node.stat ? <DiffStatLabel additions={node.stat.additions} deletions={node.stat.deletions} /> : null}
        </button>
        {expanded ? (
          <div className="t3-changed-tree-children">
            {(node.children || []).map((child) => (
              <TreeNode
                key={`${child.kind}:${child.path}`}
                node={child}
                depth={depth + 1}
                turnId={turnId}
                onOpenDiff={onOpenDiff}
                allExpanded={allExpanded}
              />
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  const stat = node.stat || { additions: 0, deletions: 0 };
  return (
    <button
      type="button"
      className="t3-changed-tree-row file"
      style={{ paddingLeft: `${7 + depth * 14}px` }}
      onClick={() => onOpenDiff && onOpenDiff({ turnId, filePath: node.path })}
      data-testid={`changed-file--${node.path}`}
    >
      <span className="t3-tree-spacer" aria-hidden="true" />
      <span className="t3-tree-icon" aria-hidden="true">[]</span>
      <span className="t3-tree-name">{node.name}</span>
      <DiffStatLabel additions={stat.additions} deletions={stat.deletions} />
    </button>
  );
}

export default function ChangedFilesCard({ row, onOpenDiff, chrome = {} }) {
  const files = row.files || row.changedFiles || [];
  const [allExpanded, setAllExpanded] = React.useState(false);
  const tree = React.useMemo(() => buildChangedFilesTree(files), [files]);
  const stats = React.useMemo(() => summarizeDiffStats(files), [files]);
  if (!files.length) return null;
  return (
    <section className="t3-changed-files-card" data-testid="changed-files-card" data-row-kind="diff_summary">
      <header className="t3-changed-files-title">
        <button
          className="t3-changed-files-open"
          type="button"
          onClick={() => onOpenDiff && onOpenDiff({ turnId: row.turnId || "", filePath: files[0]?.path || "" })}
        >
          <span>{formatTemplate(chrome.summaryTemplate, { count: files.length })}</span>
          <DiffStatLabel additions={row.additions ?? stats.additions} deletions={row.deletions ?? stats.deletions} />
        </button>
        <div className="t3-changed-files-actions">
          <button
            type="button"
            className="t3-mini-button"
            onClick={() => setAllExpanded((value) => !value)}
          >
            {allExpanded ? chrome.collapseLabel || "" : chrome.expandLabel || ""}
          </button>
          <button
            type="button"
            className="t3-mini-button"
            onClick={() => onOpenDiff && onOpenDiff({ turnId: row.turnId || "", filePath: files[0]?.path || "" })}
          >
            {chrome.viewDiffLabel || ""}
          </button>
        </div>
      </header>
      <div className="t3-changed-files-tree" data-testid="changed-files-tree">
        {tree.map((node) => (
          <TreeNode
            key={`${node.kind}:${node.path}`}
            node={node}
            depth={0}
            turnId={row.turnId || ""}
            onOpenDiff={onOpenDiff}
            allExpanded={allExpanded}
          />
        ))}
      </div>
    </section>
  );
}
