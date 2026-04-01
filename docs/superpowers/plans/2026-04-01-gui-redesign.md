# GUI 全面迭代 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 GUI 从 warm parchment 风格迁移到 GitHub Dark 设计体系，修复布局溢出和面板不同步问题，融入 Claude Code 风格工具状态展示。

**Architecture:** 完全重写 `styles.css`（设计 token 体系），重构 App.jsx JSX 为 `.app-shell` + `.workspace` 三列可拖拽布局，逐组件按新 token 更新，后端增加 refresh-signal push。

**Tech Stack:** React 18, esbuild (build.mjs), CSS custom properties, FastAPI WebSocket, Python protocol dataclasses

---

## File Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `webapp/src/styles.css` | **完全重写** | 设计 token + 所有布局与组件样式 |
| `webapp/src/App.jsx` | **修改** | 新 JSX 壳层、resize 行为、新 WS 事件处理 |
| `webapp/src/components/Timeline.jsx` | **修改** | 工具块三态展示 |
| `webapp/src/components/Inspector.jsx` | **修改** | Tab 3+溢出菜单，badge 数字 |
| `webapp/src/components/Composer.jsx` | **修改** | 模式徽章，提示栏 |
| `protocol/__init__.py` | **修改** | FrontendCallbacks 新增两个方法签名 |
| `core/adapter.py` | **修改** | CallbackBridge tool_finished 触发 refresh |
| `frontend/gui/backend/server.py` | **修改** | WebSocketFrontend 新增两个 dispatch 方法 |
| `tests/test_gui_sync.py` | **新建** | 后端 sync push 单元测试 |

---

## Task 1: CSS 设计 Token 系统

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/styles.css` (complete rewrite)

- [ ] **Step 1: 备份并核查当前 CSS 长度**

```bash
cd d:/Project/coding_agent/src/embedagent/frontend/gui/webapp
wc -l src/styles.css
```

- [ ] **Step 2: 完整替换 styles.css**

将 `src/styles.css` 替换为以下内容（完整文件）：

```css
/* ═══════════════════════════════════════════
   DESIGN TOKENS — GitHub Dark System
   ═══════════════════════════════════════════ */
:root {
  /* backgrounds — 4 层深度 */
  --bg-canvas:   #0d1117;
  --bg-default:  #161b22;
  --bg-subtle:   #21262d;
  --border-default: #30363d;
  --border-focus:   #388bfd;

  /* text — 全部 ≥ 4.5:1 on bg-canvas */
  --text-primary:   #e6edf3;   /* 14.5:1 */
  --text-secondary: #8b949e;   /* 5.9:1  */
  --text-muted:     #6e7681;   /* 4.5:1  */
  --text-link:      #58a6ff;
  --text-success:   #3fb950;

  /* semantic */
  --color-success: #3fb950;
  --color-warning: #d29922;
  --color-error:   #f85149;
  --color-info:    #388bfd;
  --color-accent:  #bc8cff;
  --color-diff-add:#7ee787;
  --color-diff-del:#ffa198;

  /* typography */
  --font-sans: system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "Cascadia Code", "Consolas", "SF Mono", "Courier New", monospace;

  /* spacing */
  --sp-1:4px; --sp-2:8px; --sp-3:12px; --sp-4:16px; --sp-6:24px;

  /* radius */
  --r-sm:4px; --r-md:6px; --r-lg:10px;

  /* layout */
  --header-h: 40px;
  --sidebar-w-raw:   220px;
  --inspector-w-raw: 260px;
}

/* ═══════════════════════════════════════════
   RESET
   ═══════════════════════════════════════════ */
*, *::before, *::after { box-sizing: border-box; min-width: 0; }

body {
  margin: 0;
  font-family: var(--font-sans);
  background: var(--bg-canvas);
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.5;
  overflow: hidden;
}

/* ═══════════════════════════════════════════
   APP SHELL
   ═══════════════════════════════════════════ */
.app-shell {
  display: grid;
  grid-template-rows: var(--header-h) 1fr;
  height: 100vh;
  overflow: hidden;
}

/* ═══════════════════════════════════════════
   GLOBAL HEADER
   ═══════════════════════════════════════════ */
.app-header {
  background: var(--bg-default);
  border-bottom: 1px solid var(--border-default);
  display: flex;
  align-items: center;
  padding: 0 var(--sp-4);
  gap: var(--sp-3);
  height: var(--header-h);
  flex-shrink: 0;
}

.app-logo {
  color: var(--color-success);
  font-weight: 700;
  font-size: 13px;
  font-family: var(--font-mono);
  letter-spacing: -0.3px;
}

.mode-badge {
  border-radius: var(--r-sm);
  padding: 2px 8px;
  font-size: 11px;
  font-family: var(--font-mono);
  border: 1px solid;
}
.mode-badge.mode-explore { color: var(--color-info);    background: rgba(56,139,253,.1);  border-color: rgba(56,139,253,.25);  }
.mode-badge.mode-spec    { color: var(--color-accent);  background: rgba(188,140,255,.1); border-color: rgba(188,140,255,.25); }
.mode-badge.mode-code    { color: var(--color-success); background: rgba(63,185,80,.1);   border-color: rgba(63,185,80,.25);   }
.mode-badge.mode-debug   { color: var(--color-warning); background: rgba(210,153,34,.1);  border-color: rgba(210,153,34,.25);  }
.mode-badge.mode-verify  { color: #e3b341;              background: rgba(227,179,65,.1);  border-color: rgba(227,179,65,.25);  }

.header-right { margin-left: auto; display: flex; align-items: center; gap: var(--sp-3); }

.status-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--color-success);
  display: inline-block;
}
.status-dot.running,
.status-dot.waiting_permission  { background: var(--color-warning); }
.status-dot.waiting_user_input  { background: var(--color-info); }
.status-dot.error               { background: var(--color-error); }

.status-label { font-family: var(--font-mono); font-size: 11px; color: var(--color-warning); }
.status-label.idle  { color: var(--color-success); }
.status-label.error { color: var(--color-error); }

.meta-text { color: var(--text-muted); font-size: 11px; font-family: var(--font-mono); }

