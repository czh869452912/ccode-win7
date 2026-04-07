# EmbedAgent 代码与文档一致性审查报告

> 审查日期：2026-04-07  
> 审查范围：docs/ 根目录及 docs/archive/ 下的架构/协议/前端/TUI/Harness 相关文档，与 src/embedagent/ 实际代码进行静态比对  
> 审查方式：纯静态比对，不涉及运行测试或修改代码

---

## 摘要

本轮审查共发现 **8 类结构/一致性问题**，主要集中在：

1. 文档引用已删除的代码实体（`tools_v2/`）
2. 文档描述的目录结构与代码实际路径不符（`frontend/terminal/` vs `frontend/tui/`）
3. 文档中的 WebSocket 协议事件类型超出代码实现范围（`step_start`/`step_end`）
4. 文档对测试数量的描述与实际测试文件不符
5. 历史文档未按要求归档，仍留在 docs 根目录
6. 文档内部目录树存在逻辑/排版错误
7. TUI 入口文件存在状态描述与实际不符
8. 开发追踪文档中仍保留已被废弃的旧模式名历史记录（已知为历史记录，若作为当前状态参考则会造成混淆）

---

## 问题详情

### 1. tool-contracts.md 引用已删除的 `tools_v2/` 目录

**位置**：`docs/tool-contracts.md` 第 118 行

**文档原文**：

> The authoritative implementation lives in:
> - `src/embedagent/tools/runtime.py`
> - `src/embedagent/tools/harness_runtime.py`
> - `src/embedagent/tools_v2/`

**实际代码**：`src/embedagent/tools_v2/` 目录已不存在（`ls` 验证为 NOT FOUND）。根据 `docs/development-tracker.md` 及近期 commit 记录，`tools_v2/` 中的存活模块已迁入 `src/embedagent/tools/`，旧目录已被删除。

**影响**：文档提供了错误的源码定位，新成员或后续维护者可能因找不到该目录而产生困惑。

**建议**：从 Source Of Truth 段落中删除 `src/embedagent/tools_v2/` 引用。

---

### 2. tui-information-architecture.md 描述的目录路径与代码严重不符

**位置**：`docs/tui-information-architecture.md` 第 54–87 行

**文档原文**：包结构描述为

```text
src/embedagent/
├── tui.py
└── frontend/
    └── terminal/
        ├── __init__.py
        ├── bootstrap.py
        ├── app.py
        ├── state.py
        ├── reducer.py
        ├── controller.py
        ├── commands.py
        ├── completion.py
        ├── host.py
        ├── theme.py
        ├── layout.py
        ├── models.py
        ├── services/
        └── views/
```

**实际代码**：TUI 实际位于 `src/embedagent/frontend/tui/`，而非 `frontend/terminal/`。所有子模块（`bootstrap.py`、`app.py`、`services/`、`views/` 等）的前缀均为 `frontend/tui/`。

**影响**：文档中的路径全部失效，无法作为导航或新成员入门的参考。

**建议**：将文档中的 `frontend/terminal/` 全局替换为 `frontend/tui/`；或如该文档自身尾部注记所言，将其移入 `docs/archive/` 并标记为历史文档。

---

### 3. architecture-new.md 目录树存在结构/排版错误

**位置**：`docs/architecture-new.md` 第 63–76 行

**文档原文**：

```text
    └── gui/                     # GUI 实现（PyWebView）
        ├── __init__.py
        ├── launcher.py
        ├── backend/
        │   ├── __init__.py
        │   └── server.py
        ├── static/
        │   ├── index.html
        │   └── assets/
        └── webapp/              # React + Vite 源码

└── frontend/tui/          # 旧 TUI 位置（向后兼容）
    └── ...
```

**问题**：
- `frontend/gui/` 同级缩进下又出现一个 `frontend/tui/`，但缺少合理的父节点包裹。根据文档上下文，`frontend/tui/` 已经在上方 `frontend/` 节点下完整列出，此处重复出现造成目录树逻辑混乱。
- 第 74 行的 `└── frontend/tui/` 缩进也不对（比 `gui/` 的父级 `frontend/` 更深但没有合理的中间节点）。

**建议**：删除第 74–76 行的重复/错误目录树片段，或在一处统一的 `frontend/` 子树下同时列出 `tui/` 和 `gui/`。

---

### 4. tui-information-architecture.md 对 `tui.py` 存在状态的描述与实际不符

**位置**：`docs/tui-information-architecture.md` 第 54 行

**文档原文**：

> 当前终端前端已从单文件 `src/embedagent/tui.py` 迁移为模块包

**实际代码**：`src/embedagent/tui.py` 仍然存在，内容为兼容 shim，使用 `__getattr__` 延迟导入 `TerminalApp` 及 `run_tui`，并非“已迁移/删除”。

**影响**：文档传递了“旧入口已消失”的错误印象，而实际上 `embedagent.tui` 仍被作为向后兼容入口使用。

**建议**：将描述修正为“`src/embedagent/tui.py` 保留为兼容 shim，实际实现已迁移到 `frontend/tui/` 模块包”。

---

### 5. frontend-protocol.md 列出的 WebSocket 事件类型超出现有代码实现

**位置**：`docs/frontend-protocol.md` 第 72–90 行

**文档原文**：列出的 Important pushed event types 包括：

- `step_start`
- `step_end`

