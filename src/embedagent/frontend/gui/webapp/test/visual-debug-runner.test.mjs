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

  assert.deepEqual(runner.parseScenarioList("load,chat"), ["load", "chat"]);
  assert.deepEqual(runner.parseScenarioList("all"), ["load", "chat", "diff"]);
  assert.throws(() => runner.parseScenarioList("load,unknown"), /Unknown GUI visual scenario/);

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
    "--headed",
  ]);
  assert.equal(args.scenario, "diff");
  assert.equal(args.workspace, "C:/work/demo");
  assert.equal(args.port, 54321);
  assert.equal(args.bundleRoot, "C:/bundle");
  assert.equal(args.output, "C:/tmp/gui-visual");
  assert.equal(args.headlessBrowser, false);

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
