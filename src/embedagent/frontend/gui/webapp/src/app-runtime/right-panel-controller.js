import { surfaceDefinitionFor, titleForSurfaceKind } from "../workbench/surfaces.js";

export function rightPanelSurfaceTitle(kind, fallback = "", appCapabilities = null) {
  const label = String(fallback || "").replace(/^Open\s+/i, "").trim();
  if (label) return label;
  return titleForSurfaceKind(kind, appCapabilities);
}

export function normalizeFileSurfacePath(path) {
  return String(path || "").replace(/\\/g, "/").replace(/^\/+/, "");
}

export function fileSurfaceTitle(path) {
  const normalized = normalizeFileSurfacePath(path);
  if (!normalized) return "File";
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
    if (surfaceKind === "file") return;
    if (surfaceKind === "terminal") {
      void terminalController.openRightPanelSurface();
      return;
    }
    const appCapabilities = getAppCapabilities();
    const definition = surfaceDefinitionFor(surfaceKind, appCapabilities);
    dispatch({
      type: "workbench_surface_opened",
      placement: "right",
      kind: surfaceKind,
      title: rightPanelSurfaceTitle(surfaceKind, title, appCapabilities),
      resourceId: definition?.defaultResourceId || "",
    });
  }

  return {
    fileSurfaceTitle,
    normalizeFileSurfacePath,
    openSurface,
    rightPanelSurfaceTitle,
  };
}
