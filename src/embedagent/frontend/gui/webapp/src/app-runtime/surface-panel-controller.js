function noop() {}

export function createSurfacePanelController({
  dispatch,
  sourceControlController,
} = {}) {
  const send = typeof dispatch === "function" ? dispatch : noop;

  function focusDiffFile(filePath) {
    send({ type: "diff_file_focused", filePath });
  }

  function refreshSourceControl() {
    return sourceControlController?.loadStatus?.(true);
  }

  function selectSourceControlFile(file, scope) {
    return sourceControlController?.openFile?.(file, scope);
  }

  function changeAppSettings(patch) {
    send({ type: "app_shell_settings_changed", patch });
  }

  return {
    changeAppSettings,
    focusDiffFile,
    refreshSourceControl,
    selectSourceControlFile,
  };
}