**实际代码**：
- `src/embedagent/frontend/gui/backend/server.py`（`WebSocketFrontend`）处理了 `message`、`tool_start`、`tool_progress`、`tool_finish`、`permission_request`、`user_input_request`、`session_status`、`stream_delta`、`reasoning_delta`、`thinking_state`、`command_result`、`plan_updated`、`tasks_refresh`、`artifacts_refresh`、`turn_event`（`turn_start`/`turn_end`）等。
- 但未找到对 `step_start` 和 `step_end` 的专门路由或事件转换逻辑。代码中仅存在 `turn_start`/`turn_end` 的 `on_turn_event` 处理，没有 step 级别的事件。

**影响**：协议文档声明了代码未实现的事件类型，若第三方前端依据该文档实现 step 级事件监听，将无法收到对应消息。

**建议**：在代码中补齐 `step_start`/`step_end` 事件转发，或在文档中删除尚未实现的事件类型。

---

### 6. architecture-new.md 中协议接口的方法名描述与 protocol/__init__.py 不一致

**位置**：`docs/architecture-new.md` 第 84–105 行

**文档原文**：`CoreInterface` 示例签名中使用了：

```python
def submit_user_message(...) -> None: ...
def approve_permission(...) -> None: ...
def reject_permission(...) -> None: ...
```

**实际代码**：`src/embedagent/protocol/__init__.py` 中 `CoreInterface` 抽象类定义的方法名为：

```python
def submit_message(self, session_id: str, text: str) -> None: ...
def approve_permission(self, session_id: str, permission_id: str) -> None: ...
def reject_permission(self, session_id: str, permission_id: str) -> None: ...
```

- `submit_message` 在 protocol 层是 `submit_message`，在 `inprocess_adapter.py` 中才是 `submit_user_message`。
- 文档将内部实现的方法名写进了协议层描述，容易造成“协议接口应叫 `submit_user_message`”的误解。

**建议**：将 architecture-new.md 中 `CoreInterface` 的示例方法名与 `protocol/__init__.py` 保持严格一致。

---

### 7. architecture-new.md 对架构测试数量的描述与实际测试文件不符

**位置**：`docs/architecture-new.md` 第 238–248 行

**文档原文**：

```text
TestProtocol (5 tests)          ✓
TestMockFrontend (6 tests)      ✓
TestFrontendTUIImport           ✓
TestFrontendGUIImport           ✓
TestCoreAdapterImport           ✓
```

**实际代码**：`tests/test_architecture.py` 中：
- `TestProtocol` 类实际包含 **10 个** 测试方法（`test_message_creation`、`test_session_snapshot`、`test_tool_call`、`test_tool_result`、`test_workspace_info`、`test_command_result`、`test_permission_request_keeps_anchor_fields`、`test_user_input_request_keeps_anchor_fields`、`test_plan_snapshot`、`test_turn_record_and_timeline_item`），而非 5 个。
- `TestMockFrontend` 实际为 6 个，此项正确。
- 其余类均未标注测试数量。

**影响**：文档给出的测试范围与覆盖率印象严重低于实际，可能误导读者认为协议层测试不足。

**建议**：更新 `TestProtocol` 的测试数量标注为 10，或删除具体数量标注，改为指向 `tests/test_architecture.py` 的链接。

---

### 8. tui-information-architecture.md 作为历史文档未归档到 docs/archive/

**位置**：`docs/tui-information-architecture.md`

**文档自身声明**（第 327–336 行）：

> This document predates the current `tasks/build` frontend vocabulary cutover.  
> Treat it as historical reference material, not as the current frontend contract.  
> Current source-of-truth documents are: `docs/frontend-protocol.md`, `docs/overall-solution-architecture.md`

**实际状态**：该文档仍位于 `docs/` 根目录，而项目中其他已关闭的 slice（如 `gui-runtime-hardening`、`gui-timeline-event-anchors`、`transcript-truth-tool-result-cutover`）均已移入 `docs/archive/` 下。

**影响**：与项目自身的文档治理规则不一致，降低了当前官方文档的可发现性。

**建议**：将该文档及附属内容移入 `docs/archive/tui-information-architecture/`（参考其他 archive 的目录组织方式），并在原位置保留一个指向 archive 的 README 或链接。

---

## 附注：已知但可接受的不一致

以下条目在审查中被识别，但考虑到其历史记录属性或并不影响当前架构理解，仅作附注，不评为问题：

1. **`docs/development-tracker.md` 中保留旧模式名 `code`**  
   该文档记录了历史实施过程（"Phase 3 模式系统 v2 已落地：5 模式配置驱动（`explore`/`spec`/`code`/`debug`/`verify`）"）。当前官方模式契约（`docs/mode-schema.md`、`docs/agent-harness-v2.md`）已将其替换为 `build`。由于 development-tracker 本身具有编年史性质，保留旧名是可接受的，只要读者理解其为历史记录而非当前基线。

2. **`docs/tool-contracts.md` 声明了 `git_write` 权限类别，但当前工具目录中无工具实际使用它**  
   `git_status`/`git_diff`/`git_log` 均标记为 `read` 类别。`git_write` 在 `permissions.py` 中存在定义，但工具侧尚未提供对应的写入型 Git 工具。这不属于文档-代码直接冲突，而是一个待补全的功能缺口。

---

## 结论

当前项目文档与代码之间存在**中度的结构漂移**，主要来源是近期的 V2 切over（工具目录删除、模式词汇从 `code` 切到 `build`、TUI 目录迁移）后，部分文档未及时同步。建议优先修复 **问题 1、2、3、5、8**，因为它们直接影响路径导航、协议实现理解和文档治理一致性。