.ghost {
  background: none;
  border: 1px solid var(--border-default);
  border-radius: var(--r-sm);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 11px;
  padding: 3px 8px;
}
.ghost:hover { background: var(--bg-subtle); color: var(--text-primary); }

/* ═══════════════════════════════════════════
   WORKSPACE — 3-COLUMN RESIZABLE
   ═══════════════════════════════════════════ */
.workspace {
  display: grid;
  grid-template-columns:
    clamp(160px, var(--sidebar-w-raw),   360px)
    4px
    1fr
    4px
    clamp(200px, var(--inspector-w-raw), 480px);
  overflow: hidden;
}

.resize-handle {
  background: var(--bg-default);
  cursor: col-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  user-select: none;
  transition: background .15s;
}
.resize-handle:hover,
.resize-handle.dragging { background: rgba(56,139,253,.15); }

.resize-handle::after {
  content: '';
  width: 1px; height: 48px;
  background: var(--border-default);
  border-radius: 1px;
  transition: background .15s;
}
.resize-handle:hover::after,
.resize-handle.dragging::after { background: var(--color-info); }

/* ═══════════════════════════════════════════
   SIDEBAR
   ═══════════════════════════════════════════ */
.sidebar {
  background: var(--bg-default);
  border-right: 1px solid var(--bg-subtle);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-tabs { display: flex; border-bottom: 1px solid var(--border-default); flex-shrink: 0; }

.sidebar-tab {
  flex: 1; padding: 9px 0;
  font-size: 11px; color: var(--text-muted);
  background: none; border: none; cursor: pointer;
  text-align: center;
  border-bottom: 2px solid transparent; margin-bottom: -1px;
  transition: color .15s;
}
.sidebar-tab:hover { color: var(--text-secondary); }
.sidebar-tab.active { color: var(--text-primary); border-bottom-color: var(--color-success); }

.sidebar-content { flex: 1; overflow-y: auto; padding: var(--sp-2); }

.section-label {
  font-size: 9px; color: var(--text-muted);
  letter-spacing: .8px; text-transform: uppercase;
  padding: 6px var(--sp-2) 4px;
  font-family: var(--font-mono);
}

.session-item {
  padding: 5px 8px; border-radius: var(--r-sm);
  cursor: pointer; margin-bottom: 2px; overflow: hidden;
  border-left: 2px solid transparent;
}
.session-item:hover { background: var(--bg-subtle); }
.session-item.active { background: var(--bg-subtle); border-left-color: var(--color-success); }

.session-title {
  color: var(--text-primary); font-size: 11px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  font-family: var(--font-mono);
}
.session-meta { color: var(--text-muted); font-size: 9px; font-family: var(--font-mono); }

.file-tree { font-family: var(--font-mono); font-size: 11px; color: var(--text-secondary); padding: var(--sp-2); }
.file-tree-row { cursor: pointer; padding: 2px var(--sp-2); border-radius: var(--r-sm); }
.file-tree-row:hover { background: var(--bg-subtle); color: var(--text-link); }

/* ═══════════════════════════════════════════
   MAIN CHAT
   ═══════════════════════════════════════════ */
.main-chat {
  background: var(--bg-canvas);
  display: flex; flex-direction: column;
  overflow: hidden;
}

/* ═══════════════════════════════════════════
   TIMELINE
   ═══════════════════════════════════════════ */
.timeline {
  flex: 1; overflow-y: auto;
  padding: var(--sp-4);
  display: flex; flex-direction: column; gap: 10px;
}

.turn-group { display: flex; flex-direction: column; gap: 5px; }

.user-message {
  align-self: flex-end;
  background: var(--bg-subtle);
  border-left: 2px solid var(--border-default);
  border-radius: var(--r-md);
  padding: 7px 11px;
  color: var(--text-primary); font-size: 13px;
  max-width: 72%; word-break: break-word;
}

.assistant-message {
  border-left: 2px solid var(--color-success);
  padding: 6px 11px;
  color: var(--text-primary); font-size: 13px;
  line-height: 1.6; word-break: break-word;
}
.assistant-message p { margin: 0 0 6px; }
.assistant-message p:last-child { margin-bottom: 0; }
.assistant-message code {
  background: var(--bg-subtle);
  color: var(--color-success);
  padding: 1px 4px; border-radius: var(--r-sm);
  font-family: var(--font-mono); font-size: 11px;
}
.assistant-message pre {
  background: var(--bg-subtle);
  border: 1px solid var(--border-default);
  border-radius: var(--r-md);
  padding: var(--sp-3);
  overflow-x: auto;
}
.assistant-message pre code { background: none; padding: 0; }

/* Tool block — three states */
.tool-block {
  display: flex; align-items: center; gap: 7px;
  background: var(--bg-default);
  border-radius: var(--r-sm);
  padding: 5px 9px;
  font-family: var(--font-mono); font-size: 10px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: border-color .15s;
}
.tool-block.running { border-color: rgba(210,153,34,.3); }
.tool-block.success { border-color: rgba(63,185,80,.25); }
.tool-block.error   { border-color: rgba(248,81,73,.3);  }
.tool-block:hover   { border-color: var(--border-focus); }

.tool-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.tool-dot.running { background: var(--color-warning); }
.tool-dot.success { background: var(--color-success); }
.tool-dot.error   { background: var(--color-error);   }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: .4; }
}
.tool-dot.running { animation: pulse 1.2s ease-in-out infinite; }

.tool-name         { font-size: 10px; }
.tool-name.running { color: var(--color-warning); }
.tool-name.success { color: var(--color-success); }
.tool-name.error   { color: var(--color-error);   }

