# EmbedAgent 新架构文档（2026-03-30）

> 更新日期：2026-03-30
> 描述：GUI PyWebView 重构后的新架构

---

## 1. 架构概述

新架构实现了 **Agent Core 与前端完全解耦** 的设计目标，采用分层架构：

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │     TUI      │  │     GUI      │  │ Future Web   │          │
│  │ (terminal)   │  │ (pywebview)  │  │   Console    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼─────────────────┼─────────────────┼───────────────────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │ FrontendCallbacks
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Protocol Layer                            │
│     CoreInterface      FrontendCallbacks      Data Types       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                         Core Layer                              │
│                    AgentCoreAdapter                             │
│              (包装 InProcessAdapter)                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 目录结构

```
src/embedagent/
├── protocol/                    # 通信协议层
│   └── __init__.py              # CoreInterface, FrontendCallbacks, 数据类型
│
├── core/                        # Agent Core 层
│   ├── __init__.py
│   └── adapter.py               # AgentCoreAdapter - 实现 CoreInterface
│
├── frontend/                    # 前端抽象层
│   ├── __init__.py
│   │
│   ├── tui/                     # TUI 实现（prompt_toolkit）
│   │   ├── __init__.py          # 延迟导入
│   │   ├── app.py               # TerminalApp 主协调器
│   │   ├── frontend_adapter.py  # TUIFrontend 实现 FrontendCallbacks
│   │   ├── launcher.py          # TUI 启动器
│   │   ├── controller.py
│   │   ├── layout.py
│   │   ├── services/
│   │   ├── views/
│   │   └── ...
│   │
│   └── gui/                     # GUI 实现（PyWebView）
│       ├── __init__.py
│       ├── launcher.py          # GUI 启动器
│       ├── backend/
│       │   ├── __init__.py
│       │   └── server.py        # FastAPI + WebSocket 服务器
│       └── static/
│           ├── index.html
│           ├── css/style.css
│           └── js/app.js
│
└── frontends/terminal/          # 旧 TUI 位置（向后兼容）
    └── ...
```

---

## 3. 协议层（Protocol Layer）

### 3.1 核心接口

```python
class CoreInterface(Protocol):
    """Core 对外暴露的接口"""
    def create_session(...) -> SessionSnapshot: ...
    def submit_user_message(...) -> None: ...
    def approve_permission(...) -> None: ...
    def reject_permission(...) -> None: ...
    def list_sessions(...) -> List[SessionSummary]: ...
    def get_workspace_snapshot(...) -> WorkspaceInfo: ...
    # ...

class FrontendCallbacks(Protocol):
    """前端需要实现的回调"""
    def on_message(message: Message) -> None: ...
    def on_tool_start(call: ToolCall) -> None: ...
    def on_tool_finish(result: ToolResult) -> None: ...
    def on_permission_request(request: PermissionRequest) -> bool: ...
    def on_session_status_change(snapshot: SessionSnapshot) -> None: ...
    def on_stream_delta(text: str) -> None: ...
```

### 3.2 数据类型

| 类型 | 用途 |
|------|------|
| `Message` | 用户/助手/系统消息 |
| `ToolCall` | 工具调用请求 |
| `ToolResult` | 工具执行结果 |
| `PermissionRequest` | 权限确认请求 |
| `SessionSnapshot` | 会话状态快照 |
| `WorkspaceInfo` | 工作区信息 |

---

## 4. Core 层

### 4.1 AgentCoreAdapter

`AgentCoreAdapter` 是 Core 层的核心实现：

- 包装现有的 `InProcessAdapter`
- 实现 `CoreInterface` 协议
- 管理 `FrontendCallbacks` 注册
- 将内部事件转换为协议事件分发给前端

```python
class AgentCoreAdapter:
    def __init__(self, workspace: str, config: dict):
        self._adapter = InProcessAdapter(...)
        self._frontend: Optional[FrontendCallbacks] = None
    
    def register_frontend(self, frontend: FrontendCallbacks) -> None:
        """注册前端回调"""
        self._frontend = frontend
    
    def submit_user_message(self, text: str) -> None:
        """处理用户消息，通过回调返回结果"""
        # 调用内部 adapter
        # 通过 _frontend.on_* 回调分发事件
```

---

## 5. 前端层

### 5.1 TUI 前端

**位置**: `frontend/tui/`

**特点**:
- 基于 `prompt_toolkit` + `rich`
- 终端界面，适合远程/服务器环境
- 低资源占用

**启动方式**:
```bash
python -m embedagent.frontend.tui.launcher /path/to/workspace
```

**架构适配**:
- `TUIFrontend` 实现 `FrontendCallbacks`
- 将协议事件转换为 TUI 状态更新
- 通过 `reducer` 模式管理状态

### 5.2 GUI 前端

**位置**: `frontend/gui/`

**特点**:
- 基于 `PyWebView` + `FastAPI` + `WebSocket`
- 现代 Web 界面，类似 Claude Code
- Windows 7 兼容（IE11 回退）

**启动方式**:
```bash
python -m embedagent.frontend.gui.launcher /path/to/workspace
```

**架构**:
```
GUI Launcher
    │
    ├─► PyWebView 窗口
    │       │
    │       └─► WebSocket 连接
    │               │
    └─► FastAPI 服务器 ◄──── WebSocket
                │
                ├─► GUIBackend
                │       │
                │       └─► AgentCoreAdapter
                │               │
                │               └─► InProcessAdapter
                │
                └─► Static Files (HTML/CSS/JS)
```

---

## 6. 向后兼容

### 6.1 旧 TUI 入口

旧位置 `frontends/terminal/` 仍然保留，通过 `embedagent.tui` 导入：

```python
# 旧方式（仍然有效）
from embedagent.tui import run_tui

# 新方式
from embedagent.frontend.tui import launch_tui
```

### 6.2 延迟导入

对于依赖缺失的情况（如 `prompt_toolkit` 未安装），新架构采用延迟导入：

```python
# frontend/tui/__init__.py
def __getattr__(name):
    if name == "TerminalApp":
        from .app import TerminalApp
        return TerminalApp
    # ...
```

---

## 7. 测试覆盖

新架构包含专门的架构测试：

```bash
# 运行架构测试
python tests/test_architecture.py

# 结果
TestProtocol (5 tests)          ✓
TestMockFrontend (6 tests)      ✓
TestFrontendTUIImport           ✓
TestFrontendGUIImport           ✓
TestCoreAdapterImport           ✓
```

---

## 8. 与文档对应

| 文档 | 新架构对应 |
|------|-----------|
| `docs/frontend-protocol.md` | `protocol/` 层 |
| `docs/tui-information-architecture.md` | `frontend/tui/` + `frontends/terminal/` |
| `docs/overall-solution-architecture.md` | Core/Frontend 解耦设计 |
| `docs/development-tracker.md` | T-012 已更新 |

---

## 9. 后续工作

- [ ] 将旧 `frontends/terminal/` 完全迁移到 `frontend/tui/`
- [ ] 实现 GUI 的 diff 确认弹窗与后端联动
- [ ] 实现 GUI 的权限确认弹窗与后端联动
- [ ] 添加更多架构集成测试
- [ ] 更新 `docs/frontend-protocol.md` 以反映新协议层

---

## 10. 变更记录

| 日期 | 变更 |
|------|------|
| 2026-03-30 | 创建新架构文档 |
| 2026-03-30 | 添加 `protocol/` 层 |
| 2026-03-30 | 添加 `core/` 层 |
| 2026-03-30 | 添加 `frontend/gui/` 层 |
| 2026-03-30 | 迁移 `frontend/tui/` 层 |
