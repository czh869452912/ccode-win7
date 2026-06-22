import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const WEBAPP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const REPO_ROOT = path.resolve(WEBAPP_ROOT, "..", "..", "..", "..", "..");

export async function runVisualDebugRunnerTests() {
  const packageJson = JSON.parse(
    fs.readFileSync(path.join(WEBAPP_ROOT, "package.json"), "utf8"),
  );
  assert.equal(
    packageJson.scripts["visual:gui"],
    "node ../../../../../scripts/gui-visual-debug.mjs",
  );

  const runner = await import(pathToFileURL(path.join(REPO_ROOT, "scripts", "gui-visual-debug.mjs")));
  const runnerSource = fs.readFileSync(path.join(REPO_ROOT, "scripts", "gui-visual-debug.mjs"), "utf8");

  assert.deepEqual(runner.parseScenarioList("load,chat"), ["load", "chat"]);
  assert.deepEqual(runner.parseScenarioList("load,file"), ["load", "file"]);
  assert.deepEqual(runner.parseScenarioList("composer"), ["composer"]);
  assert.deepEqual(runner.parseScenarioList("load,composer"), ["load", "composer"]);
  assert.deepEqual(runner.parseScenarioList("palette"), ["palette"]);
  assert.deepEqual(runner.parseScenarioList("load,palette"), ["load", "palette"]);
  assert.deepEqual(runner.parseScenarioList("thread"), ["thread"]);
  assert.deepEqual(runner.parseScenarioList("timeline,interaction"), ["timeline", "interaction"]);
  assert.deepEqual(runner.parseScenarioList("all"), ["app", "load", "chat", "composer", "palette", "preview", "diff", "file", "terminal", "responsive", "thread", "timeline", "interaction", "panel-overflow", "terminal-split", "timeline-context"]);
  assert.deepEqual(runner.parseScenarioList("preview"), ["preview"]);
  assert.deepEqual(runner.parseScenarioList("load,preview"), ["load", "preview"]);
  assert.deepEqual(runner.parseScenarioList("app"), ["app"]);
  assert.deepEqual(runner.parseScenarioList("load,app"), ["app", "load"]);
  assert.throws(() => runner.parseScenarioList("load,unknown"), /Unknown GUI visual scenario/);
  assert.deepEqual(runner.parseViewportList("700x640,520x720"), [
    { name: "700x640", width: 700, height: 640 },
    { name: "520x720", width: 520, height: 720 },
  ]);
  assert.throws(() => runner.parseViewportList("700"), /Invalid viewport/);

  const args = runner.parseVisualDebugArgs([
    "--scenario",
    "diff",
    "--workspace",
    "C:/work/demo",
    "--port",
    "54321",
    "--bundle-root",
    "C:/bundle",
    "--output",
    "C:/tmp/gui-visual",
    "--viewports",
    "900x640,700x640",
    "--headed",
  ]);
  assert.equal(args.scenario, "diff");
  assert.equal(args.workspace, "C:/work/demo");
  assert.equal(args.port, 54321);
  assert.equal(args.bundleRoot, "C:/bundle");
  assert.equal(args.output, "C:/tmp/gui-visual");
  assert.equal(args.viewports, "900x640,700x640");
  assert.equal(args.headlessBrowser, false);
  assert.equal(args.buildWebapp, true);
  assert.equal(runnerSource.includes('"cmd.exe"'), true);
  assert.equal(runnerSource.includes('"npm.cmd"'), false);
  assert.equal(runnerSource.includes("visual_debug=1"), true);
  assert.equal(runnerSource.includes("__EMBEDAGENT_VISUAL_DEBUG__"), true);
  assert.equal(runnerSource.includes("resetScenarioViewport"), true);
  assert.equal(runnerSource.includes("await resetScenarioViewport(page);"), true);
  assert.equal(runnerSource.includes(".right-panel-surface-tab"), true);
  assert.equal(runnerSource.includes("right-panel-surface-tab--diff"), true);
  assert.equal(runnerSource.includes("runFileScenario"), true);
  assert.equal(runnerSource.includes("right-panel-file-surface"), true);
  assert.equal(runnerSource.includes("right-panel-surface-tab--file"), true);
  assert.equal(runnerSource.includes("file-preview-breadcrumbs"), true);
  assert.equal(runnerSource.includes("file-preview-mode-toggle"), true);
  assert.equal(runnerSource.includes("filePreviewChromeState"), true);
  assert.equal(runnerSource.includes("file-preview-open-action"), true);
  assert.equal(runnerSource.includes("file-preview-gutter"), true);
  assert.equal(runnerSource.includes("file-preview-markdown"), true);
  assert.equal(runnerSource.includes("loadFilePreviewRevealFixture"), true);
  assert.equal(runnerSource.includes("data-file-link-reveal"), true);
  assert.equal(runnerSource.includes("diffChromeState"), true);
  assert.equal(runnerSource.includes("diff-mode-toggle--split"), true);
  assert.equal(runnerSource.includes('"preview"'), true);
  assert.equal(runnerSource.includes("runPreviewScenario"), true);
  assert.equal(runnerSource.includes("right-panel-preview-surface"), true);
  assert.equal(runnerSource.includes("preview-url-input"), true);
  assert.equal(runnerSource.includes("preview-local-server-card"), true);
  assert.equal(runnerSource.includes("preview-open-external-action"), true);
  assert.equal(runnerSource.includes("preview-refresh-action"), true);
  assert.equal(runnerSource.includes("Preview unavailable"), true);
  assert.equal(runnerSource.includes("runTerminalScenario"), true);
  assert.equal(runnerSource.includes("right-panel-terminal-surface"), true);
  assert.equal(runnerSource.includes("right-panel-tab--diff"), false);
  assert.equal(runnerSource.includes("runTimelineScenario"), true);
  assert.equal(runnerSource.includes("runInteractionScenario"), true);
  assert.equal(runnerSource.includes("runPanelOverflowScenario"), true);
  assert.equal(runnerSource.includes("runTerminalSplitScenario"), true);
  assert.equal(runnerSource.includes("runTimelineContextScenario"), true);
  assert.equal(runnerSource.includes("runThreadScenario"), true);
  assert.equal(runnerSource.includes("loadTimelineFixture"), true);
  assert.equal(runnerSource.includes("timeline-reasoning-row"), true);
  assert.equal(runnerSource.includes("timeline-thinking-row"), true);
  assert.equal(runnerSource.includes("timeline-review-result-row"), true);
  assert.equal(runnerSource.includes("timeline-tool-file-link--src/parser.c"), true);
  assert.equal(runnerSource.includes("timelineLinkRevealState"), true);
  assert.equal(runnerSource.includes("loadInteractionFixture"), true);
  assert.equal(runnerSource.includes("loadPanelOverflowFixture"), true);
  assert.equal(runnerSource.includes("loadTerminalSplitFixture"), true);
  assert.equal(runnerSource.includes("loadTimelineContextFixture"), true);
  assert.equal(runnerSource.includes("loadThreadLifecycleFixture"), true);
  assert.equal(runnerSource.includes("loadSourceControlFixture"), true);
  assert.equal(runnerSource.includes("runComposerScenario"), true);
  assert.equal(runnerSource.includes("loadComposerFileTreeFixture"), true);
  assert.equal(runnerSource.includes("composer-command-menu"), true);
  assert.equal(runnerSource.includes("composer-primary-action"), true);
  assert.equal(runnerSource.includes("@src/parser.c"), true);
  assert.equal(runnerSource.includes("branch-toolbar"), true);
  assert.equal(runnerSource.includes('"palette"'), true);
  assert.equal(runnerSource.includes("runPaletteScenario"), true);
  assert.equal(runnerSource.includes("command-palette-group--commands"), true);
  assert.equal(runnerSource.includes("command-palette-submenu--surface"), true);
  assert.equal(runnerSource.includes("command-palette-command--surface.diff"), true);
  assert.equal(runnerSource.includes("command-palette-session--"), true);
  assert.equal(runnerSource.includes("command-palette-workspace--"), true);

  const noBuildArgs = runner.parseVisualDebugArgs(["--no-build"]);
  assert.equal(noBuildArgs.buildWebapp, false);

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
  assert.equal(launch.args.includes("--headless"), true);
  assert.equal(launch.args.includes("--workspace"), true);
  assert.equal(launch.args.includes("C:/work/demo"), true);
  assert.equal(launch.args.includes("--port"), true);
  assert.equal(launch.args.includes("54321"), true);
  assert.equal(launch.env.PYTHONPATH, path.join("C:/repo", "src"));
  assert.equal(launch.env.EMBEDAGENT_BUNDLE_ROOT, "C:/bundle");
  assert.equal(launch.env.EMBEDAGENT_GUI_APP_HOME, "C:/tmp/gui-app-home");

  const appLaunch = runner.buildGuiLaunchConfig({
    repoRoot: "C:/repo",
    workspace: "",
    port: 54321,
    mode: "build",
    baseUrl: "http://127.0.0.1:45678/v1",
    model: "visual-debug-model",
    timeout: 9,
    maxTurns: 3,
    bundleRoot: "",
    python: "C:/python/python.exe",
  });
  assert.equal(appLaunch.args.includes("--workspace"), false);
  assert.equal(runnerSource.includes("EMBEDAGENT_GUI_APP_HOME"), true);

  const summary = runner.summarizeConsoleMessages([
    { type: "log", text: "hello" },
    { type: "warning", text: "layout warning" },
    { type: "error", text: "boom" },
  ]);
  assert.deepEqual(summary.relevant.map((entry) => entry.type), ["warning", "error"]);

  assert.equal(
    runner.resolvePython({
      repoRoot: "C:/repo",
      python: "C:/custom/python.exe",
      existsSync: () => false,
    }),
    "C:/custom/python.exe",
  );
  assert.equal(
    runner.resolvePython({
      repoRoot: "C:/repo/.worktrees/feature",
      existsSync: (candidate) => candidate.replace(/\\/g, "/") === "C:/repo/.venv/Scripts/python.exe",
    }).replace(/\\/g, "/"),
    "C:/repo/.venv/Scripts/python.exe",
  );
  assert.equal(
    runner.resolveWebappPackageJson("C:/repo").replace(/\\/g, "/"),
    "C:/repo/src/embedagent/frontend/gui/webapp/package.json",
  );
  assert.equal(
    runner.resolveGitExecutable({
      bundleRoot: "C:/bundle",
      existsSync: (candidate) => candidate.replace(/\\/g, "/") === "C:/bundle/bin/git/cmd/git.exe",
    }).replace(/\\/g, "/"),
    "C:/bundle/bin/git/cmd/git.exe",
  );
  assert.equal(
    runner.resolveGitExecutable({
      bundleRoot: "C:/missing",
      existsSync: () => false,
    }),
    "git",
  );
  await assert.rejects(
    () => runner.waitForProcessStart({
      once: (event, callback) => {
        if (event === "error") callback(new Error("missing python"));
      },
      pid: undefined,
    }),
    /Failed to start GUI process: missing python/,
  );
}
