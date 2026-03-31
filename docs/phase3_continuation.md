# Phase 3 剩余任务（续接计划）

本文件记录 Phase 3 的实施进度，供跨设备继续开发时参考。

## 已完成

- **G3/G4** ✅ 模式配色 + 状态栏（commit `ceb2f97`）
  - `styles.css`: 每模式颜色类 `.mode-explore/spec/code/debug/verify` + dark mode 变体
  - `styles.css`: `select.badge` 自定义下拉箭头，去除系统外观
  - `styles.css`: `.status-bar` 及子元素样式（turn 计数、模式名、连接状态）
  - `App.jsx`: header 中 badge+select 合并为单一 `<select class="badge mode mode-X">`
  - `App.jsx`: `<StatusBar>` 组件插在 `</header>` 之后，显示 Turn N/max · mode · status
  - `App.jsx`: `session_status` 处理器中检测模式变更 → 插入 `kind:"system" tone:"context"` timeline 卡片

- **A3** ✅ 权限内联卡片（commit `ceb2f97`）
  - `App.jsx`: `sessionAutoApprove` ref（Set），自动批准已记住的 category
  - `App.jsx`: `permission_request` 路由：`category === "command"` → modal，其他 → inline timeline item
  - `App.jsx`: `sendInlinePermissionResponse(permissionId, approved, remember, category)` 函数
  - `Timeline.jsx`: `PermissionCard` 组件，含 Approve/Deny + "remember" 复选框；resolved 状态显示结果
  - `store.js`: `permission_request_inline` + `permission_item_resolved` action
  - `styles.css`: `.permission-card` 完整样式（active + resolved + dark）

---

## 待实施

### A2：`propose_mode_switch` 工具（后端 + 前端）

**目标**：用专用 2 步流程替代 ask_user 的 `option_N_mode` 机制

**后端改动**：

1. **`src/embedagent/interaction.py`**：
   - 新增 `propose_mode_switch_schema()` 返回工具定义：
     ```python
     {
       "type": "function",
       "function": {
         "name": "propose_mode_switch",
         "description": "向用户建议切换工作模式。当前任务需要的能力超出当前模式权限时调用。",
         "parameters": {
           "type": "object",
           "properties": {
             "target_mode": {"type": "string", "enum": ["explore","spec","code","debug","verify"]},
             "reason": {"type": "string", "description": "为何需要切换模式的简短说明"}
           },
           "required": ["target_mode", "reason"],
           "additionalProperties": False
         }
       }
     }
     ```
   - 新增 `@dataclass class ModeSwitchProposal: target_mode: str; reason: str`

2. **`src/embedagent/loop.py`**：
   - 在 `_dispatch_tool_call()` 里新增分支：
     ```python
     if name == "propose_mode_switch":
         return await self._handle_propose_mode_switch(arguments)
     ```
   - 新增 `_handle_propose_mode_switch(arguments)` 方法：
     - 发送 `mode_switch_proposal` 事件（通过 event_handler）
     - 等待用户响应（通过 user_input_resolver，request_id=`"mode_switch_{uuid}"`）
     - 响应中 `selected_mode` 非空 → 调用 `self._switch_mode(target_mode)` → 返回确认文本
     - 响应拒绝 → 返回 "用户选择保持当前模式"
   - 将 `propose_mode_switch_schema()` 加入工具列表（所有模式可用）

3. **`src/embedagent/frontend/gui/backend/server.py`**：
   - `WebSocketFrontend.on_turn_event` 已支持任意事件广播，`mode_switch_proposal` 会自动通过，无需修改

**前端改动**：

4. **`webapp/src/App.jsx`**：
   - `handleSocketMessage` 中的 `user_input_request` 处理已存在。
   - 当 `data.tool_name === "propose_mode_switch"` 时，派发带 `kind: "mode_switch_proposal"` 的 timeline item，而非普通 `user_input` item。

5. **`webapp/src/components/Timeline.jsx`**：
   - 新增 `ModeSwitchCard` 组件：
     - 显示 "Agent 建议切换到 X 模式：{reason}"，使用目标模式配色
     - 两个按钮：确认切换 / 保持当前模式
     - 点击后调用 `onSubmitUserInput(option)`，option 含 `selected_mode: target_mode`
   - 在 `TurnGroup` 的 `activityItems.map` 中增加 `kind === "mode_switch_proposal"` 分支

6. **`webapp/src/styles.css`**：
   - 新增 `.mode-switch-card` 样式，使用目标模式的配色（复用 `.mode-X` 颜色变量）

---

### P1：系统提示词支持项目上下文

**目标**：`build_system_prompt()` 从工作区 `.embedagent/context.md` 加载项目特定上下文

**文件**：`src/embedagent/modes.py`（找到 `build_system_prompt` 函数）

**实施**（约 10 行）：
```python
def _load_project_context(workspace: str) -> str:
    ctx_path = os.path.join(workspace, ".embedagent", "context.md")
    try:
        with open(ctx_path, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

# 在 build_system_prompt 末尾追加：
ctx = _load_project_context(workspace)
if ctx:
    prompt += f"\n\n## Project Context\n{ctx}"
```

**示例 `.embedagent/context.md`**：
```markdown
## Project: EmbedAgent
- Language: Python + C (embedded target)
- Build: cmake + ninja
- Test: pytest src/
- Style: Black formatter, 120-char lines
- Target: Windows 7 offline, no internet
```

---

### A1-完整：后端 Timeline API 返回结构化 Turn 列表

**目标**：`GET /api/sessions/{id}/timeline` 返回聚合后的 Turn 数据，而非原始事件流

**文件**：
- `src/embedagent/inprocess_adapter.py`（`get_session_timeline` 方法）
- `src/embedagent/frontend/gui/backend/server.py`（`/timeline` 端点）
- `webapp/src/state-helpers.js`（`timelineFromEvents` 改为接受 Turn 格式）

**返回格式**：
```json
{
  "turns": [
    {
      "turn_id": "t-abc123",
      "user_text": "...",
      "reasoning": "聚合后的完整 reasoning 文本",
      "tool_calls": [
        {"tool_name": "...", "arguments": {}, "status": "success", "data": {}, "error": ""}
      ],
      "assistant_text": "...",
      "status": "completed"
    }
  ]
}
```

**实施步骤**：
1. `inprocess_adapter.py` 的 `get_session_timeline()` 对原始事件做聚合：
   - 遍历事件，`turn_start` 开新 Turn 组
   - `reasoning_delta` 拼接为单字符串
   - `tool_start`/`tool_finish` 配对
   - `assistant_delta` 拼接为 `assistant_text`
2. `server.py` 端点 `/timeline` 调用聚合方法，返回 `{"turns": [...]}`
3. `state-helpers.js` 的 `timelineFromEvents()` 改为处理 Turn 格式，展开为前端 timeline items（可大幅简化）

---

## 实施顺序建议

1. **P1** — 最简单，10 行，高价值，先做热身
2. **A2** — 核心价值，解决模式切换 7 步问题
3. **A1-完整** — 最复杂，需要前后端联动，最后做

## 关键文件路径

| 任务 | 核心文件 |
|------|---------|
| A2 后端 | `src/embedagent/interaction.py`, `src/embedagent/loop.py` |
| A2 前端 | `webapp/src/components/Timeline.jsx`, `webapp/src/styles.css`, `webapp/src/App.jsx` |
| A1 后端 | `src/embedagent/inprocess_adapter.py`, `src/embedagent/frontend/gui/backend/server.py` |
| A1 前端 | `webapp/src/state-helpers.js` |
| P1 | `src/embedagent/modes.py` |
