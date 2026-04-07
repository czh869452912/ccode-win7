# GUI 全面迭代设计规范

**日期：** 2026-04-01  
**范围：** `src/embedagent/frontend/gui/webapp/`（React/PyWebView 前端）  
**方案：** 方案 B — 设计系统重建  

---

## 背景与动机

当前 GUI 存在三类系统性问题：

1. **面板不同步**：Inspector（Todos/Plan/Artifacts）和 Sidebar 文件树只在会话激活时加载一次，Agent 执行工具后不自动更新。
2. **布局溢出**：3 列固定宽度（300px + fluid + 340px）共 640px 固定，在常见窗口尺寸下大量卡片和 tab 飞出容器边界。
3. **色彩可读性差**：`--muted: #7b6857` 在 `#f5f0e8` 背景上对比度仅 3.8:1（不达 WCAG AA 标准 4.5:1），暗色模式下对比度问题更严重。

同时参考 Claude Code 源码设计，融入其工具状态展示、流式渲染、状态感知输入等核心交互模式。

---

## 设计决策

| 维度 | 决策 |
|------|------|
| 视觉风格 | GitHub Dark（#0d1117 底色，语义化 token） |
| 布局 | 可拖拽三列（CSS 变量 + clamp 约束） |
| 数据同步 | 后端 push（todos/artifacts）+ 前端 tool_finished 后 refetch 文件树 |
| 参考来源 | Claude Code 工具 block 三态、模式感知 Composer、顶部状态 header |

---

## 一、设计 Token 系统

### 背景色层级

```css
--bg-canvas:   #0d1117;   /* 窗口底色 */
--bg-default:  #161b22;   /* 面板底色（sidebar、inspector、header） */
--bg-subtle:   #21262d;   /* 卡片、hover 态、徽章 */
--border-default: #30363d; /* 通用边框 */
--border-focus:   #388bfd; /* 焦点边框 */
```

### 文字层级（全部 ≥ 4.5:1 对比度）

```css
--text-primary:   #e6edf3;   /* 主文字 (14.5:1) */
--text-secondary: #8b949e;   /* 次要文字 (5.9:1) */
--text-muted:     #6e7681;   /* 时间戳、标签 (4.5:1) */
--text-link:      #58a6ff;   /* 链接、强调 */
--text-success:   #3fb950;   /* 成功状态 */
```

### 语义强调色

```css
--color-success:  #3fb950;   /* 工具成功、会话空闲、idle 状态 */
--color-warning:  #d29922;   /* Agent 运行中、待审权限 */
--color-error:    #f85149;   /* 工具失败、权限拒绝 */
--color-info:     #388bfd;   /* explore/spec 模式、信息类 */
--color-accent:   #bc8cff;   /* plan 内容、spec 模式 */
--color-diff-add: #7ee787;   /* diff 新增行 */
--color-diff-del: #ffa198;   /* diff 删除行 */
```

### 字体 & 间距

```css
--font-sans: system-ui, -apple-system, "Segoe UI", sans-serif;
--font-mono: "Cascadia Code", "Consolas", "SF Mono", monospace;

--space-1: 4px;  --space-2: 8px;  --space-3: 12px;
--space-4: 16px; --space-6: 24px;

--radius-sm: 4px;  --radius-md: 6px;  --radius-lg: 10px;
```

**实施**：重写 `src/styles.css`，所有颜色引用替换为 token，删除旧有 warm parchment 变量。

---

## 二、布局架构

### 整体结构

```
.app-shell (display:grid; grid-template-rows: 40px 1fr; height:100vh; overflow:hidden)
├── .app-header (40px, 固定)
└── .workspace  (display:grid; grid-template-columns: var(--sidebar-w) 4px 1fr 4px var(--inspector-w))
    ├── .sidebar
    ├── .resize-handle (左拖拽手柄, 4px)
    ├── .main-chat
    ├── .resize-handle (右拖拽手柄, 4px)
    └── .inspector
```

### 宽度约束（用 CSS clamp）

```css
/* JS 写入原始值（无限制）*/
:root {
  --sidebar-w-raw:   220px;
  --inspector-w-raw: 260px;
}

/* grid 使用 clamp 计算后的值，避免自引用循环 */
.workspace {
  grid-template-columns:
    clamp(160px, var(--sidebar-w-raw),   360px)
    4px
    1fr
    4px
    clamp(200px, var(--inspector-w-raw), 480px);
}
```

**拖拽实现**：`mousedown` 在 resize-handle 上 → 监听 `mousemove` → `document.documentElement.style.setProperty('--sidebar-w-raw', x + 'px')` → `mouseup` 清理监听。`clamp()` 在 `grid-template-columns` 内自动限界，无需 JS 边界检查。

### 防溢出三原则

```css
/* 1. 父容器截断 */
.workspace { overflow: hidden; }

/* 2. 子列内部滚动 */
.sidebar, .inspector { overflow-y: auto; }

/* 3. 全局收缩 */
*, *::before, *::after { box-sizing: border-box; min-width: 0; }
```

### 全局 Header（新增）

40px 固定高，三段布局：
- **左**：品牌名 + 当前模式徽章（颜色跟随 `--color-{mode}`）
- **右**：`● running/idle/error` 状态点 + session ID + `turns N/M`

---

## 三、组件改动详情

### 3.1 Timeline（`Timeline.jsx`）

**工具块三态**（借鉴 Claude Code tool block）：

