#!/usr/bin/env node
import fs from "node:fs";
import assert from "node:assert/strict";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";

export const SCENARIOS = [
  "load",
  "chat",
  "composer",
  "palette",
  "preview",
  "diff",
  "file",
  "terminal",
  "responsive",
  "app",
  "thread",
  "timeline",
  "interaction",
  "panel-overflow",
  "terminal-split",
  "timeline-context",
];

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_REPO_ROOT = path.resolve(SCRIPT_DIR, "..");
const DEFAULT_SCENARIO_VIEWPORT = Object.freeze({ width: 1280, height: 720 });
const VISUAL_DEBUG_DIFF_FIXTURE = [
  "--- a/demo.c",
  "+++ b/demo.c",
  "@@ -1,3 +1,3 @@",
  " int main(void) {",
  "-    return 0;",
  "+    return 1;",
  " }",
  "--- a/src/app/util.c",
  "+++ b/src/app/util.c",
  "@@ -1 +1,2 @@",
  "+int util(void) { return 1; }",
  "",
].join("\n");

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
  const unique = Array.from(new Set(scenarios));
  if (unique.includes("app")) {
    return ["app", ...unique.filter((item) => item !== "app")];
  }
  return unique;
}

export function parseViewportList(value = "1280x720,900x640,700x640,520x720") {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const match = item.match(/^(\d+)x(\d+)$/i);
      if (!match) {
        throw new Error(`Invalid viewport: ${item}`);
      }
      const width = Number(match[1]);
      const height = Number(match[2]);
      if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
        throw new Error(`Invalid viewport: ${item}`);
      }
      return { name: `${width}x${height}`, width, height };
    });
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
    viewports: "1280x720,900x640,700x640,520x720",
    buildWebapp: true,
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
    } else if (arg === "--viewports") {
      options.viewports = readOption(argv, index);
      index += 1;
    } else if (arg === "--no-build") {
      options.buildWebapp = false;
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
  parseViewportList(options.viewports);
  return options;
}

