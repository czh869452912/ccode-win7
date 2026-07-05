import { installVisualDebugFixtures } from "./visual-debug-fixtures.js";

function readLocationSearch(windowObject) {
  return windowObject?.location?.search || "";
}

export function createVisualDebugController({
  windowObject,
  getLocationSearch,
  dispatch,
  openDiffFixture,
  getCurrentMode,
  installFixtures,
} = {}) {
  const installFixtureHook =
    typeof installFixtures === "function" ? installFixtures : installVisualDebugFixtures;
  const readSearch =
    typeof getLocationSearch === "function"
      ? getLocationSearch
      : () => readLocationSearch(windowObject);
  const readMode =
    typeof getCurrentMode === "function" ? getCurrentMode : () => "explore";

  function install() {
    return installFixtureHook({
      windowObject,
      locationSearch: readSearch(),
      dispatch,
      openDiffFixture,
      currentMode: readMode() || "explore",
    });
  }

  return { install };
}