| 状态 | 左侧圆点 | 边框 | 右侧 meta |
|------|---------|------|----------|
| running | `--color-warning` 脉冲动效 | `--color-warning` 低透明度 | "running..." |
| success | `--color-success` | `--color-success` 低透明度 | 返回摘要 + 耗时 |
| error | `--color-error` | `--color-error` 低透明度 | "exit N · Xms ▸ 展开" |

- 工具块点击可展开详细输出（折叠态默认，error 态自动展开）
- 用户消息：右对齐气泡，`--bg-subtle` 背景，左侧 `--border-default` 线
- 助手消息：左侧 `--color-success` 2px 边线，流式光标用 `@keyframes blink`
- 系统消息（模式切换等）：`--bg-default` 小标签行，单独样式

### 3.2 Inspector（`Inspector.jsx`）

**Tab 重排**：7 个平铺 tab 改为"前 3 常驻 + `···` 溢出菜单"：
- 常驻：Todos（带 badge 数字）、Plan、Artifacts
- 溢出（`···` 弹出）：Review、Permissions、Preview、Log
- Badge 数字由 push 事件驱动实时更新

**实时同步**：
- `todos_updated` WebSocket 事件 → dispatch `todos_loaded` → Todos tab badge 更新
- `artifacts_updated` WebSocket 事件 → dispatch `artifacts_loaded` → Artifacts tab badge 更新

### 3.3 Sidebar（`Sidebar.jsx`）

- 文件树：监听 `tool_finished` 事件，当 `isFileSystemTool(tool_name)` 时自动 refetch
- `isFileSystemTool` 匹配：`["write_file", "edit_file", "git_commit", "git_reset"]`
- 会话列表：激活项左侧 `--color-success` 2px 边线，标题 `text-overflow: ellipsis`

### 3.4 Composer（`Composer.jsx`）

- 左侧模式标签，颜色与 header 模式徽章一致
- Agent running 时：`pointer-events: none; opacity: 0.5`
- 底部提示栏：`/ 命令` `↑↓ 历史` `Shift+Enter 换行`，running 时显示 `● running 时禁用`

---

## 四、数据同步架构

### 后端改动（`backend/server.py`）

在 `WebSocketFrontend` 中新增两个回调实现：

```python
async def on_todos_updated(self, todos: list):
    await self.broadcast({"type": "todos_updated", "data": todos})

async def on_artifacts_updated(self, artifacts: list):
    await self.broadcast({"type": "artifacts_updated", "data": artifacts})
```

### 协议新增（`protocol/__init__.py`）

在 `FrontendCallbacks` Protocol 中新增：
```python
def on_todos_updated(self, todos: List[dict]) -> None: ...
def on_artifacts_updated(self, artifacts: List[dict]) -> None: ...
```

### 触发时机（`core/adapter.py`）

在 `CallbackBridge` 的 `tool_finished` 处理中：
- `manage_todos` 工具完成 → 调用 `on_todos_updated`
- `write_file` / `edit_file` 工具完成 → 调用 `on_artifacts_updated`

### 前端改动（`App.jsx`）

```javascript
const FS_TOOLS = ["write_file", "edit_file", "git_commit", "git_reset"];

case "tool_finished":
  dispatch({ type: "tool_finished", data });
  if (FS_TOOLS.includes(data.tool_name)) {
    fetchFileTree();
  }
  break;

case "todos_updated":
  dispatch({ type: "todos_loaded", data: data.todos });
  break;

case "artifacts_updated":
  dispatch({ type: "artifacts_loaded", data: data.artifacts });
  break;
```

---

## 五、受影响文件清单

### 前端（`src/embedagent/frontend/gui/webapp/src/`）

| 文件 | 改动类型 |
|------|---------|
| `styles.css` | 完全重写（token 体系 + 布局） |
| `App.jsx` | 新增 WebSocket 事件处理、拖拽逻辑、header 组件 |
| `store.js` | 新增 `todos_updated`、`artifacts_updated` action |
| `components/Timeline.jsx` | 工具三态展示、用户/助手消息重设计 |
| `components/Inspector.jsx` | Tab 重排（3 常驻 + ··· 菜单）、badge 实时更新 |
| `components/Sidebar.jsx` | 文件树 tool_finished 触发 refetch |
| `components/Composer.jsx` | 模式感知、running 禁用、提示栏 |

### 后端（`src/embedagent/frontend/gui/`）

| 文件 | 改动类型 |
|------|---------|
| `backend/server.py` | 新增 `on_todos_updated`、`on_artifacts_updated` |
| `backend/bridge.py` | 无改动（现有 dispatcher 可复用） |

### 协议层（`src/embedagent/`）

| 文件 | 改动类型 |
|------|---------|
| `protocol/__init__.py` | `FrontendCallbacks` 新增两个方法签名 |
| `core/adapter.py` | `CallbackBridge` 新增触发逻辑 |

---

## 六、验证计划

1. **布局验证**：以 800px、1024px、1280px 三个窗口宽度打开 GUI，确认无内容溢出，拖拽手柄限界正确。
2. **色彩验证**：用浏览器 DevTools Accessibility 检查器确认所有文字对比度 ≥ 4.5:1。
3. **同步验证**：
   - 触发 `manage_todos` 工具 → Todos tab badge 数字实时更新
   - 触发 `write_file` 工具 → Sidebar 文件树自动刷新新文件
   - 触发 `plan_updated` 事件 → Plan tab 内容自动更新（已有功能，回归验证）
4. **工具三态验证**：mock 一次 running → success 和一次 running → error 的工具调用，确认动效和展开逻辑。
5. **Composer 禁用验证**：Agent running 时确认输入框和发送按钮不可用。
