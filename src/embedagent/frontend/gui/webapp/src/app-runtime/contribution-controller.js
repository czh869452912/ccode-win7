function text(value) {
  return String(value || "").trim();
}

function normalizeFilePath(path) {
  return String(path || "").replace(/\\/g, "/").replace(/^\/+/, "");
}

function descriptorFor(getShellDescriptor, surfaceId) {
  const shell = typeof getShellDescriptor === "function" ? getShellDescriptor() : {};
  const surfaces = Array.isArray(shell?.surfaces) ? shell.surfaces : [];
  return surfaces.find((item) => item?.id === surfaceId) || null;
}

export function createContributionController({ dispatch, getShellDescriptor } = {}) {
  const send = typeof dispatch === "function" ? dispatch : () => {};

  function openSurface(surfaceId, label = "", options = {}) {
    const id = text(surfaceId);
    const descriptor = descriptorFor(getShellDescriptor, id);
    if (!descriptor || descriptor.placement !== "secondary") return false;
    send({
      type: "contribution_opened",
      kind: id,
      label: text(label || descriptor.label),
      rendererKey: text(descriptor.rendererKey),
      ...options,
    });
    return true;
  }

  function openFile({ filePath, title = "", revealLine } = {}) {
    const path = normalizeFilePath(filePath);
    if (!path) return false;
    const shell = typeof getShellDescriptor === "function" ? getShellDescriptor() : {};
    const descriptor = (shell.surfaces || []).find((item) => item?.rendererKey === "file_reference");
    if (!descriptor) return false;
    send({
      type: "contribution_opened",
      kind: descriptor.id,
      label: text(title || path.split("/").pop()),
      rendererKey: "file_preview",
      resourceId: path,
      filePath: path,
      revealLine,
    });
    return true;
  }

  function openPreview({ resourceId, title = "", previewSnapshot = null } = {}) {
    return openSurface("preview", title || resourceId, {
      resourceId: text(resourceId),
      previewSnapshot,
    });
  }

  function activate(surface) {
    if (surface?.id) send({ type: "contribution_activated", surfaceId: surface.id });
  }

  function close(surface) {
    if (surface?.id) send({ type: "contribution_closed", surfaceId: surface.id });
  }

  function closeOthers(surface) {
    if (surface?.id) send({ type: "contribution_close_others", surfaceId: surface.id });
  }

  function closeAfter(surface) {
    if (surface?.id) send({ type: "contribution_close_after", surfaceId: surface.id });
  }

  function closeAll() {
    send({ type: "contribution_close_all" });
  }

  return {
    activate,
    close,
    closeAfter,
    closeAll,
    closeOthers,
    normalizeFilePath,
    openFile,
    openFiles: () => openSurface("files"),
    openPreview,
    openSurface,
  };
}
