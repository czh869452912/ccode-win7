#!/usr/bin/env node
import fs from "node:fs";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";

export const SCENARIOS = ["load", "chat", "diff"];

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_REPO_ROOT = path.resolve(SCRIPT_DIR, "..");

function boolEnv(name) {
  const value = String(process.env[name] || "").trim().toLowerCase();
  return value === "1" || value === "true" || value === "yes";
}

export function parseScenarioList(value = "load") {
  const raw = String(value || "load").trim().toLowerCase();
  const scenarios = raw === "all"
    ? SCENARIOS
    : raw.split(",").map((item) => item.trim()).filter(Boolean);
  const unknown = scenarios.filter((item) => !SCENARIOS.includes(item));
  if (unknown.length > 0) {
    throw new Error(`Unknown GUI visual scenario: ${unknown.join(", ")}`);
  }
  return Array.from(new Set(scenarios));
}

function readOption(argv, index) {
  if (index + 1 >= argv.length || argv[index + 1].startsWith("--")) {
    throw new Error(`Missing value for ${argv[index]}`);
  }
  return argv[index + 1];
}

export function parseVisualDebugArgs(argv = process.argv.slice(2)) {
  const options = {
    scenario: "load",
    workspace: "",
    output: path.join(os.tmpdir(), `embedagent-gui-visual-${Date.now()}`),
    port: 0,
    modelPort: 0,
    mode: "build",
    model: "visual-debug-model",
    timeout: 12,
    maxTurns: 4,
    bundleRoot: "",
    python: "",
    headlessBrowser: true,
    keepServer: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--scenario") {
      options.scenario = readOption(argv, index);
      index += 1;
    } else if (arg === "--workspace") {
      options.workspace = readOption(argv, index);
      index += 1;
    } else if (arg === "--output") {
      options.output = readOption(argv, index);
      index += 1;
    } else if (arg === "--port") {
      options.port = Number(readOption(argv, index));
      index += 1;
    } else if (arg === "--model-port") {
      options.modelPort = Number(readOption(argv, index));
      index += 1;
    } else if (arg === "--mode") {
      options.mode = readOption(argv, index);
      index += 1;
    } else if (arg === "--model") {
      options.model = readOption(argv, index);
      index += 1;
    } else if (arg === "--timeout") {
      options.timeout = Number(readOption(argv, index));
      index += 1;
    } else if (arg === "--max-turns") {
      options.maxTurns = Number(readOption(argv, index));
      index += 1;
    } else if (arg === "--bundle-root") {
      options.bundleRoot = readOption(argv, index);
      index += 1;
    } else if (arg === "--python") {
      options.python = readOption(argv, index);
      index += 1;
    } else if (arg === "--headed") {
      options.headlessBrowser = false;
    } else if (arg === "--keep-server") {
      options.keepServer = true;
    } else if (arg === "--help" || arg === "-h") {
      options.help = true;
    } else {
      throw new Error(`Unknown option: ${arg}`);
    }
  }

  if (!Number.isFinite(options.port) || options.port < 0) {
    throw new Error("--port must be a non-negative number");
  }
  if (!Number.isFinite(options.modelPort) || options.modelPort < 0) {
    throw new Error("--model-port must be a non-negative number");
  }
  if (!Number.isFinite(options.timeout) || options.timeout <= 0) {
    throw new Error("--timeout must be a positive number");
  }
  if (!Number.isFinite(options.maxTurns) || options.maxTurns <= 0) {
    throw new Error("--max-turns must be a positive number");
  }
  parseScenarioList(options.scenario);
  return options;
}

export function buildGuiLaunchConfig({
  repoRoot,
  workspace,
  port,
  mode = "build",
  baseUrl,
  model = "visual-debug-model",
  timeout = 12,
  maxTurns = 4,
  bundleRoot = "",
  python = "",
} = {}) {
  const command = resolvePython({ repoRoot, python });
  const env = {
    ...process.env,
    PYTHONPATH: path.join(repoRoot, "src"),
  };
  if (bundleRoot) {
    env.EMBEDAGENT_BUNDLE_ROOT = bundleRoot;
  }
  return {
    command,
    args: [
      "-m",
      "embedagent.frontend.gui.launcher",
      "--workspace",
      workspace,
      "--mode",
      mode,
      "--model",
      model,
      "--base-url",
      baseUrl,
      "--port",
      String(port),
      "--timeout",
      String(timeout),
      "--max-turns",
      String(maxTurns),
      "--headless",
      "--auto-close-seconds",
      "300",
    ],
    env,
  };
}