.tool-args  { color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.tool-meta  { color: var(--text-muted); margin-left: auto; flex-shrink: 0; white-space: nowrap; }
.tool-expand{ color: var(--color-error); flex-shrink: 0; font-size: 9px; margin-left: var(--sp-2); }

.tool-output {
  background: var(--bg-subtle);
  border: 1px solid var(--border-default);
  border-radius: var(--r-sm);
  padding: var(--sp-2) var(--sp-3);
  font-family: var(--font-mono); font-size: 10px;
  color: var(--text-secondary);
  white-space: pre-wrap; overflow-x: auto;
  max-height: 200px; overflow-y: auto;
  margin-top: 2px;
}

.system-message {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 8px;
  background: var(--bg-default);
  border: 1px solid var(--border-default);
  border-radius: var(--r-sm);
  font-size: 10px; color: var(--text-secondary);
  font-family: var(--font-mono);
}

@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
.stream-cursor {
  display: inline-block; width: 2px; height: 12px;
  background: var(--color-success); margin-left: 2px;
  vertical-align: middle;
  animation: blink 1s step-end infinite;
}

/* ═══════════════════════════════════════════
   INSPECTOR
   ═══════════════════════════════════════════ */
.inspector {
  background: var(--bg-default);
  border-left: 1px solid var(--bg-subtle);
  display: flex; flex-direction: column;
  overflow: hidden;
  position: relative;
}

.inspector-tabs {
  display: flex; align-items: center;
  border-bottom: 1px solid var(--border-default);
  padding: 0 var(--sp-2);
  flex-shrink: 0;
}

.insp-tab {
  padding: 9px 8px;
  font-size: 10px; color: var(--text-muted);
  cursor: pointer; white-space: nowrap;
  font-family: var(--font-mono);
  background: none; border: none;
  border-bottom: 2px solid transparent; margin-bottom: -1px;
}
.insp-tab:hover { color: var(--text-secondary); }
.insp-tab.active { color: var(--color-success); border-bottom-color: var(--color-success); }

.tab-badge {
  background: var(--color-success); color: var(--bg-canvas);
  border-radius: 8px; padding: 0 4px;
  font-size: 8px; font-weight: bold; margin-left: 3px;
}

.more-tab-btn {
  margin-left: auto;
  background: var(--bg-subtle); color: var(--text-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--r-sm);
  padding: 3px 7px; font-size: 10px; cursor: pointer;
  flex-shrink: 0;
}
.more-tab-btn:hover { background: var(--bg-canvas); }

.tab-overflow-menu {
  position: absolute; right: var(--sp-2); top: 40px;
  background: var(--bg-default);
  border: 1px solid var(--border-default);
  border-radius: var(--r-md);
  padding: var(--sp-1); z-index: 100;
  min-width: 130px;
  box-shadow: 0 4px 16px rgba(0,0,0,.5);
}
.overflow-menu-item {
  display: block; width: 100%;
  padding: 6px 10px; font-size: 11px;
  color: var(--text-secondary);
  background: none; border: none;
  cursor: pointer; text-align: left;
  border-radius: var(--r-sm);
  font-family: var(--font-mono);
}
.overflow-menu-item:hover { background: var(--bg-subtle); color: var(--text-primary); }

.inspector-body { flex: 1; overflow-y: auto; padding: var(--sp-3); }

/* Inspector panels */
.todo-item { display: flex; align-items: flex-start; gap: 7px; padding: 5px 7px; border-radius: var(--r-sm); }
.todo-item:hover { background: var(--bg-subtle); }
.todo-check { width:13px;height:13px;border-radius:3px;border:1px solid var(--border-default);flex-shrink:0;margin-top:2px; }
.todo-check.done { background:rgba(63,185,80,.2);border-color:var(--color-success); }
.todo-text { color: var(--text-primary); font-size: 12px; }
.todo-text.done { color: var(--text-muted); text-decoration: line-through; }

.artifact-item {
  padding: 7px var(--sp-2); border-radius: var(--r-sm); cursor: pointer;
  border: 1px solid var(--border-default); margin-bottom: var(--sp-2);
  background: var(--bg-subtle);
}
.artifact-item:hover { border-color: var(--color-info); }

.plan-block {
  background: rgba(188,140,255,.07);
  border: 1px solid rgba(188,140,255,.2);
  border-radius: var(--r-md);
  padding: var(--sp-2) var(--sp-3);
  font-family: var(--font-mono); font-size: 11px;
  color: var(--text-primary); line-height: 1.7;
}

.log-entry {
  display: flex; gap: var(--sp-2);
  padding: 3px 0; border-bottom: 1px solid var(--bg-subtle);
  font-family: var(--font-mono); font-size: 9px;
}
.log-time { color: var(--text-muted); flex-shrink: 0; }
.log-msg  { color: var(--text-secondary); }
.log-msg.success { color: var(--color-success); }
.log-msg.error   { color: var(--color-error); }

/* Inspector user input prompt */
.prompt-panel {
  background: var(--bg-subtle);
  border: 1px solid var(--border-default);
  border-radius: var(--r-md);
  padding: var(--sp-3);
}
.option-card {
  display: flex; flex-direction: column;
  width: 100%; text-align: left;
  background: var(--bg-default); color: var(--text-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--r-sm); padding: var(--sp-2) var(--sp-3);
  cursor: pointer; margin-bottom: var(--sp-1); font-size: 12px;
}
.option-card:hover { border-color: var(--color-info); }

/* ═══════════════════════════════════════════
   COMPOSER
   ═══════════════════════════════════════════ */
.composer {
  border-top: 1px solid var(--border-default);
  padding: var(--sp-3) var(--sp-3) var(--sp-2);
  background: var(--bg-canvas); flex-shrink: 0;
}

.composer-inner {
  display: flex; align-items: flex-end; gap: var(--sp-2);
  background: var(--bg-default);
  border: 1px solid var(--border-default);
  border-radius: var(--r-md); padding: 7px 10px;
  transition: border-color .15s;
}
.composer-inner:focus-within { border-color: var(--border-focus); }

.composer-mode-badge {
  border-radius: 3px; padding: 1px 6px;
  font-size: 9px; font-family: var(--font-mono);
  flex-shrink: 0; align-self: center;
  border: 1px solid;
}
.composer-mode-badge.mode-explore { color:var(--color-info);    background:rgba(56,139,253,.1);  border-color:rgba(56,139,253,.25);  }
.composer-mode-badge.mode-spec    { color:var(--color-accent);  background:rgba(188,140,255,.1); border-color:rgba(188,140,255,.25); }
.composer-mode-badge.mode-code    { color:var(--color-success); background:rgba(63,185,80,.1);   border-color:rgba(63,185,80,.25);   }
.composer-mode-badge.mode-debug   { color:var(--color-warning); background:rgba(210,153,34,.1);  border-color:rgba(210,153,34,.25);  }
.composer-mode-badge.mode-verify  { color:#e3b341;              background:rgba(227,179,65,.1);  border-color:rgba(227,179,65,.25);  }

.composer textarea {
  flex: 1; background: none; border: none; outline: none;
  color: var(--text-primary); font-family: var(--font-sans);
  font-size: 13px; resize: none;
  min-height: 20px; max-height: 160px;
  padding: 0; line-height: 1.5;
}
.composer textarea::placeholder { color: var(--text-muted); }
.composer textarea:disabled      { opacity: .5; cursor: not-allowed; }

.composer-hint-bar { display: flex; gap: var(--sp-3); margin-top: var(--sp-1); padding: 0 2px; }
.hint-text { color: var(--text-muted); font-size: 9px; font-family: var(--font-mono); }
.hint-text.running-hint { color: var(--color-warning); margin-left: auto; }

.composer-hints {
  position: absolute; bottom: 100%; left: 0; right: 0;
  background: var(--bg-default);
  border: 1px solid var(--border-default);
  border-radius: var(--r-md);
  padding: var(--sp-1); margin-bottom: 4px;
  max-height: 180px; overflow-y: auto;
  z-index: 50;
}
.composer-hint {
  display: block; width: 100%;
  padding: 5px 10px; text-align: left;
  color: var(--text-secondary); font-family: var(--font-mono); font-size: 12px;
  background: none; border: none; cursor: pointer;
  border-radius: var(--r-sm);
}
.composer-hint:hover { background: var(--bg-subtle); color: var(--text-primary); }

.send {
  background: none;
  border: 1px solid var(--color-success); border-radius: var(--r-sm);
  color: var(--color-success); cursor: pointer;
  font-size: 11px; padding: 4px 10px; flex-shrink: 0;
}
.send:hover    { background: rgba(63,185,80,.1); }
.send:disabled { opacity: .4; cursor: not-allowed; }

.stop {
  background: rgba(248,81,73,.1);
  border: 1px solid rgba(248,81,73,.4); border-radius: var(--r-sm);
  color: var(--color-error); cursor: pointer;
  font-size: 11px; padding: 4px 10px; flex-shrink: 0;
}
.stop:hover { background: rgba(248,81,73,.2); }

/* ═══════════════════════════════════════════
   PERMISSION MODAL
   ═══════════════════════════════════════════ */
.permission-modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(0,0,0,.6);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}
.modal-box {
  background: var(--bg-default);
  border: 1px solid var(--border-default);
  border-radius: var(--r-lg);
  padding: var(--sp-6); min-width: 380px; max-width: 520px;
  box-shadow: 0 8px 32px rgba(0,0,0,.5);
}
.primary {
  background: var(--color-success); color: var(--bg-canvas);
  border: none; border-radius: var(--r-sm);
  padding: 6px 14px; cursor: pointer; font-size: 12px;
}
.primary:hover { opacity: .85; }

/* ═══════════════════════════════════════════
   DIFF VIEW
   ═══════════════════════════════════════════ */
.diff-view { font-family: var(--font-mono); font-size: 11px; overflow: auto; }
.diff-add { color: var(--color-diff-add); background: rgba(63,185,80,.08); }
.diff-del { color: var(--color-diff-del); background: rgba(248,81,73,.08); }

/* ═══════════════════════════════════════════
   SCROLLBAR
   ═══════════════════════════════════════════ */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-default); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
