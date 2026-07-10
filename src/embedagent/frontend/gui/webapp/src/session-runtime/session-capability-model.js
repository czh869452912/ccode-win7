const EMPTY_OBJECT = Object.freeze({});

function objectOrEmpty(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : EMPTY_OBJECT;
}

export function buildSessionCapabilityModel(sessionCapabilities = null) {
  const capabilities = objectOrEmpty(sessionCapabilities);
  return {
    sessionCapabilities: capabilities,
    modeCatalog: objectOrEmpty(capabilities.modeCatalog),
    toolCatalog: objectOrEmpty(capabilities.toolCatalog),
    emptyState: capabilities.emptyState || null,
  };
}

export function buildSessionCapabilityModelFromState(state = null) {
  return buildSessionCapabilityModel(state && state.sessionCapabilities);
}