export function resolvePython({ repoRoot, python = "", existsSync = fs.existsSync } = {}) {
  if (python) return python;
  const candidates = [
    path.join(repoRoot, ".venv", "Scripts", "python.exe"),
  ];
  const worktreesIndex = path.normalize(repoRoot).split(path.sep).lastIndexOf(".worktrees");
  if (worktreesIndex > 0) {
    const parts = path.normalize(repoRoot).split(path.sep).slice(0, worktreesIndex);
    candidates.push(path.join(parts.join(path.sep), ".venv", "Scripts", "python.exe"));
  }
  for (const candidate of candidates) {
    if (existsSync(candidate)) return candidate;
  }
  return "python";
}

export function resolveWebappPackageJson(repoRoot) {
  return path.join(repoRoot, "src", "embedagent", "frontend", "gui", "webapp", "package.json");
}

export function summarizeConsoleMessages(messages = []) {
  const relevant = messages
    .map((entry) => ({
      type: String(entry.type || entry.level || ""),
      text: String(entry.text || entry.message || ""),
      location: entry.location || null,
    }))
    .filter((entry) => entry.type === "error" || entry.type === "warning" || entry.type === "warn");
  return { count: relevant.length, relevant };
}

async function freePort() {
  return await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() => resolve(Number(address.port)));
    });
  });
}

async function waitForHttp(url, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  let lastError = null;
  while (Date.now() < deadline) {
    try {
      const status = await new Promise((resolve, reject) => {
        const request = http.get(url, (response) => {
          response.resume();
          response.on("end", () => resolve(response.statusCode));
        });
        request.setTimeout(2000, () => request.destroy(new Error("timeout")));
        request.on("error", reject);
      });
      if (status === 200) return;
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Timed out waiting for ${url}: ${lastError ? lastError.message : "no response"}`);
}

function ensureDir(target) {
  fs.mkdirSync(target, { recursive: true });
}

function createWorkspace(targetRoot) {
  ensureDir(targetRoot);
  const readme = path.join(targetRoot, "README.md");
  if (!fs.existsSync(readme)) {
    fs.writeFileSync(readme, "# Visual Debug Workspace\n\nFixture file for GUI visual debugging.\n", "utf8");
  }
  return targetRoot;
}

export function resolveGitExecutable({ bundleRoot = "", existsSync = fs.existsSync } = {}) {
  const candidates = [];
  if (bundleRoot) {
    candidates.push(
      path.join(bundleRoot, "bin", "git", "cmd", "git.exe"),
      path.join(bundleRoot, "bin", "git", "bin", "git.exe"),
    );
  }
  for (const candidate of candidates) {
    if (existsSync(candidate)) return candidate;
  }
  return "git";
}

function createDiffWorkspace(targetRoot, gitExecutable = "git") {
  createWorkspace(targetRoot);
  const demo = path.join(targetRoot, "demo.c");
  fs.writeFileSync(demo, "int main(void) {\n    return 0;\n}\n", "utf8");
  if (!fs.existsSync(path.join(targetRoot, ".git"))) {
    const init = spawnSync(gitExecutable, ["init"], { cwd: targetRoot, encoding: "utf8" });
    if (init.status !== 0) {
      throw new Error(`git init failed: ${init.stderr || init.stdout}`);
    }
    spawnSync(gitExecutable, ["config", "user.email", "codex@example.test"], { cwd: targetRoot });
    spawnSync(gitExecutable, ["config", "user.name", "Codex"], { cwd: targetRoot });
    const add = spawnSync(gitExecutable, ["add", "demo.c"], { cwd: targetRoot, encoding: "utf8" });
    if (add.status !== 0) {
      throw new Error(`git add failed: ${add.stderr || add.stdout}`);
    }
    const commit = spawnSync(gitExecutable, ["commit", "-m", "initial"], { cwd: targetRoot, encoding: "utf8" });
    if (commit.status !== 0) {
      throw new Error(`git commit failed: ${commit.stderr || commit.stdout}`);
    }
  }
  fs.writeFileSync(demo, "int main(void) {\n    return 1;\n}\n", "utf8");
  return targetRoot;
}

function startFakeModelServer(port) {
  const server = http.createServer((request, response) => {
    if (request.method !== "POST" || request.url.replace(/\/$/, "") !== "/v1/chat/completions") {
      response.writeHead(404);
      response.end();
      return;
    }
    let raw = "";
    request.setEncoding("utf8");
    request.on("data", (chunk) => {
      raw += chunk;
    });
    request.on("end", () => {
      const payload = JSON.parse(raw || "{}");
      const messages = Array.isArray(payload.messages) ? payload.messages : [];
      const userText = [...messages].reverse().find((item) => item.role === "user")?.content || "";
      const reply = String(userText).includes("/diff")
        ? "Diff command completed."
        : "GUI visual debug reply";
      if (payload.stream) {
        response.writeHead(200, {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
        });
        response.write(`data: ${JSON.stringify({ choices: [{ delta: { content: reply }, finish_reason: null }] })}\n\n`);
        response.write(`data: ${JSON.stringify({ choices: [{ delta: {}, finish_reason: "stop" }] })}\n\n`);
        response.write("data: [DONE]\n\n");
        response.end();
        return;
      }
      const body = JSON.stringify({
        choices: [
          {
            message: { content: reply },
            finish_reason: "stop",
          },
        ],
      });
      response.writeHead(200, { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) });
      response.end(body);
    });
  });
  return new Promise((resolve, reject) => {
    server.on("error", reject);
    server.listen(port, "127.0.0.1", () => resolve(server));
  });
}

function startGuiProcess(config, outputDir) {
  const stdoutPath = path.join(outputDir, "gui.stdout.log");
  const stderrPath = path.join(outputDir, "gui.stderr.log");
  const stdout = fs.openSync(stdoutPath, "w");
  const stderr = fs.openSync(stderrPath, "w");
  const child = spawn(config.command, config.args, {
    cwd: DEFAULT_REPO_ROOT,
    env: config.env,
    stdio: ["ignore", stdout, stderr],
    windowsHide: true,
  });
  child.stdoutPath = stdoutPath;
  child.stderrPath = stderrPath;
  return child;
}

export async function waitForProcessStart(child) {
  if (child.pid) return child.pid;
  return await new Promise((resolve, reject) => {
    child.once("spawn", () => resolve(child.pid));
    child.once("error", (error) => {
      reject(new Error(`Failed to start GUI process: ${error.message}`));
    });
  });
}

async function captureScenario({ page, scenario, outputDir }) {
  const screenshotPath = path.join(outputDir, `${scenario}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: false });
  return screenshotPath;
}

