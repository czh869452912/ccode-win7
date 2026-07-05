import { surfaceDefinitionFor } from "../workbench/surfaces.js";

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
    switch (definition ? definition.openKind : "") {
      case "terminal.right_panel":
        void terminalController.openRightPanelSurface();
        return;
      case "workbench.surface":
        dispatch({
          type: "workbench_surface_opened",
          placement: "right",
          kind: surfaceKind,
          title: rightPanelSurfaceTitle(surfaceKind, title, appCapabilities),
          resourceId: definition?.defaultResourceId || "",
        });
        return;
      default:
        return;
    }
  }

  return {
    fileSurfaceTitle,
    normalizeFileSurfacePath,
    openSurface,
    rightPanelSurfaceTitle,
  };
}