```

- [ ] **Step 3: 确认文件已更新**

```bash
head -5 src/styles.css
```
Expected: 看到 `DESIGN TOKENS — GitHub Dark System`

- [ ] **Step 4: Commit**

```bash
cd d:/Project/coding_agent
git add src/embedagent/frontend/gui/webapp/src/styles.css
git commit -m "style: replace warm parchment CSS with GitHub dark design token system"
```

---

## Task 2: App Shell 重构 — 全局 Header + 三列布局

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx` (JSX render section, lines 564–705)

App.jsx 当前 render 返回 `.shell` 包含 Sidebar + `.chat-shell` + Inspector。需要改为 `.app-shell` > `.app-header` + `.workspace`。StatusBar 组件（lines 687–705）内容合并到 `.app-header`。

- [ ] **Step 1: 将 App.jsx render 函数 (lines 564–683) 替换为新结构**

找到 `return (` 开始的第 564 行，将整个 return 块替换为：

```jsx
  return (
    <LangContext.Provider value={state.lang}>
    <div className="app-shell">
      {/* ── Global Header ── */}
      <header className="app-header">
        <span className="app-logo">EmbedAgent</span>
        <span className={`mode-badge mode-${currentMode}`}>{currentMode}</span>
        <div className="header-right">
          <span className={`status-dot ${currentStatus}`} title={currentStatus} />
          <span className={`status-label ${currentStatus === "idle" ? "idle" : currentStatus === "error" ? "error" : ""}`}>
            {currentStatus}
          </span>
          {state.currentSessionId && (
            <span className="meta-text">{state.currentSessionId.slice(0, 8)}</span>
          )}
          {state.turnsUsed > 0 && (
            <span className="meta-text">turns {state.turnsUsed}/{state.maxTurns}</span>
          )}
          <button className="ghost" onClick={loadSessions} aria-label={t("header.refresh", state.lang)}>
            {t("header.refresh", state.lang)}
          </button>
          <button
            className="ghost lang-toggle"
            onClick={() => dispatch({ type: "set_lang", value: state.lang === "en" ? "zh" : "en" })}
            aria-label="Toggle language"
          >
            {t("lang.toggle", state.lang)}
          </button>
          <button
            className={`ghost inspector-toggle${state.inspectorOpen ? " active" : ""}`}
            onClick={() => dispatch({ type: "toggle_inspector" })}
            title={t("header.toggleInspector", state.lang)}
            aria-pressed={state.inspectorOpen}
          >
            ⊞
          </button>
        </div>
      </header>

      {/* ── Workspace ── */}
      <div className="workspace">
        <Sidebar
          sidebarTab={state.sidebarTab}
          sessions={sessionCards}
          currentSessionId={state.currentSessionId}
          fileTree={state.fileTree}
          treeHeight={treeHeight}
          currentMode={currentMode}
          onTabChange={(v) => dispatch({ type: "set_sidebar", value: v })}
          onLoadSession={loadSession}
          onCreateSession={createSession}
          onOpenFile={openFile}
          onLoadFileChildren={loadFileChildren}
        />

        <div
          className="resize-handle"
          onMouseDown={(e) => startResize(e, "--sidebar-w-raw", 1)}
          aria-hidden="true"
        />

        <main className="main-chat">
          <Timeline
            ref={timelineRef}
            timeline={state.timeline}
            toolCatalog={state.toolCatalog}
            thinkingActive={state.thinkingActive}
            streamingReasoningId={state.streamingReasoningId}
            terminationReason={state.terminationReason}
            turnsUsed={state.turnsUsed}
            maxTurns={state.maxTurns}
            userAnswer={userAnswer}
            onUserAnswerChange={setUserAnswer}
            onSubmitUserInput={sendUserInputResponse}
            onPermissionResponse={sendInlinePermissionResponse}
            onScroll={handleTimelineScroll}
          />
          <Composer
            value={state.composer}
            onChange={(v) => dispatch({ type: "set_composer", value: v })}
            onSend={sendMessage}
            onStop={cancelSession}
            isRunning={currentStatus === "running" || currentStatus === "waiting_user_input"}
            currentMode={currentMode}
            commandHints={SLASH_COMMAND_HINTS}
          />
        </main>

        <div
          className="resize-handle"
          onMouseDown={(e) => startResize(e, "--inspector-w-raw", -1)}
          aria-hidden="true"
        />

        {state.inspectorOpen ? (
          <Inspector
            inspectorTab={state.inspectorTab}
            todos={state.todos}
            artifacts={state.artifacts}
            plan={state.plan}
            review={state.review}
            permissionContext={state.permissionContext}
            preview={state.preview}
            userInput={state.userInput}
            userAnswer={userAnswer}
            eventLog={state.eventLog}
            onTabChange={(v) => dispatch({ type: "set_inspector", value: v })}
            onOpenArtifact={openArtifact}
            onOpenReviewEvidence={openReviewEvidence}
            onUserAnswerChange={setUserAnswer}
            onSubmitUserInput={sendUserInputResponse}
          />
        ) : (
          <div style={{ background: "var(--bg-default)", borderLeft: "1px solid var(--bg-subtle)" }} />
        )}
      </div>

      <PermissionModal
        permission={state.permission}
        onApprove={(remember, category) => sendPermissionResponse(true, remember, category)}
        onDeny={(remember, category) => sendPermissionResponse(false, remember, category)}
      />
    </div>
    </LangContext.Provider>
  );
```