async function assertNoOverlap(page) {
  return await page.evaluate(() => {
    const rects = Array.from(document.querySelectorAll(".right-panel-tab")).map((el) => {
      const rect = el.getBoundingClientRect();
      return { text: el.textContent.trim(), x: rect.x, width: rect.width };
    });
    return rects.every((item, index) => index === 0 || item.x >= rects[index - 1].x + rects[index - 1].width - 0.5);
  });
}

async function runLoadScenario(page) {
  await page.waitForSelector('[data-testid="workbench-layout"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="composer-input"]', { timeout: 10000 });
  const timelineRows = await page.locator("[data-row-kind]").count();
  const noOverlap = await assertNoOverlap(page);
  if (!noOverlap) throw new Error("Right panel tabs overlap in load scenario");
  return { timelineRows, rightTabsDoNotOverlap: noOverlap };
}

async function runChatScenario(page) {
  await page.fill('[data-testid="composer-input"]', "visual debug chat");
  await page.click('[data-testid="send-button"]');
  await page.waitForSelector('[data-testid="timeline-user-message"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="timeline-assistant-message"]', { timeout: 15000 });
  await page.waitForFunction(() => {
    const status = document.querySelector('[data-testid="workbench-header"] .status-label');
    return status && status.textContent.trim() === "idle";
  }, null, { timeout: 15000 });
  const assistantText = await page.locator('[data-testid="timeline-assistant-message"]').last().innerText();
  if (assistantText !== "GUI visual debug reply") {
    throw new Error(`Expected one assistant reply, got: ${assistantText}`);
  }
  return { assistantText };
}

async function runDiffScenario(page) {
  await page.fill('[data-testid="composer-input"]', "/diff");
  await page.click('[data-testid="send-button"]');
  await page.waitForSelector('[data-testid="diff-panel"]', { timeout: 15000 });
  await page.waitForSelector('[data-testid="diff-file--demo.c"]', { timeout: 15000 });
  const panelText = await page.locator('[data-testid="diff-panel"]').innerText();
  const activeTab = await page.locator('[data-testid="right-panel-tab--diff"]').getAttribute("aria-selected");
  const noOverlap = await assertNoOverlap(page);
  if (activeTab !== "true") throw new Error("Diff tab did not become active");
  if (!panelText.includes("demo.c") || !panelText.includes("return 1")) {
    throw new Error("Diff panel did not show the expected demo.c change");
  }
  if (!noOverlap) throw new Error("Right panel tabs overlap in diff scenario");
  return {
    activeTab: activeTab === "true",
    hasDemoDiff: panelText.includes("demo.c") && panelText.includes("return 1"),
    rightTabsDoNotOverlap: noOverlap,
  };
}

