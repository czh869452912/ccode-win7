function invoke(callback, ...args) {
  if (typeof callback !== "function") {
    return Promise.resolve();
  }
  return Promise.resolve().then(() => callback(...args));
}

export function createComposerController({
  dispatch,
  getComposerDraft,
  submitText,
  refreshSourceControl,
} = {}) {
  const send = typeof dispatch === "function" ? dispatch : () => {};
  const readDraft =
    typeof getComposerDraft === "function" ? getComposerDraft : () => "";
  const submit = typeof submitText === "function" ? submitText : () => {};

  function setDraft(value) {
    send({ type: "set_composer", value });
  }

  async function sendMessage() {
    await submit(readDraft());
  }

  function openCommandPalette() {
    send({ type: "workbench_command_palette_opened" });
  }

  async function refreshSourceControlStatus() {
    await invoke(refreshSourceControl, true);
  }

  return {
    openCommandPalette,
    refreshSourceControl: refreshSourceControlStatus,
    sendMessage,
    setDraft,
  };
}
