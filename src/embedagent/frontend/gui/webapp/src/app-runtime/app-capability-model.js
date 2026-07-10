const EMPTY_ARRAY = Object.freeze([]);
const EMPTY_OBJECT = Object.freeze({});

function objectOrEmpty(value) {
  return value && typeof value === "object" ? value : EMPTY_OBJECT;
}

function arrayOrEmpty(value) {
  return Array.isArray(value) ? value : EMPTY_ARRAY;
}

export function buildAppCapabilityModel(capabilities = null) {
  const appCapabilities = objectOrEmpty(capabilities);
  const appChrome = objectOrEmpty(appCapabilities.chrome);
  const terminalCapability = objectOrEmpty(appCapabilities.terminal);
  const sourceControlCapability = objectOrEmpty(appCapabilities.sourceControl);
  const previewCapability = objectOrEmpty(appCapabilities.preview);
  const surfacesCapability = objectOrEmpty(appCapabilities.surfaces);
  const surfaceChrome = objectOrEmpty(surfacesCapability.chrome);

  return {
    appCapabilities,
    keybindings: arrayOrEmpty(appCapabilities.keybindings),
    commandPalette: objectOrEmpty(appCapabilities.commandPalette),
    appChrome,
    terminalChrome: objectOrEmpty(terminalCapability.chrome),
    sourceControlCapability,
    sourceControlChrome: objectOrEmpty(sourceControlCapability.chrome),
    previewCapability,
    previewChrome: objectOrEmpty(previewCapability.chrome),
    previewServers: arrayOrEmpty(previewCapability.localServers),
    surfaceChrome,
    filePreviewChrome: objectOrEmpty(surfaceChrome.filePreview),
    diffPanelChrome: objectOrEmpty(surfaceChrome.diffPanel),
    emptyState: appCapabilities.emptyState || null,
  };
}