function buildWebappStatic(repoRoot) {
  const webappRoot = path.dirname(resolveWebappPackageJson(repoRoot));
  const command = process.platform === "win32" ? "cmd.exe" : "npm";
  const args = process.platform === "win32"
    ? ["/d", "/s", "/c", "npm run build"]
    : ["run", "build"];
  const result = spawnSync(command, args, {
    cwd: webappRoot,
    stdio: "inherit",
    env: process.env,
  });
  if (result.error) {
    throw new Error(`Failed to build GUI webapp: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`GUI webapp build failed with exit code ${result.status}`);
  }
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
  const command = resolvePython({ repoRoot, python });
  const env = {
    ...process.env,
    PYTHONPATH: path.join(repoRoot, "src"),
  };
  if (bundleRoot) {
    env.EMBEDAGENT_BUNDLE_ROOT = bundleRoot;
  }
  if (appHome) {
    env.EMBEDAGENT_GUI_APP_HOME = appHome;
  }
  const args = ["-m", "embedagent.frontend.gui.launcher"];
  if (workspace) {
    args.push("--workspace", workspace);
  }
  args.push(
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
  );
  return {
    command,
    args,
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
  const srcDir = path.join(targetRoot, "src");
  ensureDir(srcDir);
  const parser = path.join(srcDir, "parser.c");
  if (!fs.existsSync(parser)) {
    fs.writeFileSync(
      parser,
      [
        "int parse_value(void) {",
        "  return 0;",
        "}",
        "line 4 reveal target",
        "void recover(void) {}",
      ].join("\n"),
      "utf8",
    );
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
    const rects = Array.from(document.querySelectorAll(".right-panel-surface-tab")).map((el) => {
      const rect = el.getBoundingClientRect();
      return { text: el.textContent.trim(), x: rect.x, width: rect.width };
    });
    return rects.every((item, index) => index === 0 || item.x >= rects[index - 1].x + rects[index - 1].width - 0.5);
  });
}

async function scrollContainerMetrics(page, selectors = []) {
  return await page.evaluate((items) => {
    const metrics = {};
    for (const [name, selector] of items) {
      const element = document.querySelector(selector);
      if (!element) {
        metrics[name] = { present: false };
        continue;
      }
      const style = window.getComputedStyle(element);
      const before = element.scrollTop;
      element.scrollTop = Math.min(48, Math.max(0, element.scrollHeight - element.clientHeight));
      const after = element.scrollTop;
      element.scrollTop = before;
      metrics[name] = {
        present: true,
        overflowY: style.overflowY,
        clientHeight: Math.round(element.clientHeight),
        scrollHeight: Math.round(element.scrollHeight),
        canScroll: after > before || element.scrollHeight > element.clientHeight + 1,
      };
    }
    return metrics;
  }, selectors);
}

function assertScrollContainer(metrics, name, { requireScrollable = false } = {}) {
  const item = metrics[name];
  if (!item?.present) {
    throw new Error(`Missing scroll container: ${name}`);
  }
  if (!["auto", "scroll"].includes(item.overflowY)) {
    throw new Error(`Expected ${name} to allow vertical scrolling, saw overflow-y=${item.overflowY}`);
  }
  if (item.clientHeight <= 0) {
    throw new Error(`Scroll container ${name} has no visible height`);
  }
  if (requireScrollable && !item.canScroll) {
    throw new Error(`Expected ${name} to be scrollable with fixture content`);
  }
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
  await page.click('[data-testid="composer-primary-action"]');
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
  await page.evaluate(() => {
    window.__EMBEDAGENT_VISUAL_DEBUG__?.loadSourceControlFixture?.();
  });
  await page.waitForSelector('[data-testid="branch-toolbar"]', { timeout: 10000 });
  const branchToolbar = await page.locator('[data-testid="branch-toolbar"]').innerText();
  if (!branchToolbar.includes("feature/t3-toolbar") || !branchToolbar.includes("4 changes")) {
    throw new Error(`Branch toolbar did not show fixture state: ${branchToolbar}`);
  }
  return { assistantText, branchToolbar };
}

async function composerMenuMetrics(page) {
  return await page.evaluate(() => {
    const menu = document.querySelector('[data-testid="composer-command-menu"]');
    const input = document.querySelector('[data-testid="composer-input"]');
    const menuBox = menu?.getBoundingClientRect();
    const inputBox = input?.getBoundingClientRect();
    return {
      viewportWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      menu: menuBox ? {
        left: Math.round(menuBox.left),
        right: Math.round(menuBox.right),
        width: Math.round(menuBox.width),
        height: Math.round(menuBox.height),
      } : null,
      input: inputBox ? {
        left: Math.round(inputBox.left),
        right: Math.round(inputBox.right),
        width: Math.round(inputBox.width),
      } : null,
      activeItems: document.querySelectorAll(".composer-menu-item.active").length,
    };
  });
}

async function loadComposerFixture(page) {
  await page.evaluate(() => {
    window.__EMBEDAGENT_VISUAL_DEBUG__.loadComposerFileTreeFixture();
  });
}

async function openComposerPathMenu(page, input, viewportName) {
  let lastMenuText = "";
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await loadComposerFixture(page);
    await input.fill("@par");
    await page.waitForSelector('[data-testid="composer-command-menu"]', { timeout: 10000 });
    lastMenuText = await page.locator('[data-testid="composer-command-menu"]').innerText();
    if (lastMenuText.includes("src/parser.c")) {
      return lastMenuText;
    }
    await input.fill("");
  }
  throw new Error(`Composer path menu did not show src/parser.c at ${viewportName}: ${lastMenuText}`);
}

async function runComposerScenario(page, options, outputDir) {
  const viewports = parseViewportList(options.viewports);
  const results = [];
  for (const viewport of viewports) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.waitForFunction(() => Boolean(window.__EMBEDAGENT_VISUAL_DEBUG__), null, { timeout: 10000 });
    await page.waitForSelector('[data-testid="workbench-layout"]', { timeout: 10000 });
    await loadComposerFixture(page);
    await page.waitForSelector('[data-testid="composer-input"]', { timeout: 10000 });
    const input = page.locator('[data-testid="composer-input"]');

    await input.fill("/di");
    await page.waitForSelector('[data-testid="composer-command-menu"]', { timeout: 10000 });
    await page.keyboard.press("ArrowDown");
    const slashMenuText = await page.locator('[data-testid="composer-command-menu"]').innerText();
    if (!slashMenuText.includes("/diff")) {
      throw new Error(`Composer slash menu did not show /diff at ${viewport.name}: ${slashMenuText}`);
    }
    const slashMetrics = await composerMenuMetrics(page);
    if (slashMetrics.documentWidth > slashMetrics.viewportWidth + 1) {
      throw new Error(`Composer slash menu caused horizontal overflow at ${viewport.name}: ${slashMetrics.documentWidth}`);
    }
    if (!slashMetrics.menu || slashMetrics.menu.left < 0 || slashMetrics.menu.right > slashMetrics.viewportWidth + 1) {
      throw new Error(`Composer slash menu escaped viewport at ${viewport.name}: ${JSON.stringify(slashMetrics.menu)}`);
    }
    if (slashMetrics.activeItems !== 1) {
      throw new Error(`Composer slash menu should have one active item at ${viewport.name}`);
    }
    await page.keyboard.press("Enter");
    const slashValue = await input.inputValue();
    if (!slashValue.startsWith("/diff ")) {
      throw new Error(`Composer slash selection did not insert /diff: ${slashValue}`);
    }

    await openComposerPathMenu(page, input, viewport.name);
    const pathMetrics = await composerMenuMetrics(page);
    if (pathMetrics.documentWidth > pathMetrics.viewportWidth + 1) {
      throw new Error(`Composer path menu caused horizontal overflow at ${viewport.name}: ${pathMetrics.documentWidth}`);
    }
    await page.keyboard.press("Enter");
    const pathValue = await input.inputValue();
    if (pathValue !== "@src/parser.c ") {
      throw new Error(`Composer path selection did not insert @src/parser.c: ${pathValue}`);
    }

    const screenshot = path.join(outputDir, `composer-${viewport.name}.png`);
    await page.screenshot({ path: screenshot, fullPage: false });
    results.push({
      name: viewport.name,
      slashMenu: slashMetrics,
      pathMenu: pathMetrics,
      slashValue,
      pathValue,
      screenshot,
    });
  }
  return { viewports: results };
}

async function runPaletteScenario(page, options, outputDir) {
  const viewports = parseViewportList(options.viewports);
  const results = [];
  for (const viewport of viewports) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.waitForFunction(() => Boolean(window.__EMBEDAGENT_VISUAL_DEBUG__), null, { timeout: 10000 });
    await page.waitForSelector('[data-testid="workbench-layout"]', { timeout: 10000 });
    await page.evaluate(() => {
      window.__EMBEDAGENT_VISUAL_DEBUG__.loadThreadLifecycleFixture();
    });
    await page.waitForSelector(".thread-card.selected", { state: "attached", timeout: 10000 });

    await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
    await page.waitForSelector('[data-testid="command-palette"]', { timeout: 10000 });
    await page.waitForSelector('[data-testid="command-palette-group--commands"]', { timeout: 10000 });
    await page.waitForSelector('[data-testid^="command-palette-session--"]', { timeout: 10000 });
    await page.waitForSelector('[data-testid^="command-palette-workspace--"]', { timeout: 10000 });

    const rootText = await page.locator('[data-testid="command-palette"]').innerText();
    const normalizedRootText = rootText.toLowerCase();
    if (!normalizedRootText.includes("commands") || !normalizedRootText.includes("sessions") || !normalizedRootText.includes("workspaces")) {
      throw new Error(`Palette root groups missing at ${viewport.name}: ${rootText}`);
    }

    await page.keyboard.press("ArrowDown");
    const activeRowsAfterArrow = await page.locator(".cmd-palette-row.active").count();
    if (activeRowsAfterArrow !== 1) {
      throw new Error(`Palette should have one active row after ArrowDown at ${viewport.name}`);
    }

    await page.click('[data-testid="command-palette-submenu--surface"]');
    await page.waitForSelector('[data-testid="command-palette-back"]', { timeout: 10000 });
    await page.fill('[data-testid="command-palette-input"]', "diff");
    await page.waitForSelector('[data-testid="command-palette-command--surface.diff"]', { timeout: 10000 });
    await page.keyboard.press("Enter");
    await page.waitForSelector('[data-testid="right-panel-surface-tab--diff"]', { timeout: 10000 });

    const noOverlap = await assertNoOverlap(page);
    if (!noOverlap) throw new Error(`Palette scenario overlapped layout at ${viewport.name}`);

    const screenshot = path.join(outputDir, `palette-${viewport.name}.png`);
    await page.screenshot({ path: screenshot, fullPage: true });
    results.push({ name: viewport.name, noOverlap, screenshot });
  }
  return { viewports: results };
}

async function runPreviewScenario(page) {
  await page.waitForSelector('[data-testid="right-panel-empty-surface--preview"]', { timeout: 10000 });
  await page.click('[data-testid="right-panel-empty-surface--preview"]');
  await page.waitForSelector('[data-testid="right-panel-preview-surface"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="preview-url-input"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="preview-empty-state"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="preview-local-server-card"]', { timeout: 10000 });
  const emptyText = await page.locator('[data-testid="right-panel-preview-surface"]').innerText();
  const localServerCount = await page.locator('[data-testid="preview-local-server-card"]').count();
  await page.locator('[data-testid="preview-local-server-card"]').first().click();
  await page.waitForSelector('[data-testid="preview-refresh-action"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="preview-open-external-action"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="preview-unreachable"], [data-testid="preview-viewport"]', { timeout: 10000 });
  const activeTab = await page.locator('[data-testid="right-panel-surface-tab--preview"] [role="tab"]').getAttribute("aria-selected");
  const previewTabs = await page.locator('[data-testid="right-panel-surface-tab--preview"]').count();
  const urlValue = await page.locator('[data-testid="preview-url-input"]').inputValue();
  const refreshDisabled = await page.locator('[data-testid="preview-refresh-action"]').isDisabled();
  const openExternalDisabled = await page.locator('[data-testid="preview-open-external-action"]').isDisabled();
  const surfaceText = await page.locator('[data-testid="right-panel-preview-surface"]').innerText();
  const noOverlap = await assertNoOverlap(page);
  if (activeTab !== "true") throw new Error("Preview tab did not become active");
  if (previewTabs !== 1) throw new Error(`Preview URL should replace the empty preview tab, saw ${previewTabs} tabs`);
  if (localServerCount < 1) throw new Error("Preview empty state did not expose local server cards");
  if (!emptyText.includes("Local servers") || !emptyText.includes("localhost:5173")) {
    throw new Error(`Preview empty state was incomplete: ${emptyText}`);
  }
  if (!urlValue.includes("localhost:5173")) {
    throw new Error(`Preview URL field did not use the local server URL: ${urlValue}`);
  }
  if (refreshDisabled || openExternalDisabled) {
    throw new Error("Preview runtime actions should be enabled after opening a local URL");
  }
  if (!surfaceText.includes("Preview unavailable")) {
    throw new Error(`Preview runtime did not show the expected unavailable state: ${surfaceText}`);
  }
  if (!noOverlap) throw new Error("Right panel tabs overlap in preview scenario");
  return {
    activeTab: activeTab === "true",
    previewTabs,
    localServerCount,
    urlValue,
    runtimeActionsEnabled: !refreshDisabled && !openExternalDisabled,
    hasViewport: true,
    rightTabsDoNotOverlap: noOverlap,
  };
}

async function runDiffScenario(page) {
  await page.waitForFunction(() => Boolean(window.__EMBEDAGENT_VISUAL_DEBUG__), null, { timeout: 10000 });
  await page.evaluate((diff) => {
    window.__EMBEDAGENT_VISUAL_DEBUG__.openDiffFixture({
      title: "Visual Debug Diff",
      diff,
      filePath: "demo.c",
    });
  }, VISUAL_DEBUG_DIFF_FIXTURE);
  await page.waitForSelector('[data-testid="diff-panel"]', { timeout: 15000 });
  await page.waitForSelector('[data-testid="diff-file-rail"]', { timeout: 15000 });
  await page.waitForSelector('[data-testid="diff-file--demo.c"]', { timeout: 15000 });
  const panelText = await page.locator('[data-testid="diff-panel"]').innerText();
  const activeTab = await page.locator('[data-testid="right-panel-surface-tab--diff"] [role="tab"]').getAttribute("aria-selected");
  const diffChromeState = await page.evaluate(() => ({
    hasSubheader: Boolean(document.querySelector(".diff-panel [data-surface-subheader]")),
    hasChipStrip: Boolean(document.querySelector(".diff-selection-chip-strip")),
    hasStacked: Boolean(document.querySelector('[data-testid="diff-mode-toggle--stacked"]')),
    hasSplit: Boolean(document.querySelector('[data-testid="diff-mode-toggle--split"]')),
    hasWrap: Boolean(document.querySelector('[data-testid="diff-wrap-toggle"]')),
    hasWhitespace: Boolean(document.querySelector('[data-testid="diff-whitespace-toggle"]')),
  }));
  await page.click('[data-testid="diff-mode-toggle--split"]');
  await page.click('[data-testid="diff-wrap-toggle"]');
  const diffChromeToggleState = await page.evaluate(() => {
    const viewport = document.querySelector(".diff-panel-viewport");
    return {
      split: Boolean(viewport?.classList.contains("split")),
      wordWrap: Boolean(viewport?.classList.contains("word-wrap")),
    };
  });
  const noOverlap = await assertNoOverlap(page);
  if (activeTab !== "true") throw new Error("Diff tab did not become active");
  if (!panelText.includes("demo.c") || !panelText.includes("return 1")) {
    throw new Error("Diff panel did not show the expected demo.c change");
  }
  if (!Object.values(diffChromeState).every(Boolean)) {
    throw new Error(`Diff panel chrome is incomplete: ${JSON.stringify(diffChromeState)}`);
  }
  if (!diffChromeToggleState.split || !diffChromeToggleState.wordWrap) {
    throw new Error(`Diff panel controls did not update viewport classes: ${JSON.stringify(diffChromeToggleState)}`);
  }
  if (!noOverlap) throw new Error("Right panel tabs overlap in diff scenario");
  return {
    activeTab: activeTab === "true",
    hasFileRail: await page.locator('[data-testid="diff-file-rail"]').isVisible(),
    hasDemoDiff: panelText.includes("demo.c") && panelText.includes("return 1"),
    diffChromeState,
    diffChromeToggleState,
    rightTabsDoNotOverlap: noOverlap,
  };
}

async function runFileScenario(page) {
  await page.waitForSelector('[data-testid="right-panel-empty-surface--files"]', { timeout: 10000 });
  const leftFilesTabCount = await page.locator('[data-testid="sidebar-tab--files"]').count();
  const leftFileTreeCount = await page.locator('[data-testid^="file-tree-node--"]').count();
  await page.click('[data-testid="right-panel-empty-surface--files"]');
  await page.waitForSelector('[data-testid="right-panel-files-surface"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="right-panel-file-node--README.md"]', { timeout: 10000 });
  const filesMetrics = await scrollContainerMetrics(page, [
    ["filesSurface", '[data-testid="right-panel-file-tree-scroll"]'],
    ["rightPanelBody", ".right-panel-body"],
  ]);
  await page.click('[data-testid="right-panel-file-node--README.md"]');
  await page.waitForSelector('[data-testid="right-panel-file-surface"]', { timeout: 15000 });
  await page.waitForSelector('[data-testid="file-preview-breadcrumbs"]', { timeout: 15000 });
  // README.md is a markdown file, so the T3 file chrome defaults to the rendered preview.
  await page.waitForSelector('[data-testid="file-preview-markdown"]', { timeout: 15000 });
  await page.waitForSelector('[data-testid="file-preview-mode-toggle"]', { timeout: 15000 });
  const breadcrumbText = await page.locator('[data-testid="file-preview-breadcrumbs"]').innerText();
  const filePreviewChromeState = await page.evaluate(() => ({
    hasSubheader: Boolean(document.querySelector(".right-panel-file-surface [data-surface-subheader]")),
    hasOpenAction: Boolean(document.querySelector('[data-testid="file-preview-open-action"]')),
    hasExplorerToggle: Boolean(document.querySelector('[data-testid="file-preview-explorer-toggle"]')),
    hasBreadcrumbs: Boolean(document.querySelector("[data-file-breadcrumbs]")),
  }));
  // Switch to the code view to exercise the numbered gutter.
  await page.click('[data-testid="file-preview-mode-toggle"]');
  await page.waitForSelector('[data-testid="right-panel-file-content"]', { timeout: 15000 });
  await page.waitForSelector('[data-testid="file-preview-gutter"]', { timeout: 15000 });
  const panelText = await page.locator('[data-testid="right-panel-file-surface"]').innerText();
  await page.evaluate(() => {
    window.__EMBEDAGENT_VISUAL_DEBUG__?.loadFilePreviewRevealFixture?.();
  });
  await page.waitForSelector('[data-testid="right-panel-file-content"]', { timeout: 15000 });
  await page.waitForSelector('[data-file-link-reveal]', { timeout: 15000 });
  const revealState = await page.evaluate(() => {
    const revealed = Array.from(document.querySelectorAll("[data-file-link-reveal]"));
    const target = document.querySelector('[data-file-line="4"]');
    const gutter = document.querySelector('[data-file-line-number="4"]');
    const content = document.querySelector('[data-testid="right-panel-file-content"]');
    const targetRect = target?.getBoundingClientRect();
    const contentRect = content?.getBoundingClientRect();
    return {
      count: revealed.length,
      targetText: target?.textContent || "",
      gutterText: gutter?.textContent || "",
      targetVisible: Boolean(
        targetRect &&
          contentRect &&
          targetRect.top >= contentRect.top &&
          targetRect.bottom <= contentRect.bottom,
      ),
    };
  });
  const activeTab = await page.locator('[data-testid="right-panel-surface-tab--file"] [role="tab"]').getAttribute("aria-selected");
  const filesTabs = await page.locator('[data-testid="right-panel-surface-tab--files"]').count();
  const noOverlap = await assertNoOverlap(page);
  if (leftFilesTabCount !== 0) throw new Error("Left sidebar still exposes a Files tab");
  if (leftFileTreeCount !== 0) throw new Error("Left sidebar still renders file tree nodes");
  assertScrollContainer(filesMetrics, "filesSurface");
  if (activeTab !== "true") throw new Error("File tab did not become active");
  if (filesTabs !== 0) throw new Error("Standalone files surface was not replaced by file surface");
  if (!breadcrumbText.includes("README.md")) {
    throw new Error("File surface breadcrumbs did not show the file name");
  }
  if (!Object.values(filePreviewChromeState).every(Boolean)) {
    throw new Error(`File preview chrome is incomplete: ${JSON.stringify(filePreviewChromeState)}`);
  }
  if (!panelText.includes("Visual Debug Workspace")) {
    throw new Error("File surface did not show README.md fixture content");
  }
  if (revealState.count !== 2 || !revealState.targetText.includes("line 4 reveal target")) {
    throw new Error(`File reveal marker did not target README.md line 4: ${JSON.stringify(revealState)}`);
  }
  if (!revealState.targetVisible) {
    throw new Error("File reveal target was not visible after scrollIntoView");
  }
  if (!noOverlap) throw new Error("Right panel tabs overlap in file scenario");
  return {
    activeTab: activeTab === "true",
    filesSurfaceReplaced: filesTabs === 0,
    hasReadmeContent: panelText.includes("Visual Debug Workspace"),
    hasBreadcrumbs: breadcrumbText.includes("README.md"),
    filePreviewChromeState,
    leftFilesTabAbsent: leftFilesTabCount === 0,
    leftFileTreeAbsent: leftFileTreeCount === 0,
    revealState,
    scrollContainers: filesMetrics,
    rightTabsDoNotOverlap: noOverlap,
  };
}

async function runTerminalScenario(page) {
  await page.waitForSelector('[data-testid="new-session-btn"]', { timeout: 10000 });
  if (await page.locator(".thread-card.selected").count() === 0) {
    await page.click('[data-testid="new-session-btn"]');
    await page.waitForSelector(".thread-card.selected", { timeout: 15000 });
  }
  await page.waitForSelector('[data-testid="right-panel-empty-surface--terminal"]', { timeout: 10000 });
  await page.click('[data-testid="right-panel-empty-surface--terminal"]');
  await page.waitForSelector('[data-testid="right-panel-terminal-surface"]', { timeout: 15000 });
  await page.waitForSelector('[data-testid^="right-panel-terminal-pane--"]', { timeout: 15000 });
  await page.click('[data-testid="right-panel-terminal-surface"] button[title="Split terminal horizontally"]');
  try {
    await page.waitForFunction(() => {
      return document.querySelectorAll('[data-testid^="right-panel-terminal-pane--"]').length >= 2;
    }, null, { timeout: 15000 });
  } catch (error) {
    const details = await page.evaluate(() => ({
      paneIds: Array.from(document.querySelectorAll('[data-testid^="right-panel-terminal-pane--"]')).map((element) => element.getAttribute("data-testid")),
      surfaceText: document.querySelector('[data-testid="right-panel-terminal-surface"]')?.textContent || "",
      notice: document.querySelector(".interaction-notice")?.textContent || "",
      selectedThreadCount: document.querySelectorAll(".thread-card.selected").length,
    }));
    throw new Error(`Terminal split did not create a second pane: ${JSON.stringify(details)} (${error.message})`);
  }
  const activeTab = await page.locator('[data-testid="right-panel-surface-tab--terminal"] [role="tab"]').getAttribute("aria-selected");
  const paneCount = await page.locator('[data-testid^="right-panel-terminal-pane--"]').count();
  const splitDirection = await page.locator('[data-testid="right-panel-terminal-surface"]').getAttribute("data-split-direction");
  const noOverlap = await assertNoOverlap(page);
  if (activeTab !== "true") throw new Error("Terminal tab did not become active");
  if (paneCount < 2) throw new Error(`Expected split terminal panes, saw ${paneCount}`);
  if (splitDirection !== "horizontal") throw new Error(`Expected horizontal split, saw ${splitDirection}`);
  if (!noOverlap) throw new Error("Right panel tabs overlap in terminal scenario");
  return {
    activeTab: activeTab === "true",
    paneCount,
    splitDirection,
    rightTabsDoNotOverlap: noOverlap,
  };
}

async function runTimelineScenario(page) {
  await page.waitForFunction(() => Boolean(window.__EMBEDAGENT_VISUAL_DEBUG__), null, { timeout: 10000 });
  await page.evaluate(() => {
    window.__EMBEDAGENT_VISUAL_DEBUG__.loadTimelineFixture();
  });
  await page.waitForSelector('[data-testid="timeline-user-message"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="changed-files-card"]', { timeout: 10000 });
  const firstFold = page.locator('[data-testid="timeline-turn-fold"] button[aria-expanded="false"]').first();
  if (await firstFold.count()) {
    await firstFold.click();
  }
  await page.waitForSelector('[data-testid="timeline-reasoning-row"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="timeline-review-result-row"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="timeline-working-row"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="timeline-work-row"]', { timeout: 10000 });
  for (let index = 0; index < 20; index += 1) {
    const collapsedWorkRow = page.locator('[data-testid="timeline-work-row"] button[aria-expanded="false"]').first();
    if (!(await collapsedWorkRow.count())) break;
    await collapsedWorkRow.click();
  }
  await page.waitForSelector('[data-testid="timeline-work-detail"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="timeline-tool-detail"]', { timeout: 10000 });
  const fileLink = page.locator('[data-testid="timeline-tool-file-link--src/parser.c"]').filter({ hasText: "src/parser.c:4" }).first();
  if (await fileLink.count()) {
    await fileLink.click();
  } else {
    await page.locator('[data-testid="timeline-file-link--src/parser.c"]').first().click();
  }
  await page.waitForSelector('[data-testid="right-panel-file-surface"]', { timeout: 10000 });
  await page.waitForSelector("[data-file-link-reveal]", { timeout: 10000 });
  const timelineLinkRevealState = await page.evaluate(() => {
    const revealed = Array.from(document.querySelectorAll("[data-file-link-reveal]"));
    const target = document.querySelector('[data-file-line="4"]');
    const gutter = document.querySelector('[data-file-line-number="4"]');
    return {
      count: revealed.length,
      targetText: target?.textContent || "",
      gutterText: gutter?.textContent || "",
    };
  });
  if (timelineLinkRevealState.count !== 2 || !timelineLinkRevealState.targetText.includes("line 4 reveal target")) {
    throw new Error(`Timeline file link did not reveal target line: ${JSON.stringify(timelineLinkRevealState)}`);
  }
  const rowCount = await page.locator("[data-row-kind]").count();
  const detailText = await page.locator('[data-testid="timeline-work-detail"]').first().innerText();
  const rawJsonVisible = detailText.trim().startsWith("{") || detailText.includes('"path":');
  const detailFieldCount = await page.locator(".t3-tool-detail-grid dt").count();
  const workPresentation = await page.evaluate(() =>
    Array.from(document.querySelectorAll('[data-testid="timeline-work-row"]')).map((row) => ({
      iconName: row.getAttribute("data-icon-name") || "",
      statusIndicator: row.getAttribute("data-status-indicator") || "",
      text: (row.textContent || "").replace(/\s+/g, " ").trim(),
    })),
  );
  const scrollMetrics = await scrollContainerMetrics(page, [
    ["timeline", ".timeline"],
  ]);
  const noOverlap = await assertNoOverlap(page);
  assertScrollContainer(scrollMetrics, "timeline");
  if (rawJsonVisible) throw new Error("Timeline work detail still exposes raw JSON");
  if (detailFieldCount === 0) throw new Error("Timeline work detail did not render structured fields");
  const iconNames = new Set(workPresentation.map((entry) => entry.iconName));
  for (const expectedIcon of ["eye", "square-pen", "terminal", "wrench"]) {
    if (!iconNames.has(expectedIcon)) {
      throw new Error(`Timeline work rows missing ${expectedIcon} presentation icon: ${JSON.stringify(workPresentation)}`);
    }
  }
  if (!workPresentation.some((entry) => entry.statusIndicator === "success")) {
    throw new Error(`Timeline work rows missing success status indicator: ${JSON.stringify(workPresentation)}`);
  }
  if (!noOverlap) throw new Error("Right panel tabs overlap in timeline scenario");
  const richTimelineState = {
    hasChangedFiles: await page.locator('[data-testid="changed-files-card"]').isVisible(),
    hasReasoning: await page.locator('[data-testid="timeline-reasoning-row"]').first().isVisible(),
    hasReview: await page.locator('[data-testid="timeline-review-result-row"]').first().isVisible(),
    hasWorking: await page.locator('[data-testid="timeline-working-row"]').first().isVisible(),
    hasExpandedDetail: await page.locator('[data-testid="timeline-work-detail"]').first().isVisible(),
    timelineLinkRevealState,
    workPresentation,
  };
  await page.evaluate(() => {
    window.__EMBEDAGENT_VISUAL_DEBUG__.loadLongTimelineFixture();
  });
  await page.waitForFunction(
    () => document.querySelectorAll('[data-testid="timeline-user-message"]').length > 20,
    null,
    { timeout: 10000 },
  );
  const longScrollMetrics = await scrollContainerMetrics(page, [
    ["timeline", ".timeline"],
  ]);
  assertScrollContainer(longScrollMetrics, "timeline", { requireScrollable: true });
  return {
    rowCount,
    ...richTimelineState,
    hasStructuredToolDetail: detailFieldCount > 0,
    rawJsonVisible,
    scrollContainers: scrollMetrics,
    longScrollContainers: longScrollMetrics,
    rightTabsDoNotOverlap: noOverlap,
  };
}

async function runInteractionScenario(page) {
  await page.waitForFunction(() => Boolean(window.__EMBEDAGENT_VISUAL_DEBUG__), null, { timeout: 10000 });
  await page.evaluate(() => {
    window.__EMBEDAGENT_VISUAL_DEBUG__.loadInteractionFixture("permission");
  });
  await page.waitForSelector('[data-testid="composer-interaction-panel"]', { timeout: 10000 });
  const panelText = await page.locator('[data-testid="composer-interaction-panel"]').innerText();
  const noOverlap = await assertNoOverlap(page);
  if (!panelText.includes("edit_file") && !panelText.includes("parser.c")) {
    throw new Error("Interaction fixture did not render permission details");
  }
  if (!noOverlap) throw new Error("Right panel tabs overlap in interaction scenario");
  return {
    hasInteractionPanel: true,
    panelText,
    rightTabsDoNotOverlap: noOverlap,
  };
}

async function runPanelOverflowScenario(page) {
  await page.waitForFunction(() => Boolean(window.__EMBEDAGENT_VISUAL_DEBUG__), null, { timeout: 10000 });
  await page.evaluate(() => {
    window.__EMBEDAGENT_VISUAL_DEBUG__.loadPanelOverflowFixture();
  });
  await page.getByTestId("right-panel-surface-tabs").waitFor();
  await page.getByLabel("Add panel surface").click();
  const menuVisible = await page.locator(".right-panel-add-menu-popup").isVisible();
  assert.equal(menuVisible, true);
  const menuBox = await page.locator(".right-panel-add-menu-popup").boundingBox();
  const tabsBox = await page.getByTestId("right-panel-surface-tabs").boundingBox();
  assert.equal(Boolean(menuBox && tabsBox && menuBox.height > tabsBox.height), true);
  return { menuEscapesTabbar: true };
}

async function runTerminalSplitScenario(page) {
  await page.waitForFunction(() => Boolean(window.__EMBEDAGENT_VISUAL_DEBUG__), null, { timeout: 10000 });
  await page.evaluate(() => {
    window.__EMBEDAGENT_VISUAL_DEBUG__.loadTerminalSplitFixture();
  });
  await page.getByTestId("right-panel-terminal-surface").waitFor();
  const paneCount = await page.locator(".terminal-shell-pane").count();
  assert.equal(paneCount, 2);
  return { paneCount };
}

async function runTimelineContextScenario(page) {
  await page.waitForFunction(() => Boolean(window.__EMBEDAGENT_VISUAL_DEBUG__), null, { timeout: 10000 });
  await page.evaluate(() => {
    window.__EMBEDAGENT_VISUAL_DEBUG__.loadTimelineContextFixture();
  });
  await page.getByTestId("timeline-root").waitFor();
  const compactRows = await page.locator('[data-row-kind="compact"]').count();
  assert.equal(compactRows, 0);
  const contextRows = await page.locator('[data-row-kind="context_summary"], [data-row-kind="system_notice"]').count();
  return { compactRows, contextRows };
}

async function runThreadScenario(page) {
  await page.waitForFunction(() => Boolean(window.__EMBEDAGENT_VISUAL_DEBUG__), null, { timeout: 10000 });
  await page.waitForSelector('[data-testid="workbench-layout"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="thread-list"]', { timeout: 10000 });
  await page.waitForFunction(() => {
    return Boolean(
      document.querySelector('[data-testid="thread-empty-state"]')
      || document.querySelector(".thread-card"),
    );
  }, null, { timeout: 10000 });
  await page.evaluate(() => {
    window.__EMBEDAGENT_VISUAL_DEBUG__.loadThreadLifecycleFixture();
  });
  await page.waitForSelector('[data-testid="thread-lifecycle-panel"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="session-card--visual-thread-active"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="thread-action--rename--visual-thread-active"]', { timeout: 10000 });
  const rowCount = await page.locator(".thread-card").count();
  const actionCount = await page.locator(".thread-action").count();
  const selectedCount = await page.locator(".thread-card.selected").count();
  const scrollMetrics = await scrollContainerMetrics(page, [
    ["threadList", ".thread-list"],
  ]);
  const layout = await page.evaluate(() => {
    const sidebar = document.querySelector('[data-testid="sidebar"]');
    const rows = Array.from(document.querySelectorAll(".thread-card"));
    const actions = Array.from(document.querySelectorAll(".thread-actions"));
    const rect = (element) => {
      if (!element) return null;
      const box = element.getBoundingClientRect();
      return {
        left: Math.round(box.left),
        right: Math.round(box.right),
        top: Math.round(box.top),
        bottom: Math.round(box.bottom),
        width: Math.round(box.width),
        height: Math.round(box.height),
      };
    };
    const sidebarRect = rect(sidebar);
    return {
      sidebar: sidebarRect,
      rows: rows.map(rect),
      actions: actions.map(rect),
      rowText: rows.map((row) => row.textContent.trim().replace(/\s+/g, " ")),
    };
  });
  if (rowCount < 3) {
    throw new Error(`Thread lifecycle fixture expected at least 3 rows, saw ${rowCount}`);
  }
  if (actionCount !== rowCount * 3) {
    throw new Error(`Thread lifecycle fixture expected 3 actions per row, saw ${actionCount}`);
  }
  if (selectedCount !== 1) {
    throw new Error(`Thread lifecycle fixture expected one active thread, saw ${selectedCount}`);
  }
  if (!layout.sidebar) {
    throw new Error("Thread lifecycle scenario could not measure sidebar");
  }
  assertScrollContainer(scrollMetrics, "threadList");
  const overflowing = layout.rows
    .concat(layout.actions)
    .filter((item) => item && item.right > layout.sidebar.right + 1);
  if (overflowing.length > 0) {
    throw new Error("Thread lifecycle controls overflow the sidebar");
  }
  return {
    rowCount,
    actionCount,
    enabledActionCount: actionCount - await page.locator(".thread-action:disabled").count(),
    selectedCount,
    scrollContainers: scrollMetrics,
    layout,
  };
}

async function runAppScenario(page, options) {
  const first = options.appWorkspaceA;
  const second = options.appWorkspaceB;
  await page.waitForSelector('[data-testid="no-workspace-state"]', { timeout: 10000 });
  await page.fill('[data-testid="workspace-path-input"]', first);
  await page.click('[data-testid="open-workspace-button"]');
  await page.waitForSelector('[data-testid="workbench-layout"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="workspace-switcher"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="workspace-current-card"]', { timeout: 10000 });
  await page.waitForSelector('[data-testid="thread-list"]', { timeout: 10000 });
  await page.waitForSelector(".thread-panel-header", { timeout: 10000 });
  await page.waitForSelector('[data-testid="thread-empty-state"]', { timeout: 10000 });
  await page.fill('[data-testid="sidebar-workspace-path-input"]', second);
  await page.keyboard.press("Enter");
  const secondLabel = path.basename(second);
  await page.waitForFunction(
    (expectedLabel) => {
      const header = document.querySelector(".workspace-header-label");
      const active = document.querySelector(".workspace-row.active");
      return Boolean(
        header?.textContent?.includes(expectedLabel)
        && active?.textContent?.includes(expectedLabel),
      );
    },
    secondLabel,
    { timeout: 10000 },
  );
  const staleSessionSelected = await page.locator(".thread-card.selected").count();
  const projectManagerVisible = await page.locator('[data-testid="workspace-current-card"]').isVisible();
  const threadManagerVisible = await page.locator(".thread-panel-header").isVisible();
  const emptyThreadVisible = await page.locator('[data-testid="thread-empty-state"]').isVisible();
  const sidebarLayout = await page.evaluate(() => {
    const sidebar = document.querySelector('[data-testid="sidebar"]');
    const project = document.querySelector('[data-testid="workspace-switcher"]');
    const thread = document.querySelector(".thread-panel-header");
    const rect = (element) => {
      if (!element) return null;
      const box = element.getBoundingClientRect();
      return {
        top: Math.round(box.top),
        bottom: Math.round(box.bottom),
        height: Math.round(box.height),
      };
    };
    return {
      sidebar: rect(sidebar),
      project: rect(project),
      thread: rect(thread),
    };
  });
  if (!sidebarLayout.thread || !sidebarLayout.sidebar) {
    throw new Error("App scenario could not measure sidebar thread manager");
  }
  if (sidebarLayout.thread.bottom > sidebarLayout.sidebar.bottom) {
    throw new Error("Thread manager is pushed outside the visible sidebar");
  }
  return {
    openedFirstWorkspace: true,
    switchedSecondWorkspace: true,
    staleSessionSelected,
    projectManagerVisible,
    threadManagerVisible,
    emptyThreadVisible,
    sidebarLayout,
  };
}

async function measureResponsiveLayout(page) {
  return await page.evaluate(() => {
    const rect = (selector) => {
      const element = document.querySelector(selector);
      if (!element) return null;
      const box = element.getBoundingClientRect();
      return {
        left: Math.round(box.left),
        top: Math.round(box.top),
        right: Math.round(box.right),
        bottom: Math.round(box.bottom),
        width: Math.round(box.width),
        height: Math.round(box.height),
      };
    };
    const visibleTabs = Array.from(document.querySelectorAll('[role="tab"]')).filter((element) => {
      const style = window.getComputedStyle(element);
      const box = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
    });
    const visibleTabText = visibleTabs.map((element) => element.textContent.trim().replace(/\s+/g, " "));
    const headerButtons = Array.from(document.querySelectorAll(".app-header button")).map((element) => {
      const box = element.getBoundingClientRect();
      return {
        text: element.textContent.trim().replace(/\s+/g, " "),
        width: Math.round(box.width),
        height: Math.round(box.height),
      };
    });
    return {
      viewport: { width: window.innerWidth, height: window.innerHeight },
      documentWidth: document.documentElement.scrollWidth,
      center: rect(".workbench-center"),
      right: rect(".workbench-right-slot"),
      composer: rect(".composer"),
      branchToolbar: rect('[data-testid="branch-toolbar"]'),
      input: rect('[data-testid="composer-input"]'),
      visibleTabText,
      headerButtons,
      inspectorTabCount: Array.from(document.querySelectorAll(".insp-tab")).filter((element) => {
        const style = window.getComputedStyle(element);
        const box = element.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && box.width > 0 && box.height > 0;
      }).length,
    };
  });
}

async function runResponsiveScenario(page, options, outputDir) {
  const viewports = parseViewportList(options.viewports);
  const results = [];
  for (const viewport of viewports) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.waitForSelector('[data-testid="workbench-layout"]', { timeout: 10000 });
    await page.waitForSelector('[data-testid="composer-input"]', { timeout: 10000, state: "attached" });
    await page.evaluate(() => {
      window.__EMBEDAGENT_VISUAL_DEBUG__?.loadSourceControlFixture?.();
    });
    await page.waitForSelector('[data-testid="branch-toolbar"]', { timeout: 10000 });
    await page.waitForTimeout(250);
    const metrics = await measureResponsiveLayout(page);
    const minimumCenterWidth = viewport.width <= 720 ? 360 : 360;
    if (!metrics.center || metrics.center.width < minimumCenterWidth) {
      throw new Error(
        `Responsive center too narrow at ${viewport.name}: ${metrics.center ? metrics.center.width : "missing"}`,
      );
    }
    if (!metrics.input || metrics.input.width < 160) {
      throw new Error(
        `Composer input too narrow at ${viewport.name}: ${metrics.input ? metrics.input.width : "missing"}`,
      );
    }
    if (!metrics.branchToolbar || metrics.branchToolbar.width < 260) {
      throw new Error(
        `Branch toolbar too narrow at ${viewport.name}: ${metrics.branchToolbar ? metrics.branchToolbar.width : "missing"}`,
      );
    }
    if (metrics.documentWidth > viewport.width + 1) {
      throw new Error(`Horizontal document overflow at ${viewport.name}: ${metrics.documentWidth}`);
    }
    if (metrics.inspectorTabCount !== 0) {
      throw new Error(`Nested inspector tabs are visible at ${viewport.name}`);
    }
    const tallHeaderButton = metrics.headerButtons.find((button) => button.height > 32);
    if (tallHeaderButton) {
      throw new Error(
        `Header button wrapped at ${viewport.name}: ${tallHeaderButton.text} ${tallHeaderButton.height}px`,
      );
    }
    const screenshot = path.join(outputDir, `responsive-${viewport.name}.png`);
    await page.screenshot({ path: screenshot, fullPage: false });
    results.push({ ...metrics, name: viewport.name, screenshot });
  }
  return { viewports: results };
}

async function resetScenarioViewport(page) {
  await page.setViewportSize(DEFAULT_SCENARIO_VIEWPORT);
}

async function resetScenarioStorage(page) {
  await page.evaluate(() => {
    window.localStorage?.clear?.();
    window.sessionStorage?.clear?.();
  });
}

async function runScenarios(options, repoRoot, outputDir) {
  const requireFromWebapp = createRequire(pathToFileURL(resolveWebappPackageJson(repoRoot)));
  const { chromium } = requireFromWebapp("playwright");
  const browser = await chromium.launch({ headless: options.headlessBrowser });
  const page = await browser.newPage({ viewport: DEFAULT_SCENARIO_VIEWPORT });
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
    const url = `http://127.0.0.1:${options.port}/?visual_debug=1`;
    await page.goto(url, { waitUntil: "domcontentloaded" });
    const scenarios = parseScenarioList(options.scenario);
    for (const scenario of scenarios) {
      if (scenario !== "responsive") {
        await resetScenarioViewport(page);
      }
      if (scenario !== "app") {
        await resetScenarioStorage(page);
        await page.reload({ waitUntil: "domcontentloaded" });
      }
      if (scenario === "app") {
        results.app = await runAppScenario(page, options);
      } else if (scenario === "load") {
        results.load = await runLoadScenario(page);
      } else if (scenario === "chat") {
        results.chat = await runChatScenario(page);
      } else if (scenario === "composer") {
        results.composer = await runComposerScenario(page, options, outputDir);
      } else if (scenario === "palette") {
        results.palette = await runPaletteScenario(page, options, outputDir);
      } else if (scenario === "preview") {
        results.preview = await runPreviewScenario(page);
      } else if (scenario === "diff") {
        results.diff = await runDiffScenario(page);
      } else if (scenario === "file") {
        results.file = await runFileScenario(page);
      } else if (scenario === "terminal") {
        results.terminal = await runTerminalScenario(page);
      } else if (scenario === "thread") {
        results.thread = await runThreadScenario(page);
      } else if (scenario === "timeline") {
        results.timeline = await runTimelineScenario(page);
      } else if (scenario === "interaction") {
        results.interaction = await runInteractionScenario(page);
      } else if (scenario === "panel-overflow") {
        results[scenario] = await runPanelOverflowScenario(page);
      } else if (scenario === "terminal-split") {
        results[scenario] = await runTerminalSplitScenario(page);
      } else if (scenario === "timeline-context") {
        results[scenario] = await runTimelineContextScenario(page);
      } else if (scenario === "responsive") {
        results.responsive = await runResponsiveScenario(page, options, outputDir);
      }
      if (scenario !== "responsive") {
        results[scenario].screenshot = await captureScenario({ page, scenario, outputDir });
      }
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
  --scenario load|chat|composer|palette|preview|diff|file|terminal|responsive|app|thread|timeline|interaction|panel-overflow|terminal-split|timeline-context|all
                                   Scenario list to run (default: load)
  --workspace PATH                Existing workspace; temp workspace by default
  --output PATH                   Output dir for screenshots and summary JSON
  --bundle-root PATH              Optional offline bundle root for bundled tools
  --port N                        GUI port; 0 picks a free port
  --model-port N                  Fake model port; 0 picks a free port
  --viewports LIST                Responsive viewport list, e.g. 1280x720,700x640
  --no-build                      Reuse existing frontend/gui/static assets
  --headed                        Show the Playwright browser
  --keep-server                   Leave GUI server running after the run
`);
}

function collectScreenshots(results) {
  const screenshots = [];
  for (const result of Object.values(results || {})) {
    if (result && typeof result.screenshot === "string") {
      screenshots.push(result.screenshot);
    }
    if (result && Array.isArray(result.viewports)) {
      for (const viewport of result.viewports) {
        if (viewport && typeof viewport.screenshot === "string") {
          screenshots.push(viewport.screenshot);
        }
      }
    }
  }
  return screenshots;
}

export async function runVisualDebug(options = parseVisualDebugArgs()) {
  if (options.help) {
    printHelp();
    return { help: true };
  }
  const repoRoot = DEFAULT_REPO_ROOT;
  if (options.buildWebapp) {
    buildWebappStatic(repoRoot);
  }
  const outputDir = path.resolve(options.output);
  ensureDir(outputDir);
  const appHome = path.join(outputDir, "app-home");
  ensureDir(appHome);
  const scenarios = parseScenarioList(options.scenario);
  const workspace = path.resolve(
    options.workspace || path.join(os.tmpdir(), `embedagent-gui-visual-workspace-${Date.now()}`),
  );
  if (scenarios.includes("diff")) {
    createDiffWorkspace(workspace, resolveGitExecutable({ bundleRoot: options.bundleRoot }));
  } else {
    createWorkspace(workspace);
  }
  const appWorkspaceA = createWorkspace(
    path.join(os.tmpdir(), `embedagent-gui-app-a-${Date.now()}`),
  );
  const appWorkspaceB = scenarios.includes("diff")
    ? createDiffWorkspace(
        path.join(os.tmpdir(), `embedagent-gui-app-b-${Date.now()}`),
        resolveGitExecutable({ bundleRoot: options.bundleRoot }),
      )
    : createWorkspace(path.join(os.tmpdir(), `embedagent-gui-app-b-${Date.now()}`));
  const launchWorkspace = scenarios.includes("app") ? "" : workspace;

  const port = options.port || await freePort();
  const modelPort = options.modelPort || await freePort();
  const modelServer = await startFakeModelServer(modelPort);
  const launch = buildGuiLaunchConfig({
    repoRoot,
    workspace: launchWorkspace,
    port,
    mode: options.mode,
    baseUrl: `http://127.0.0.1:${modelPort}/v1`,
    model: options.model,
    timeout: options.timeout,
    maxTurns: options.maxTurns,
    bundleRoot: options.bundleRoot,
    appHome,
    python: options.python,
  });
  const child = startGuiProcess(launch, outputDir);
  await waitForProcessStart(child);
  const summary = {
    url: `http://127.0.0.1:${port}/`,
    workspace,
    outputDir,
    appHome,
    scenarios,
    appWorkspaces: {
      first: appWorkspaceA,
      second: appWorkspaceB,
    },
    screenshots: [],
    console: { count: 0, relevant: [] },
    guiLogs: {
      stdout: child.stdoutPath,
      stderr: child.stderrPath,
    },
  };
  try {
    await waitForHttp(summary.url, 20000);
    const run = await runScenarios(
      { ...options, port, appWorkspaceA, appWorkspaceB },
      repoRoot,
      outputDir,
    );
    Object.assign(summary, run, {
      screenshots: collectScreenshots(run.results),
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

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
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
