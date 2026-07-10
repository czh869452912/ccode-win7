function defaultWindowObject() {
  return typeof window !== "undefined" ? window : {};
}

export function createBrowserDialogService({ windowObject } = {}) {
  const target = windowObject || defaultWindowObject();

  function prompt(message, initialValue) {
    if (typeof target.prompt !== "function") return null;
    return target.prompt(message, initialValue);
  }

  function confirm(message) {
    if (typeof target.confirm !== "function") return false;
    return target.confirm(message);
  }

  return { prompt, confirm };
}
