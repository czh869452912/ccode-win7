export function terminalCapabilityEnabled(appCapabilities = {}) {
  const capabilities =
    appCapabilities && typeof appCapabilities === "object" ? appCapabilities : {};
  return capabilities?.terminal?.enabled === true;
}