- [ ] **Step 2: 删除旧 StatusBar 组件定义（lines 687–705）**

删除文件末尾的 `function StatusBar(...)` 整个函数定义（它已被 `app-header` 取代）。

- [ ] **Step 3: 删除旧 treeHeight resize effect（line 46–51）**

该 effect 为旧侧边栏计算高度，新布局中 sidebar 用 flex+overflow-y:auto 自动填充。删除：

```javascript
  // 删除这段（lines 46-51）:
  useEffect(() => {
    const update = () => setTreeHeight(Math.max(window.innerHeight - 180, 360));
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);
```

同时删除 `const [treeHeight, setTreeHeight] = useState(640);`（line 35）。

- [ ] **Step 4: 在 App 函数内（任意 useEffect 后）添加 startResize 函数**

```javascript
  function startResize(e, cssVar, direction) {
    e.preventDefault();
    const handle = e.currentTarget;
    handle.classList.add("dragging");
    const startX = e.clientX;
    const startVal = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue(cssVar).trim()
    ) || (cssVar === "--sidebar-w-raw" ? 220 : 260);

    function onMove(ev) {
      const delta = (ev.clientX - startX) * direction;
      const newVal = Math.max(160, Math.min(480, startVal + delta));
      document.documentElement.style.setProperty(cssVar, `${newVal}px`);
    }
    function onUp() {
      handle.classList.remove("dragging");
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }
```

- [ ] **Step 5: 构建确认无语法错误**

```bash
cd d:/Project/coding_agent/src/embedagent/frontend/gui/webapp
npm run build 2>&1 | tail -20
```
Expected: `✓` 或 `Build complete` 无 error

- [ ] **Step 6: Commit**

```bash
cd d:/Project/coding_agent
git add src/embedagent/frontend/gui/webapp/src/App.jsx
git commit -m "feat: restructure app shell to 3-column resizable layout with global header"
```

---

## Task 3: Timeline — 工具块三态展示

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx`

- [ ] **Step 1: 找到当前工具行渲染位置**

```bash
grep -n "tool\|ToolBlock\|tool_block\|status.*running\|status.*success\|status.*error" \
  src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx | head -30