async function runScenarios(options, repoRoot, outputDir) {
  const requireFromWebapp = createRequire(pathToFileURL(resolveWebappPackageJson(repoRoot)));
  const { chromium } = requireFromWebapp("playwright");
  const browser = await chromium.launch({ headless: options.headlessBrowser });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  const consoleMessages = [];
  page.on("console", (message) => {
    consoleMessages.push({
      type: message.type(),
      text: message.text(),
      location: message.location(),
    });
  });
  const results = {};
  try {
    const url = `http://127.0.0.1:${options.port}/`;
    await page.goto(url, { waitUntil: "domcontentloaded" });
    const scenarios = parseScenarioList(options.scenario);
    for (const scenario of scenarios) {
      if (scenario === "load") {
        results.load = await runLoadScenario(page);
      } else if (scenario === "chat") {
        results.chat = await runChatScenario(page);
      } else if (scenario === "diff") {
        results.diff = await runDiffScenario(page);
      }
      results[scenario].screenshot = await captureScenario({ page, scenario, outputDir });
    }
  } finally {
    await browser.close();
  }
  return {
    results,
    console: summarizeConsoleMessages(consoleMessages),
    repoRoot,
  };
}

function printHelp() {
  console.log(`Usage: node scripts/gui-visual-debug.mjs [options]

Options:
  --scenario load|chat|diff|all   Scenario list to run (default: load)
  --workspace PATH                Existing workspace; temp workspace by default
  --output PATH                   Output dir for screenshots and summary JSON
  --bundle-root PATH              Optional offline bundle root for bundled tools
  --port N                        GUI port; 0 picks a free port
  --model-port N                  Fake model port; 0 picks a free port
  --headed                        Show the Playwright browser
  --keep-server                   Leave GUI server running after the run
`);
}

export async function runVisualDebug(options = parseVisualDebugArgs()) {
  if (options.help) {
    printHelp();
    return { help: true };
  }
  const repoRoot = DEFAULT_REPO_ROOT;
  const outputDir = path.resolve(options.output);
  ensureDir(outputDir);
  const workspace = path.resolve(
    options.workspace || path.join(os.tmpdir(), `embedagent-gui-visual-workspace-${Date.now()}`),
  );
  if (parseScenarioList(options.scenario).includes("diff")) {
    createDiffWorkspace(workspace, resolveGitExecutable({ bundleRoot: options.bundleRoot }));
  } else {
    createWorkspace(workspace);
  }

  const port = options.port || await freePort();
  const modelPort = options.modelPort || await freePort();
  const modelServer = await startFakeModelServer(modelPort);
  const launch = buildGuiLaunchConfig({
    repoRoot,
    workspace,
    port,
    mode: options.mode,
    baseUrl: `http://127.0.0.1:${modelPort}/v1`,
    model: options.model,
    timeout: options.timeout,
    maxTurns: options.maxTurns,
    bundleRoot: options.bundleRoot,
    python: options.python,
  });
  const child = startGuiProcess(launch, outputDir);
  await waitForProcessStart(child);
  const summary = {
    url: `http://127.0.0.1:${port}/`,
    workspace,
    outputDir,
    scenarios: parseScenarioList(options.scenario),
    screenshots: [],
    console: { count: 0, relevant: [] },
    guiLogs: {
      stdout: child.stdoutPath,
      stderr: child.stderrPath,
    },
  };
  try {
    await waitForHttp(summary.url, 20000);
    const run = await runScenarios({ ...options, port }, repoRoot, outputDir);
    Object.assign(summary, run, {
      screenshots: Object.values(run.results).map((result) => result.screenshot),
    });
    fs.writeFileSync(path.join(outputDir, "summary.json"), JSON.stringify(summary, null, 2), "utf8");
    if (summary.console.count > 0) {
      throw new Error(`GUI visual debug saw ${summary.console.count} console warning/error messages`);
    }
    return summary;
  } finally {
    modelServer.close();
    if (!options.keepServer) {
      child.kill();
    }
  }
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  runVisualDebug()
    .then((summary) => {
      if (!summary.help) {
        console.log(JSON.stringify(summary, null, 2));
      }
    })
    .catch((error) => {
      console.error(error && error.stack ? error.stack : String(error));
      process.exitCode = 1;
    });
}
