import React from "react";
import { Tree } from "react-arborist";

export default function FilesSurface({
  surface,
  fileTree,
  treeHeight,
  onOpenFile,
  onLoadFileChildren,
}) {
  const nodes = Array.isArray(fileTree) ? fileTree : [];
  const title = String(surface?.title || "").trim();
  return (
    <div className="files-contribution" data-testid="files-contribution">
      <div className="files-contribution-header">
        <strong>{title}</strong>
        <span>{nodes.length}</span>
      </div>
      <div className="files-contribution-tree" data-testid="files-contribution-tree">
        <Tree
          data={nodes}
          width={320}
          height={treeHeight || 640}
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
              data-testid={`files-contribution-node--${node.data.path}`}
            >
              <span className="tree-icon" aria-hidden="true">
                {node.data.kind === "dir" ? (node.isOpen ? "v" : ">") : "."}
              </span>
              <span className="tree-label">{node.data.name}</span>
            </div>
          )}
        </Tree>
      </div>
    </div>
  );
}