```

- [ ] **Step 2: 在 Timeline.jsx 顶部（import 之后）添加 ToolBlock 组件**

在第一个 `function` 或 `export default` 前插入：

```jsx
function ToolBlock({ item }) {
  const [expanded, setExpanded] = React.useState(item.status === "error");
  const status = item.status || "running"; // "running" | "success" | "error"

  // Build display args string from item.arguments
  const argsStr = React.useMemo(() => {
    const args = item.arguments || {};
    const skip = new Set(["_tool_label","_permission_category","_supports_diff_preview",
                          "_progress_renderer_key","_result_renderer_key"]);
    const vals = Object.entries(args)
      .filter(([k]) => !skip.has(k))
      .map(([, v]) => (typeof v === "string" ? v : JSON.stringify(v)));
    return vals.join("  ").slice(0, 80);
  }, [item.arguments]);

  const metaStr = React.useMemo(() => {
    if (status === "running") return "running...";
    if (status === "success") {
      const ms = item.executionTimeMs;
      const summary = item.resultSummary || "";
      return [summary, ms != null ? `${ms}ms` : ""].filter(Boolean).join(" · ").slice(0, 60) || "done";
    }
    // error
    const ms = item.executionTimeMs;
    return `error${ms != null ? ` · ${ms}ms` : ""}`;
  }, [status, item]);

  const hasOutput = item.error || (item.resultData && typeof item.resultData === "string");

  return (
    <div>
      <div
        className={`tool-block ${status}`}
        onClick={() => hasOutput && setExpanded((v) => !v)}
        title={item.toolName}
      >
        <span className={`tool-dot ${status}`} />
        <span className={`tool-name ${status}`}>{item.label || item.toolName}</span>
        {argsStr && <span className="tool-args">{argsStr}</span>}
        <span className="tool-meta">{metaStr}</span>
        {status === "error" && hasOutput && (
          <span className="tool-expand">{expanded ? "▾" : "▸"}</span>
        )}
      </div>
      {expanded && hasOutput && (
        <div className="tool-output">
          {item.error || item.resultData}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: 在 Timeline.jsx 中找到工具项渲染，用 ToolBlock 替换**

定位当前渲染 `kind === "tool"` 或类似工具项的代码（通过 Step 1 的 grep 结果定位），将其替换为：

```jsx
{item.kind === "tool" && <ToolBlock item={item} />}
```

- [ ] **Step 4: 为流式助手消息添加光标**

定位渲染 assistant streaming 消息处。在流式末尾添加：

```jsx
{item.id === streamingAssistantId && (
  <span className="stream-cursor" aria-hidden="true" />
)}
```

- [ ] **Step 5: 构建验证**

```bash
cd d:/Project/coding_agent/src/embedagent/frontend/gui/webapp
npm run build 2>&1 | tail -10
```
Expected: 无 error

- [ ] **Step 6: Commit**

```bash
cd d:/Project/coding_agent
git add src/embedagent/frontend/gui/webapp/src/components/Timeline.jsx
git commit -m "feat: timeline tool blocks with running/success/error three-state display"
```

---

## Task 4: Inspector — Tab 溢出菜单 + Badge 数字

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx`

当前：7 个平铺 tab（lines 27–46），宽 260px 时溢出。
目标：3 个常驻 tab（Todos/Plan/Artifacts）+ `···` 弹出菜单包含其余 4 个。

- [ ] **Step 1: 替换 Inspector 的 tabs div（lines 26–47）**

将：
```jsx
      <div className="inspector-tabs" role="tablist">
        {[
          ["todos", t("inspector.todos", lang)],
          ...
          ["log", t("inspector.log", lang)],
        ].map(([id, label]) => (
          <button ... />
        ))}
      </div>
```

替换为：

```jsx
      <InspectorTabs
        active={inspectorTab}
        onChange={onTabChange}
        todosCount={todos.length}
        artifactsCount={artifacts.length}
        lang={lang}
      />
```

- [ ] **Step 2: 在 Inspector.jsx 顶部（imports 后）添加 InspectorTabs 组件**

```jsx
const PRIMARY_TABS = ["todos", "plan", "artifacts"];
const OVERFLOW_TABS = ["review", "permissions", "preview", "log"];

function InspectorTabs({ active, onChange, todosCount, artifactsCount, lang }) {
  const [overflowOpen, setOverflowOpen] = React.useState(false);
  const overflowRef = React.useRef(null);

  // Close overflow menu when clicking outside
  React.useEffect(() => {
    if (!overflowOpen) return;
    function onDoc(e) {
      if (overflowRef.current && !overflowRef.current.contains(e.target)) {
        setOverflowOpen(false);
      }
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [overflowOpen]);

  const badges = { todos: todosCount, artifacts: artifactsCount };

  return (
    <div className="inspector-tabs" role="tablist">
      {PRIMARY_TABS.map((id) => (
        <button
          key={id}
          role="tab"
          aria-selected={active === id}
          className={`insp-tab${active === id ? " active" : ""}`}
          onClick={() => onChange(id)}
        >
          {t(`inspector.${id}`, lang)}
          {badges[id] > 0 && <span className="tab-badge">{badges[id]}</span>}
        </button>
      ))}
      <div ref={overflowRef} style={{ marginLeft: "auto", position: "relative" }}>
        <button
          className="more-tab-btn"
          onClick={() => setOverflowOpen((v) => !v)}
          aria-label="More tabs"
        >
          {OVERFLOW_TABS.includes(active)
            ? t(`inspector.${active}`, lang) + " ···"
            : "···"}
        </button>
        {overflowOpen && (
          <div className="tab-overflow-menu" role="menu">
            {OVERFLOW_TABS.map((id) => (
              <button
                key={id}
                role="menuitem"
                className="overflow-menu-item"
                onClick={() => { onChange(id); setOverflowOpen(false); }}
              >
                {t(`inspector.${id}`, lang)}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 构建验证**

```bash
cd d:/Project/coding_agent/src/embedagent/frontend/gui/webapp
npm run build 2>&1 | tail -10
```
Expected: 无 error

- [ ] **Step 4: Commit**

```bash
cd d:/Project/coding_agent
git add src/embedagent/frontend/gui/webapp/src/components/Inspector.jsx
git commit -m "feat: inspector tab overflow menu (3 primary + ··· dropdown) with badge counts"
```

---

## Task 5: Composer — 模式徽章 + 运行中禁用提示

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/components/Composer.jsx`

当前：`Composer({ value, onChange, onSend, onStop, isRunning, commandHints })` — 缺少 `currentMode` prop 和提示栏。

- [ ] **Step 1: 完整替换 Composer.jsx 内容**

```jsx
import React from "react";
import { useLang } from "../LangContext.js";
import { t } from "../strings.js";

export default function Composer({
  value,
  onChange,
  onSend,
  onStop,
  isRunning,
  currentMode,
  commandHints = [],
}) {
  const lang = useLang();
  const showHints = !isRunning && value.trim().startsWith("/");
  const hints = showHints
    ? commandHints
        .filter((item) =>
          item.startsWith(value.trim().slice(1) ? `/${value.trim().slice(1)}` : "/")
        )
        .slice(0, 6)
    : [];

  return (
    <footer className="composer">
      <div className="composer-inner" style={{ position: "relative" }}>
        {currentMode && (
          <span className={`composer-mode-badge mode-${currentMode}`}>
            {currentMode}
          </span>
        )}
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (!isRunning) onSend();
            }
          }}
          placeholder={t("composer.placeholder", lang)}
          aria-label={t("composer.placeholder", lang)}
          disabled={isRunning}
          rows={1}
        />
        {hints.length > 0 && (
          <div className="composer-hints" role="listbox" aria-label="Slash command suggestions">
            {hints.map((item) => (
              <button
                key={item}
                className="composer-hint"
                onClick={() => onChange(`${item} `)}
              >
                {item}
              </button>
            ))}
          </div>
        )}
        {isRunning ? (
          <button className="stop" onClick={onStop} aria-label={t("composer.stop", lang)}>
            {t("composer.stop", lang)}
          </button>
        ) : (
          <button
            className="send"
            onClick={onSend}
            disabled={!value.trim()}
            aria-label={t("composer.send", lang)}
          >
            ↵
          </button>
        )}
      </div>
      <div className="composer-hint-bar" aria-hidden="true">
        <span className="hint-text">/ 命令</span>
        <span className="hint-text">↑↓ 历史</span>
        <span className="hint-text">Shift+Enter 换行</span>
        {isRunning && (
          <span className="hint-text running-hint">● running 时禁用</span>
        )}
      </div>
    </footer>
  );
}
```

- [ ] **Step 2: 构建验证**

```bash
cd d:/Project/coding_agent/src/embedagent/frontend/gui/webapp
npm run build 2>&1 | tail -10
```
Expected: 无 error

- [ ] **Step 3: Commit**

```bash
cd d:/Project/coding_agent
git add src/embedagent/frontend/gui/webapp/src/components/Composer.jsx
git commit -m "feat: composer mode badge, running-state hint bar, send disabled when empty"
```

---

## Task 6: 后端同步推送（TDD）

**Files:**
- Create: `tests/test_gui_sync.py`
- Modify: `src/embedagent/protocol/__init__.py` (line ~229, after `on_plan_updated`)
- Modify: `src/embedagent/core/adapter.py` (after line 88, inside `tool_finished` branch)
- Modify: `src/embedagent/frontend/gui/backend/server.py` (after `on_tool_finish`)

### Step A: 先写测试（TDD）

- [ ] **Step 1: 创建测试文件**

新建 `tests/test_gui_sync.py`：

```python
"""Tests for GUI real-time sync callbacks: todos_refresh and artifacts_refresh."""
import pytest
from unittest.mock import MagicMock


def test_websocket_frontend_has_on_todos_refresh():
    from embedagent.frontend.gui.backend.server import WebSocketFrontend
    assert hasattr(WebSocketFrontend, "on_todos_refresh"), \
        "WebSocketFrontend must have on_todos_refresh method"


def test_websocket_frontend_has_on_artifacts_refresh():
    from embedagent.frontend.gui.backend.server import WebSocketFrontend
    assert hasattr(WebSocketFrontend, "on_artifacts_refresh"), \
        "WebSocketFrontend must have on_artifacts_refresh method"


def test_on_todos_refresh_dispatches_correct_type():
    from embedagent.frontend.gui.backend.server import WebSocketFrontend
    frontend = WebSocketFrontend()
    dispatched = []
    frontend._dispatch_message = lambda msg: dispatched.append(msg) or True
    frontend.on_todos_refresh()
    assert len(dispatched) == 1
    assert dispatched[0]["type"] == "todos_refresh"


def test_on_artifacts_refresh_dispatches_correct_type():
    from embedagent.frontend.gui.backend.server import WebSocketFrontend
    frontend = WebSocketFrontend()
    dispatched = []
    frontend._dispatch_message = lambda msg: dispatched.append(msg) or True
    frontend.on_artifacts_refresh()
    assert len(dispatched) == 1
    assert dispatched[0]["type"] == "artifacts_refresh"


def test_callback_bridge_calls_todos_refresh_for_manage_todos():
    from embedagent.core.adapter import CallbackBridge
    mock_frontend = MagicMock()
    bridge = CallbackBridge(mock_frontend)
    bridge.emit("tool_finished", "session-1", {
        "tool_name": "manage_todos",
        "success": True,
        "data": {},
        "call_id": "call-1",
    })
    mock_frontend.on_todos_refresh.assert_called_once()


def test_callback_bridge_calls_artifacts_refresh_for_write_file():
    from embedagent.core.adapter import CallbackBridge
    mock_frontend = MagicMock()
    bridge = CallbackBridge(mock_frontend)
    bridge.emit("tool_finished", "session-1", {
        "tool_name": "write_file",
        "success": True,
        "data": {},
        "call_id": "call-2",
    })
    mock_frontend.on_artifacts_refresh.assert_called_once()


def test_callback_bridge_calls_artifacts_refresh_for_edit_file():
    from embedagent.core.adapter import CallbackBridge
    mock_frontend = MagicMock()
    bridge = CallbackBridge(mock_frontend)
    bridge.emit("tool_finished", "session-1", {
        "tool_name": "edit_file",
        "success": True,
        "data": {},
        "call_id": "call-3",
    })
    mock_frontend.on_artifacts_refresh.assert_called_once()


def test_callback_bridge_does_not_call_refresh_for_unrelated_tool():
    from embedagent.core.adapter import CallbackBridge
    mock_frontend = MagicMock()
    bridge = CallbackBridge(mock_frontend)
    bridge.emit("tool_finished", "session-1", {
        "tool_name": "read_file",
        "success": True,
        "data": {},
        "call_id": "call-4",
    })
    mock_frontend.on_todos_refresh.assert_not_called()
    mock_frontend.on_artifacts_refresh.assert_not_called()
```

- [ ] **Step 2: 运行测试，确认全部失败（TDD red）**

```bash
cd d:/Project/coding_agent
python -m pytest tests/test_gui_sync.py -v 2>&1 | tail -20
```
Expected: 所有测试 `FAILED`（方法不存在）

### Step B: 添加 Protocol 签名

- [ ] **Step 3: 在 `protocol/__init__.py` 的 `on_plan_updated` 方法（line 228）后追加**

```python
    def on_todos_refresh(self) -> None:
        """通知前端刷新 todos 列表"""
        ...

    def on_artifacts_refresh(self) -> None:
        """通知前端刷新 artifacts 列表"""
        ...
```

### Step C: 添加 server.py 实现

- [ ] **Step 4: 在 `server.py` 的 `on_tool_finish` 方法（line 130）后追加**

```python
    def on_todos_refresh(self) -> None:
        self._dispatch_message({"type": "todos_refresh"})

    def on_artifacts_refresh(self) -> None:
        self._dispatch_message({"type": "artifacts_refresh"})
```

### Step D: 添加 adapter.py 触发逻辑

- [ ] **Step 5: 在 `adapter.py` 的 `tool_finished` 分支（line 88，`self.frontend.on_tool_finish(result)` 之后）追加**

```python
            # Sync push: notify frontend to refetch related data
            _TODOS_TOOLS = {"manage_todos"}
            _ARTIFACT_TOOLS = {"write_file", "edit_file"}
            tool_name = payload.get("tool_name", "")
            if tool_name in _TODOS_TOOLS and hasattr(self.frontend, "on_todos_refresh"):
                self.frontend.on_todos_refresh()
            if tool_name in _ARTIFACT_TOOLS and hasattr(self.frontend, "on_artifacts_refresh"):
                self.frontend.on_artifacts_refresh()
```

- [ ] **Step 6: 运行测试，确认全部通过（TDD green）**

```bash
cd d:/Project/coding_agent
python -m pytest tests/test_gui_sync.py -v 2>&1 | tail -20
```
Expected: 8 tests `PASSED`

- [ ] **Step 7: Commit**

```bash
git add tests/test_gui_sync.py \
        src/embedagent/protocol/__init__.py \
        src/embedagent/core/adapter.py \
        src/embedagent/frontend/gui/backend/server.py
git commit -m "feat: add todos_refresh and artifacts_refresh sync push callbacks with tests"
```

---

## Task 7: 前端同步 Handler

**Files:**
- Modify: `src/embedagent/frontend/gui/webapp/src/App.jsx` (handleSocketMessage function, ~line 284)

- [ ] **Step 1: 在 `handleSocketMessage` 函数末尾（`if (type === "message" && ...` 之后）追加两个新 handler**

```javascript
    if (type === "todos_refresh") {
      if (state.currentSessionId) loadTodos(state.currentSessionId);
      return;
    }
    if (type === "artifacts_refresh") {
      loadArtifacts();
      return;
    }
```

- [ ] **Step 2: 在 `tool_finish` handler 末尾（`logEvent(...)` 之后，`return;` 之前）添加文件树 refetch**

找到 `if (type === "tool_finish") {` 块，在其 `return;` 语句前插入：

```javascript
      const FS_TOOLS = ["write_file", "edit_file", "git_commit", "git_reset"];
      if (FS_TOOLS.includes(data.tool_name || "")) {
        loadFileChildren(".");
      }
```

- [ ] **Step 3: 运行前端测试，确认已有测试不受影响**

```bash
cd d:/Project/coding_agent/src/embedagent/frontend/gui/webapp
npm test 2>&1
```
Expected: `frontend helper checks passed`

- [ ] **Step 4: 构建验证**

```bash
npm run build 2>&1 | tail -10
```
Expected: 无 error

- [ ] **Step 5: Commit**

```bash
cd d:/Project/coding_agent
git add src/embedagent/frontend/gui/webapp/src/App.jsx
git commit -m "feat: frontend handles todos_refresh, artifacts_refresh, and fs-tool file tree refetch"
```

---

## Task 8: 全量构建与冒烟验证

**Files:** none (verification only)

- [ ] **Step 1: 运行所有 Python 测试**

```bash
cd d:/Project/coding_agent
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: 所有现有测试 + `test_gui_sync.py` 8条 PASSED，无 FAILED

- [ ] **Step 2: 前端最终构建**

```bash
cd src/embedagent/frontend/gui/webapp
npm run build 2>&1
```
Expected: 输出 `../static/assets/app.js` 和 `../static/assets/app.css`

- [ ] **Step 3: 验证静态文件存在**

```bash
ls -lh ../static/assets/
```
Expected: 看到 `app.js` 和 `app.css`

- [ ] **Step 4: 启动 GUI 验证布局（手动）**

```bash
cd d:/Project/coding_agent
python -m embedagent --gui --workspace .
```

打开 GUI 后检查：
- [ ] 窗口整体背景为 `#0d1117` 深色
- [ ] 顶部 40px header 显示 EmbedAgent logo + 模式徽章 + 状态
- [ ] 三列可见，无内容溢出到窗口外
- [ ] 拖拽分隔线可调整 sidebar/inspector 宽度（限制在 160–360px）
- [ ] Inspector tab 显示 Todos/Plan/Artifacts + `···` 菜单
- [ ] Composer 左侧显示当前模式徽章

- [ ] **Step 5: 发送一条消息，验证同步**

在 GUI 中发送一条消息触发工具执行，确认：
- [ ] 工具块显示 running（黄点脉冲）→ success（绿点）或 error（红点+展开）
- [ ] session_finished 后 Todos tab badge 数字更新
- [ ] 文件写入操作后侧边栏文件树自动刷新

- [ ] **Step 6: 最终 Commit**

```bash
cd d:/Project/coding_agent
git add -A
git status  # 确认无意外文件
git commit -m "chore: final GUI redesign — GitHub dark theme, resizable layout, real-time sync"
```

---

## 自检：Spec 覆盖

| Spec 要求 | 对应 Task |
|-----------|-----------|
| GitHub dark CSS token 体系 | Task 1 |
| 可拖拽三列布局（CSS clamp） | Task 2 |
| 全局 Header（logo/模式/状态）| Task 2 |
| 防溢出三原则 | Task 1 (CSS) |
| Timeline 工具块三态 | Task 3 |
| Inspector 3+溢出 tab | Task 4 |
| Composer 模式徽章 + running 禁用 | Task 5 |
| 协议新增 on_todos/artifacts_refresh | Task 6 |
| 后端 dispatch refresh 信号 | Task 6 |
| adapter tool_finished 触发 | Task 6 |
| 前端 WS handler todos/artifacts | Task 7 |
| 文件树 tool_finished refetch | Task 7 |
| 布局/色彩/同步验证计划 | Task 8 |
