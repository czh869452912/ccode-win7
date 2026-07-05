import { surfaceDefinitionFor } from "../workbench/surfaces.js";

const RIGHT_PANEL_OPEN_HANDLERS = Object.freeze(Object.assign(Object.create(null), {
  "terminal.right_panel": ({ terminalController }) => {
    void terminalController.openRightPanelSurface();
  },
  "workbench.surface": ({ appCapabilities, definition, dispatch, surfaceKind, title }) => {
    dispatch({
      type: "workbench_surface_opened",
      placement: "right",
      kind: surfaceKind,
      title: rightPanelSurfaceTitle(surfaceKind, title, appCapabilities),
      resourceId: definition?.defaultResourceId || "",
    });
  },
}));

export function rightPanelSurfaceTitle(kind, fallback = "", appCapabilities = null) {
  const definition = surfaceDefinitionFor(kind, appCapabilities);
  const descriptorTitle = String(definition?.title || "").trim();
  return descriptorTitle || String(fallback || "").trim();
}

export function normalizeFileSurfacePath(path) {
  return String(path || "").replace(/\\/g, "/").replace(/^\/+/, "");
}

export function fileSurfaceTitle(path, filePreviewChrome = {}) {
  const normalized = normalizeFileSurfacePath(path);
  if (!normalized) return filePreviewChrome.defaultFileTitle || "";
  const parts = normalized.split("/");
  return parts[parts.length - 1] || normalized;
}

export function createRightPanelController({
  dispatch,
  terminalController,
  getAppCapabilities = () => null,
}) {
  function openSurface(kind, title = "") {
    const surfaceKind = String(kind || "");
    const appCapabilities = getAppCapabilities();
    const definition = surfaceDefinitionFor(surfaceKind, appCapabilities);
    const handler = definition ? RIGHT_PANEL_OPEN_HANDLERS[definition.openKind] : null;
    if (handler) {
      handler({ appCapabilities, definition, dispatch, surfaceKind, terminalController, title });
    }
  }

  return {
    fileSurfaceTitle,
    normalizeFileSurfacePath,
    openSurface,
    rightPanelSurfaceTitle,
  };
}
