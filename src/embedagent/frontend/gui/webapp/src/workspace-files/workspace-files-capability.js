import { surfaceDefinitionFor } from "../workbench/surfaces.js";

function appObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function composerHintDescriptors(appCapabilities) {
  const composer = appObject(appCapabilities?.chrome?.composer);
  return Array.isArray(composer?.hints) ? composer.hints : [];
}

function hasComposerFileHint(appCapabilities) {
  return composerHintDescriptors(appCapabilities).some((hint) => {
    if (!hint || typeof hint !== "object" || Array.isArray(hint)) return false;
    return String(hint.id || "").trim() === "file";
  });
}

export function workspaceFilesCapabilityEnabled(appCapabilities = {}) {
  const capabilities = appObject(appCapabilities);
  if (!capabilities) return false;
  return Boolean(
    surfaceDefinitionFor("files", capabilities) ||
      surfaceDefinitionFor("file", capabilities) ||
      hasComposerFileHint(capabilities),
  );
}
