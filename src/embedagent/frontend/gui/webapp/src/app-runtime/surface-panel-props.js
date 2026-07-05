export function buildSurfacePanelProps({
  state = {},
  appChrome = {},
  sourceControlChrome,
  diffPanelChrome,
  surfacePanelController,
} = {}) {
  const controller = surfacePanelController || {};
  return {
    plan: state.plan,
    diffSurface: state.diffSurface,
    sourceControl: state.sourceControl,
    sourceControlChrome,
    diffPanelChrome,
    appShell: state.app,
    chrome: appChrome.surfacePanel || {},
    onFocusDiffFile: controller.focusDiffFile,
    onRefreshSourceControl: controller.refreshSourceControl,
    onSelectSourceControlFile: controller.selectSourceControlFile,
    onAppSettingsChange: controller.changeAppSettings,
  };
}
