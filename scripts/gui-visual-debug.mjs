#!/usr/bin/env node
import assert from "node:assert/strict";
import fs from "node:fs";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { spawn, spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

export const SCENARIOS = Object.freeze([
  "empty",
  "session",
  "streaming",
  "tool",
  "interaction",
  "commands",
  "recovery",
  "narrow",
  "optional-terminal",
  "optional-diff",
]);

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_REPO_ROOT = path.resolve(SCRIPT_DIR, "..");

export function parseScenarioList(value = "empty") {
  const requested = String(value || "empty").trim().toLowerCase();
  const scenarios = requested === "all"
    ? [...SCENARIOS]
    : requested.split(",").map((item) => item.trim()).filter(Boolean);
  const unknown = scenarios.filter((item) => !SCENARIOS.includes(item));
  if (unknown.length) throw new Error(`Unknown GUI visual scenario: ${unknown.join(", ")}`);
  return Array.from(new Set(scenarios));
}

export function parseViewportList(value = "1280x720,900x640,700x640,520x720") {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const match = item.match(/^(\d+)x(\d+)$/i);
      if (!match) throw new Error(`Invalid viewport: ${item}`);
      const width = Number(match[1]);
      const height = Number(match[2]);
      if (width <= 0 || height <= 0) throw new Error(`Invalid viewport: ${item}`);
      return { name: `${width}x${height}`, width, height };
    });
}

function optionValue(argv, index) {
  if (!argv[index + 1] || argv[index + 1].startsWith("--")) {
    throw new Error(`Missing value for ${argv[index]}`);
  }
  return argv[index + 1];
}

export function parseVisualDebugArgs(argv = process.argv.slice(2)) {
  const options = {
    scenario: "empty",
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
    viewports: "1280x720,900x640,700x640,520x720",
    buildWebapp: true,
  };
  const valued = new Map([
    ["--scenario", "scenario"], ["--workspace", "workspace"], ["--output", "output"],
    ["--mode", "mode"], ["--model", "model"], ["--bundle-root", "bundleRoot"],
    ["--python", "python"], ["--viewports", "viewports"],
  ]);
  const numeric = new Map([
    ["--port", "port"], ["--model-port", "modelPort"], ["--timeout", "timeout"],
    ["--max-turns", "maxTurns"],
  ]);
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (valued.has(arg)) {
      options[valued.get(arg)] = optionValue(argv, index);
      index += 1;
    } else if (numeric.has(arg)) {
      options[numeric.get(arg)] = Number(optionValue(argv, index));
      index += 1;
    } else if (arg === "--headed") options.headlessBrowser = false;
    else if (arg === "--keep-server") options.keepServer = true;
    else if (arg === "--no-build") options.buildWebapp = false;
    else if (arg === "--help" || arg === "-h") options.help = true;
    else throw new Error(`Unknown option: ${arg}`);
  }
  if (options.port < 0 || options.modelPort < 0) throw new Error("ports must be non-negative");
  if (options.timeout <= 0 || options.maxTurns <= 0) throw new Error("limits must be positive");
  parseScenarioList(options.scenario);
  parseViewportList(options.viewports);
  return options;
}

export function resolveWebappPackageJson(repoRoot) {
  return path.join(repoRoot, "src", "embedagent", "frontend", "gui", "webapp", "package.json");
}

export function resolvePython({ repoRoot, python = "", existsSync = fs.existsSync } = {}) {
  if (python) return python;
  const candidates = [path.join(repoRoot, ".venv", "Scripts", "python.exe")];
  const parts = path.normalize(repoRoot).split(path.sep);
  const worktreeIndex = parts.lastIndexOf(".worktrees");
  if (worktreeIndex > 0) {
    candidates.push(path.join(parts.slice(0, worktreeIndex).join(path.sep), ".venv", "Scripts", "python.exe"));
  }
  return candidates.find((candidate) => existsSync(candidate)) || "python";
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
  appHome = "",
  python = "",
} = {}) {
  const env = {
    ...process.env,
    PYTHONPATH: path.join(repoRoot, "src"),
    EMBEDAGENT_ALLOW_SYSTEM_TOOL_FALLBACK: "1",
  };
  if (bundleRoot) env.EMBEDAGENT_BUNDLE_ROOT = bundleRoot;
  if (appHome) env.EMBEDAGENT_GUI_APP_HOME = appHome;
  const args = ["-m", "embedagent.frontend.gui.launcher"];
  if (workspace) args.push("--workspace", workspace);
  args.push(
    "--mode", mode,
    "--model", model,
    "--base-url", baseUrl,
    "--port", String(port),
    "--timeout", String(timeout),
    "--max-turns", String(maxTurns),
    "--headless",
    "--auto-close-seconds", "300",
  );
  return { command: resolvePython({ repoRoot, python }), args, env };
}

