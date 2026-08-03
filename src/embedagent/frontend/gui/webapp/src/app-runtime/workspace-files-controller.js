import { createTreeNode } from "../state-helpers.js";
import { workspaceFilesCapabilityEnabled } from "../workspace-files/workspace-files-capability.js";

function readAppCapabilities({ appCapabilities, getAppCapabilities }) {
  const value =
    typeof getAppCapabilities === "function" ? getAppCapabilities() : appCapabilities;
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

export function createWorkspaceFilesController({
  protocol,
  dispatch,
  appCapabilities,
  getAppCapabilities,
} = {}) {
  const loadWorkspaceTree =
    protocol && typeof protocol.loadWorkspaceTree === "function"
      ? protocol.loadWorkspaceTree.bind(protocol)
      : null;
  const send = typeof dispatch === "function" ? dispatch : () => {};

  async function loadFileChildren(path = ".", options = {}) {
    const optionCapabilities =
      options?.appCapabilities && typeof options.appCapabilities === "object"
        ? options.appCapabilities
        : null;
    const capabilities =
      optionCapabilities || readAppCapabilities({ appCapabilities, getAppCapabilities });
    if (!loadWorkspaceTree || !workspaceFilesCapabilityEnabled(capabilities)) return null;
    const normalizedPath = path || ".";
    const payload = await loadWorkspaceTree(normalizedPath);
    const children = (payload.items || []).map(createTreeNode);
    if (normalizedPath === ".") {
      send({ type: "file_tree_loaded", nodes: children });
    } else {
      send({ type: "file_children_loaded", path: normalizedPath, children: payload.items || [] });
    }
    return children;
  }

  return { loadFileChildren };
}
