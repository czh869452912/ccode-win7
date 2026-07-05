import { createTreeNode } from "../state-helpers.js";
import { workspaceFilesCapabilityEnabled } from "../workspace-files/workspace-files-capability.js";

function readAppCapabilities({ appCapabilities, getAppCapabilities }) {
  const value =
    typeof getAppCapabilities === "function" ? getAppCapabilities() : appCapabilities;
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

export function createWorkspaceFilesController({
  fetchJson,
  dispatch,
  appCapabilities,
  getAppCapabilities,
} = {}) {
  const request = typeof fetchJson === "function" ? fetchJson : () => Promise.resolve({});
  const send = typeof dispatch === "function" ? dispatch : () => {};

  async function loadFileChildren(path = ".", options = {}) {
    const optionCapabilities =
      options?.appCapabilities && typeof options.appCapabilities === "object"
        ? options.appCapabilities
        : null;
    const capabilities =
      optionCapabilities || readAppCapabilities({ appCapabilities, getAppCapabilities });
    if (!workspaceFilesCapabilityEnabled(capabilities)) {
      return null;
    }
    const normalizedPath = path || ".";
    const payload = await request(`/api/files/tree?path=${encodeURIComponent(normalizedPath)}`);
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
