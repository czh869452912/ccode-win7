import { surfaceDefinitionFor } from "../workbench/surfaces.js";

const RIGHT_PANEL_RESOURCE_SURFACES = Object.freeze({
  file: "file",
  files: "files",
  preview: "preview",
});

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
      surfaceDefinition: definition,
    });
  },
}));

const RIGHT_PANEL_ACTIVATION_HANDLERS = Object.freeze(Object.assign(Object.create(null), {
  "terminal.open_active": ({ surface, terminalController }) => {
    if (surface && surface.activeTerminalId) {
      void terminalController.openSession(surface.activeTerminalId);
    }
  },
}));

function declaredRightPanelSurfaceDefinition(kind, appCapabilities) {
  const capabilities =
    appCapabilities && typeof appCapabilities === "object" ? appCapabilities : null;
  return capabilities ? surfaceDefinitionFor(kind, capabilities) : null;
}

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
  function canOpenSurface(kind) {
    const surfaceKind = String(kind || "");
    const appCapabilities = getAppCapabilities();
    const definition = declaredRightPanelSurfaceDefinition(surfaceKind, appCapabilities);
    return Boolean(definition);
  }

  function canOpenPreviewSurface() {
    return canOpenSurface(RIGHT_PANEL_RESOURCE_SURFACES.preview);
  }

  function openSurface(kind, title = "") {
    const surfaceKind = String(kind || "");
    const appCapabilities = getAppCapabilities();
    const definition = declaredRightPanelSurfaceDefinition(surfaceKind, appCapabilities);
    const handler = definition ? RIGHT_PANEL_OPEN_HANDLERS[definition.openKind] : null;
    if (handler) {
      handler({ appCapabilities, definition, dispatch, surfaceKind, terminalController, title });
      return true;
    }
    return false;
  }

  function openFileSurface({ filePath, title = "", revealLine } = {}) {
    const appCapabilities = getAppCapabilities();
    const definition = declaredRightPanelSurfaceDefinition(
      RIGHT_PANEL_RESOURCE_SURFACES.file,
      appCapabilities,
    );
    if (!definition) return false;
    const normalizedPath = normalizeFileSurfacePath(filePath);
    if (!normalizedPath) return false;
    dispatch({
      type: "workbench_surface_opened",
      placement: "right",
      kind: RIGHT_PANEL_RESOURCE_SURFACES.file,
      title: String(title || normalizedPath),
      resourceId: normalizedPath,
      filePath: normalizedPath,
      revealLine,
    });
    return true;
  }

  function openFilesSurface() {
    return openSurface(RIGHT_PANEL_RESOURCE_SURFACES.files);
  }

  function openPreviewSurface({ resourceId, title = "", previewSnapshot = null } = {}) {
    const appCapabilities = getAppCapabilities();
    const definition = declaredRightPanelSurfaceDefinition(
      RIGHT_PANEL_RESOURCE_SURFACES.preview,
      appCapabilities,
    );
    if (!definition) return false;
    const normalizedResourceId = String(resourceId || "").trim();
    const normalizedTitle = String(title || normalizedResourceId).trim();
    if (!normalizedTitle) return false;
    dispatch({
      type: "workbench_surface_opened",
      placement: "right",
      kind: RIGHT_PANEL_RESOURCE_SURFACES.preview,
      title: normalizedTitle,
      resourceId: normalizedResourceId,
      previewSnapshot,
    });
    return true;
  }

  function activateSurface(surface) {
    if (!surface) return;
    dispatch({
      type: "workbench_surface_activated",
      placement: "right",
      surfaceId: surface.id,
      kind: surface.kind,
    });
    const appCapabilities = getAppCapabilities();
    const definition = surfaceDefinitionFor(surface.kind, appCapabilities);
    const handler = definition ? RIGHT_PANEL_ACTIVATION_HANDLERS[definition.activationKind] : null;
    if (handler) {
      handler({ appCapabilities, definition, dispatch, surface, terminalController });
    }
  }

  function closeSurface(surface) {
    if (!surface) return;
    dispatch({
      type: "workbench_surface_closed",
      placement: "right",
      surfaceId: surface.id,
      kind: surface.kind,
      resourceId: surface.resourceId,
    });
  }

  function closeOtherSurfaces(surface) {
    if (!surface) return;
    dispatch({
      type: "workbench_surface_close_others",
      placement: "right",
      surfaceId: surface.id,
    });
  }

  function closeSurfacesToRight(surface) {
    if (!surface) return;
    dispatch({
      type: "workbench_surface_close_to_right",
      placement: "right",
      surfaceId: surface.id,
    });
  }

  function closeAllSurfaces() {
    dispatch({ type: "workbench_surface_close_all", placement: "right" });
  }

  return {
    activateSurface,
    canOpenPreviewSurface,
    closeAllSurfaces,
    closeOtherSurfaces,
    closeSurface,
    closeSurfacesToRight,
    fileSurfaceTitle,
    normalizeFileSurfacePath,
    openFileSurface,
    openFilesSurface,
    openPreviewSurface,
    openSurface,
    rightPanelSurfaceTitle,
  };
}
