import React from "react";
import { Tree } from "react-arborist";

export default function FilesSurface({
  fileTree,
  treeHeight,
  onOpenFile,
  onLoadFileChildren,
}) {
  const nodes = Array.isArray(fileTree) ? fileTree : [];
  return (
    <div className="right-panel-files-surface" data-testid="right-panel-files-surface">
      <div className="right-panel-files-header">
        <strong>Files</strong>
        <span>{nodes.length}</span>
      </div>
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
            data-testid={`right-panel-file-node--${node.data.path}`}
          >
            <span className="tree-icon" aria-hidden="true">
              {node.data.kind === "dir" ? (node.isOpen ? "v" : ">") : "."}
            </span>
            <span className="tree-label">{node.data.name}</span>
          </div>
        )}
      </Tree>
    </div>
  );
}
