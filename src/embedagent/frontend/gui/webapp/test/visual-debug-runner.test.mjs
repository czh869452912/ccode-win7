import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const REPO_ROOT = path.resolve(WEBAPP_ROOT, "..", "..", "..", "..", "..");

export async function runVisualDebugRunnerTests() {
  const packageJson = JSON.parse(fs.readFileSync(path.join(WEBAPP_ROOT, "package.json"), "utf8"));
  assert.equal(packageJson.scripts["visual:gui"], "node ../../../../../scripts/gui-visual-debug.mjs");

  const scriptPath = path.join(REPO_ROOT, "scripts", "gui-visual-debug.mjs");
  const runner = await import(pathToFileURL(scriptPath));
  const source = fs.readFileSync(scriptPath, "utf8");
  const expected = [
    "empty", "session", "streaming", "tool", "interaction", "commands",
    "recovery", "narrow", "optional-terminal", "optional-diff",
  ];
  assert.deepEqual(runner.SCENARIOS, expected);
  assert.deepEqual(runner.parseScenarioList("session,tool,session"), ["session", "tool"]);
  assert.deepEqual(runner.parseScenarioList("all"), expected);
  assert.throws(() => runner.parseScenarioList("right-panel"), /Unknown GUI visual scenario/);
  assert.deepEqual(runner.parseViewportList("700x640,520x720"), [
    { name: "700x640", width: 700, height: 640 },
    { name: "520x720", width: 520, height: 720 },
  ]);
  assert.throws(() => runner.parseViewportList("700"), /Invalid viewport/);

  const args = runner.parseVisualDebugArgs([
    "--scenario", "optional-diff", "--workspace", "C:/work/demo", "--port", "54321",
    "--output", "C:/tmp/gui-visual", "--viewports", "900x640,520x720", "--headed",
  ]);
  assert.equal(args.scenario, "optional-diff");
  assert.equal(args.port, 54321);
  assert.equal(args.headlessBrowser, false);
  assert.equal(runner.parseVisualDebugArgs(["--no-build"]).buildWebapp, false);

  for (const contract of [
    "[data-agent-shell]",
    "[data-session-timeline]",
    "[data-session-composer]",
    "[data-permanent-right-panel]",
    "[data-permanent-bottom-drawer]",
    "elementsFromPoint",
    "scrollWidth",
    "loadScenario",
  ]) assert.equal(source.includes(contract), true, contract);
  assert.equal(/right-panel-surface|loadPanelOverflowFixture|loadTerminalSplitFixture/.test(source), false);

  const launch = runner.buildGuiLaunchConfig({
    repoRoot: "C:/repo",
    workspace: "C:/work/demo",
    port: 54321,
    mode: "build",
    baseUrl: "http://127.0.0.1:45678/v1",
    model: "visual-debug-model",
    timeout: 9,
    maxTurns: 3,
    bundleRoot: "C:/bundle",
    appHome: "C:/tmp/gui-app-home",
    python: "C:/python/python.exe",
  });
  assert.equal(launch.command, "C:/python/python.exe");
  assert.deepEqual(launch.args.slice(0, 2), ["-m", "embedagent.frontend.gui.launcher"]);
  assert.equal(launch.args.includes("--workspace"), true);
  assert.equal(launch.env.PYTHONPATH, path.join("C:/repo", "src"));
  assert.equal(launch.env.EMBEDAGENT_BUNDLE_ROOT, "C:/bundle");
  assert.equal(launch.env.EMBEDAGENT_GUI_APP_HOME, "C:/tmp/gui-app-home");

  assert.deepEqual(
    runner.summarizeConsoleMessages([
      { type: "log", text: "ok" },
      { type: "warning", text: "warn" },
      { type: "error", text: "boom" },
    ]).relevant.map((item) => item.type),
    ["warning", "error"],
  );
  assert.equal(
    runner.resolvePython({ repoRoot: "C:/repo", python: "C:/custom/python.exe" }),
    "C:/custom/python.exe",
  );
  assert.equal(
    runner.resolveWebappPackageJson("C:/repo").replace(/\\/g, "/"),
    "C:/repo/src/embedagent/frontend/gui/webapp/package.json",
  );
  await assert.rejects(
    () => runner.waitForProcessStart({
      once: (event, callback) => { if (event === "error") callback(new Error("missing python")); },
    }),
    /missing python/,
  );
}
