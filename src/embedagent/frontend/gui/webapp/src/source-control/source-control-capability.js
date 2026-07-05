export function sourceControlCapabilityEnabled(appCapabilities = {}) {
  const sourceControl =
    appCapabilities?.sourceControl && typeof appCapabilities.sourceControl === "object"
      ? appCapabilities.sourceControl
      : appCapabilities?.source_control && typeof appCapabilities.source_control === "object"
        ? appCapabilities.source_control
        : {};
  return sourceControl.enabled === true;
}
