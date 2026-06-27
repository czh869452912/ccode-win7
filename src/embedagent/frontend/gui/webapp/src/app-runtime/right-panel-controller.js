import { surfaceDefinitionFor, titleForSurfaceKind } from "../workbench/surfaces.js";

export function rightPanelSurfaceTitle(kind, fallback = "") {
  const label = String(fallback || "").replace(/^Open\s+/i, "").trim();
  if (label) return label;
  return titleForSurfaceKind(kind);
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
}) {
  function openSurface(kind, title = "") {
    const surfaceKind = String(kind || "");
    if (surfaceKind === "file") return;
    if (surfaceKind === "terminal") {
      void terminalController.openRightPanelSurface();
      return;
    }
    dispatch({
      type: "workbench_surface_opened",
      placement: "right",
      kind: surfaceKind,
      title: rightPanelSurfaceTitle(surfaceKind, title),
      resourceId: surfaceDefinitionFor(surfaceKind)?.defaultResourceId || "",
    });
    dispatch({ type: "set_inspector", value: surfaceKind });
  }

  return {
    fileSurfaceTitle,
    normalizeFileSurfacePath,
    openSurface,
    rightPanelSurfaceTitle,
  };
}