export function summarizeConsoleMessages(messages = []) {
  const relevant = messages.filter((entry) => ["error", "warning", "warn"].includes(entry.type));
  return { count: relevant.length, relevant };
}

function buildWebapp(repoRoot) {
  const webappRoot = path.dirname(resolveWebappPackageJson(repoRoot));
  const result = spawnSync(process.platform === "win32" ? "cmd.exe" : "npm", process.platform === "win32"
    ? ["/d", "/s", "/c", "npm run build"]
    : ["run", "build"], { cwd: webappRoot, stdio: "inherit" });
  if (result.error || result.status !== 0) throw new Error("GUI webapp build failed");
}

async function freePort() {
  return await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const port = Number(server.address().port);
      server.close(() => resolve(port));
    });
  });
}

async function waitForHttp(url, timeoutMs = 20000) {
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
  throw new Error(`Timed out waiting for ${url}: ${lastError?.message || "no response"}`);
}

function createWorkspace(target) {
  fs.mkdirSync(path.join(target, "src"), { recursive: true });
  fs.writeFileSync(path.join(target, "README.md"), "# Visual Debug Workspace\n", "utf8");
  fs.writeFileSync(path.join(target, "src", "parser.c"), "int parse(void) { return 0; }\n", "utf8");
  return target;
}

function startFakeModelServer(port) {
  const server = http.createServer((request, response) => {
    if (request.method !== "POST") {
      response.writeHead(404).end();
      return;
    }
    request.resume();
    request.on("end", () => {
      const body = JSON.stringify({ choices: [{ message: { content: "Visual debug reply" }, finish_reason: "stop" }] });
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(body);
    });
  });
  return new Promise((resolve, reject) => {
    server.on("error", reject);
    server.listen(port, "127.0.0.1", () => resolve(server));
  });
}

function startGui(config, outputDir) {
  const stdoutPath = path.join(outputDir, "gui.stdout.log");
  const stderrPath = path.join(outputDir, "gui.stderr.log");
  const child = spawn(config.command, config.args, {
    cwd: DEFAULT_REPO_ROOT,
    env: config.env,
    stdio: ["ignore", fs.openSync(stdoutPath, "w"), fs.openSync(stderrPath, "w")],
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
    child.once("error", reject);
  });
}

async function assertShell(page, viewport) {
  const metrics = await page.evaluate(() => {
    const shell = document.querySelector("[data-agent-shell]");
    const timeline = document.querySelector("[data-session-timeline]");
    const composer = document.querySelector("[data-session-composer]");
    const dialog = document.querySelector("[role='dialog']");
    const clickableRoot = dialog || document.querySelector("[data-session-composer]");
    const clickable = Array.from(clickableRoot?.querySelectorAll("button:not([disabled])") || [])
      .map((element) => {
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        if (style.display === "none" || style.visibility === "hidden") return null;
        const visibleRect = {
          left: Math.max(0, rect.left),
          top: Math.max(0, rect.top),
          right: Math.min(innerWidth, rect.right),
          bottom: Math.min(innerHeight, rect.bottom),
        };
        for (let parent = element.parentElement; parent; parent = parent.parentElement) {
          const parentStyle = getComputedStyle(parent);
          if (![parentStyle.overflow, parentStyle.overflowX, parentStyle.overflowY].some((value) => value !== "visible")) {
            continue;
          }
          const parentRect = parent.getBoundingClientRect();
          visibleRect.left = Math.max(visibleRect.left, parentRect.left);
          visibleRect.top = Math.max(visibleRect.top, parentRect.top);
          visibleRect.right = Math.min(visibleRect.right, parentRect.right);
          visibleRect.bottom = Math.min(visibleRect.bottom, parentRect.bottom);
        }
        if (visibleRect.right - visibleRect.left < 2 || visibleRect.bottom - visibleRect.top < 2) return null;
        const x = (visibleRect.left + visibleRect.right) / 2;
        const y = (visibleRect.top + visibleRect.bottom) / 2;
        const top = document.elementsFromPoint(x, y)[0];
        return {
          label: element.getAttribute("aria-label") || element.textContent?.trim() || element.tagName,
          hit: top === element || element.contains(top),
        };
      })
      .filter(Boolean);
    return {
      shellVisible: Boolean(shell && shell.getBoundingClientRect().width > 0),
      timelineWidth: timeline?.getBoundingClientRect().width || 0,
      composerWidth: composer?.getBoundingClientRect().width || 0,
      permanentPanels: document.querySelectorAll(
        "[data-permanent-right-panel], [data-permanent-bottom-drawer]",
      ).length,
      documentWidth: document.documentElement.scrollWidth,
      viewportWidth: document.documentElement.clientWidth,
      clickable,
    };
  });
  assert.equal(metrics.shellVisible, true);
  assert.equal(metrics.timelineWidth > 0, true);
  assert.equal(metrics.composerWidth > 0, true);
  assert.equal(metrics.permanentPanels, 0);
  assert.equal(metrics.documentWidth <= metrics.viewportWidth + 1, true);
  if (viewport.width === 520) {
    assert.equal(metrics.clickable.length > 0, true);
    assert.deepEqual(
      metrics.clickable.filter((item) => !item.hit),
      [],
    );
  }
  return metrics;
}

