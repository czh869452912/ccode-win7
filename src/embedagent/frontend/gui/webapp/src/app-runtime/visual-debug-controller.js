function readLocationSearch(windowObject) {
  return windowObject?.location?.search || "";
}

function visualDebugEnabled(search) {
  return /(?:^|[?&])visual_debug=1(?:&|$)/.test(String(search || ""));
}

function readModeValue(getCurrentMode) {
  return typeof getCurrentMode === "function" ? getCurrentMode() : "explore";
}

export function createVisualDebugController({
  windowObject,
  getLocationSearch,
  dispatch,
  openDiffFixture,
  getCurrentMode,
  installFixtures,
} = {}) {
  const readSearch =
    typeof getLocationSearch === "function"
      ? getLocationSearch
      : () => readLocationSearch(windowObject);
  const readMode = () => readModeValue(getCurrentMode);

  function fixturePayload() {
    return {
      windowObject,
      locationSearch: readSearch(),
      dispatch,
      openDiffFixture,
      currentMode: readMode() || "explore",
    };
  }

  function install() {
    const payload = fixturePayload();
    if (typeof installFixtures === "function") {
      return installFixtures(payload);
    }
    if (!visualDebugEnabled(payload.locationSearch)) return undefined;

    let active = true;
    let cleanup = null;
    import("./visual-debug-fixtures.js").then((module) => {
      if (!active || typeof module.installVisualDebugFixtures !== "function") return;
      cleanup = module.installVisualDebugFixtures(payload);
    });
    return () => {
      active = false;
      if (typeof cleanup === "function") cleanup();
    };
  }

  return { install };
}
