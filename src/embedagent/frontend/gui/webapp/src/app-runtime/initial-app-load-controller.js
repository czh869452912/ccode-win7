function invoke(callback) {
  return typeof callback === "function" ? callback() : undefined;
}

export function createInitialAppLoadController({
  loadAppBootstrap,
  loadSessionCommandCapabilities,
} = {}) {
  function start() {
    const bootstrapResult = invoke(loadAppBootstrap);
    const commandCapabilitiesResult = Promise.resolve(
      invoke(loadSessionCommandCapabilities),
    ).catch(() => null);
    return { bootstrapResult, commandCapabilitiesResult };
  }

  return { start };
}