async function runScenarios(options, repoRoot, outputDir) {
  const requireFromWebapp = createRequire(pathToFileURL(resolveWebappPackageJson(repoRoot)));
  const { chromium } = requireFromWebapp("playwright");
  const browser = await chromium.launch({ headless: options.headlessBrowser });
  const consoleMessages = [];
  const results = {};
  try {
    for (const scenario of parseScenarioList(options.scenario)) {
      results[scenario] = [];
      for (const viewport of parseViewportList(options.viewports)) {
        const page = await browser.newPage({ viewport });
        page.on("console", (message) => {
          if (["error", "warning", "warn"].includes(message.type())) {
            consoleMessages.push({ type: message.type(), text: message.text(), location: message.location() });
          }
        });
        await page.goto(`http://127.0.0.1:${options.port}/?visual_debug=1`, { waitUntil: "domcontentloaded" });
        await page.waitForFunction(() => Boolean(window.__EMBEDAGENT_VISUAL_DEBUG__), null, { timeout: 10000 });
        await page.evaluate((id) => window.__EMBEDAGENT_VISUAL_DEBUG__.loadScenario(id), scenario);
        await page.locator("[data-agent-shell]").waitFor({ state: "visible" });
        const metrics = await assertShell(page, viewport);
        const screenshot = path.join(outputDir, `${scenario}-${viewport.name}.png`);
        const image = await page.screenshot({ path: screenshot, fullPage: false });
        assert.equal(image.length > 1000, true);
        results[scenario].push({ viewport: viewport.name, screenshot, metrics });
        await page.close();
      }
    }
  } finally {
    await browser.close();
  }
  return { results, console: summarizeConsoleMessages(consoleMessages) };
}

function printHelp() {
  console.log(`Usage: node scripts/gui-visual-debug.mjs [options]

  --scenario LIST   ${SCENARIOS.join(", ")} or all
  --viewports LIST  e.g. 1280x720,520x720
  --output PATH     screenshot and summary directory
  --no-build        reuse generated GUI assets
  --headed          show the browser
  --keep-server     leave the GUI host running`);
}

export async function runVisualDebug(options = parseVisualDebugArgs()) {
  if (options.help) {
    printHelp();
    return { help: true };
  }
  const repoRoot = DEFAULT_REPO_ROOT;
  if (options.buildWebapp) buildWebapp(repoRoot);
  const outputDir = path.resolve(options.output);
  fs.mkdirSync(outputDir, { recursive: true });
  const appHome = path.join(outputDir, "app-home");
  fs.mkdirSync(appHome, { recursive: true });
  const workspace = createWorkspace(path.resolve(
    options.workspace || path.join(os.tmpdir(), `embedagent-gui-visual-workspace-${Date.now()}`),
  ));
  const port = options.port || await freePort();
  const modelPort = options.modelPort || await freePort();
  const modelServer = await startFakeModelServer(modelPort);
  const child = startGui(buildGuiLaunchConfig({
    repoRoot,
    workspace,
    port,
    mode: options.mode,
    baseUrl: `http://127.0.0.1:${modelPort}/v1`,
    model: options.model,
    timeout: options.timeout,
    maxTurns: options.maxTurns,
    bundleRoot: options.bundleRoot,
    appHome,
    python: options.python,
  }), outputDir);
  await waitForProcessStart(child);
  const summary = {
    url: `http://127.0.0.1:${port}/`,
    workspace,
    outputDir,
    scenarios: parseScenarioList(options.scenario),
    results: {},
    console: { count: 0, relevant: [] },
    guiLogs: { stdout: child.stdoutPath, stderr: child.stderrPath },
  };
  try {
    await waitForHttp(summary.url);
    Object.assign(summary, await runScenarios({ ...options, port }, repoRoot, outputDir));
    fs.writeFileSync(path.join(outputDir, "summary.json"), JSON.stringify(summary, null, 2), "utf8");
    if (summary.console.count) {
      throw new Error(`GUI visual debug saw ${summary.console.count} console warning/error messages`);
    }
    return summary;
  } finally {
    modelServer.close();
    if (!options.keepServer) child.kill();
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  runVisualDebug()
    .then((summary) => { if (!summary.help) console.log(JSON.stringify(summary, null, 2)); })
    .catch((error) => {
      console.error(error?.stack || String(error));
      process.exitCode = 1;
    });
}
