# EmbedAgent TUI 信息架构（Phase 6）

> 更新日期：2026-03-28
> 适用阶段：Phase 6 交互层设计

---

## 1. 文档目标

定义首版 TUI 的信息结构、核心交互流和边界，保证：

- 交互层不反向侵蚀 Core 设计
- 首版 TUI 足够可用，但不演化成终端 IDE
- Windows 7 终端环境下也能稳定工作

本文件关注“界面应呈现什么、如何组织信息”，不展开最终视觉细节。

---

## 2. 设计原则

### 2.1 单会话优先，多会话可切换

首版 TUI 的重点是：

- 一个活跃会话的清晰推进
- 最近会话的快速恢复

而不是同时并排管理很多会话。

### 2.2 先保证可观测，再追求炫技交互

用户首先需要知道：

- 当前模式是什么
- 当前 Agent 在做什么
- 有没有权限确认卡住
- 最近工具结果和错误是什么
- 当前会话是否已经被压缩/恢复

所以首版应优先展示状态和事件，而不是花哨布局。

### 2.3 不把 TUI 做成文本编辑器

首版 TUI 不承担：

- 多文件源码编辑
- 内嵌 diff merge
- 复杂树状工程浏览

这些都不是当前 Phase 6 的核心目标。

---

## 3. 首版范围

### 3.1 要做

- 新建会话
- 恢复最近会话
- 发送用户消息
- 查看 assistant 流式回复
- 查看工具开始/结束事件
- 响应权限确认
- 查看最近会话状态摘要
- 查看当前模式、上下文压缩和错误状态

### 3.2 暂不做

- 多标签页会话并发运行
- 内嵌文件编辑器
- artifact 专门浏览器
- 图形化 diff
- HTTP/Web 前端复用层

---

## 4. 页面结构

首版建议采用三段式纵向结构，加一个可切换侧栏。

```text
┌─────────────────────────────────────────────────────────────┐
│ Header / Session Bar                                        │
├───────────────────────────────────────┬─────────────────────┤
│ Transcript / Event Stream             │ Side Panel          │
│                                       │                     │
│ user / assistant / tool / permission  │ session summary     │
│                                       │ mode / budget       │
│                                       │ project memory      │
│                                       │ last blocker        │
├───────────────────────────────────────┴─────────────────────┤
│ Composer / Command Line                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. 主要区域

### 5.1 Header / Session Bar

显示：

- 当前 `session_id`（短 ID）
- 当前 mode
- 当前状态：`idle / running / waiting_permission / error`
- 当前工作区
- 是否来自 resume

辅助操作：

- `n` 新建会话
- `r` 恢复最近会话
- `s` 打开会话列表
- `q` 退出

### 5.2 Transcript / Event Stream

这是首版 TUI 的主区域。

显示顺序：

- 用户消息
- assistant 回复
- tool started / finished
- permission required
- session error / session finished

要求：

- assistant 流式增量要自然滚动
- tool 事件要比普通文本更醒目
- permission 事件要固定停留，直到用户处理
- context compact / session resumed 这类系统事件也要可见，但权重低于错误与权限

### 5.3 Side Panel

侧栏显示“当前会话摘要”，而不是完整历史。

建议分 4 个小块：

1. `Session`
   - current mode
   - updated_at
   - turn_count
   - message_count

2. `Context`
   - recent_turns
   - summarized_turns
   - approx_tokens_after
   - project_memory_included

3. `Work`
   - working_set
   - modified_files
   - recent_actions

4. `Status`
   - last_success
   - last_blocker
   - recent_artifacts（只显示引用，不展开正文）

### 5.4 Composer / Command Line

底部输入区统一承载三类输入：

- 普通用户消息
- slash 命令
- 权限确认快捷回复

首版建议支持：

- 直接输入消息回车发送
- `/mode <name>`
- `/resume latest`
- `/sessions`
- `/snapshot`
- `/quit`

---

## 6. 关键交互流

### 6.1 新建会话

1. 用户进入 TUI
2. 默认显示一个空会话 Composer
3. 输入消息并发送
4. Header 切到 `running`
5. Transcript 追加 `turn_started`
6. assistant / tool 事件陆续出现
7. 完成后状态切回 `idle`

### 6.2 恢复会话

1. 用户按 `r` 或输入 `/resume latest`
2. 弹出最近会话列表，显示：
   - session_id
   - current_mode
   - updated_at
   - summary_text
3. 选中后恢复
4. Transcript 追加 `session_resumed`
5. 侧栏立即显示恢复摘要、工作集和最近 blocker
6. 用户继续输入下一条消息

### 6.3 权限确认

1. Transcript 收到 `permission_required`
2. Header 状态切为 `waiting_permission`
3. 底部 Composer 切换成确认提示：
   - `y` 批准
   - `n` 拒绝
4. 用户选择后，事件流继续推进

### 6.4 错误处理

1. 出现 `session_error`
2. Header 标红或至少高亮错误状态
3. 侧栏 `Status` 区显示 `last_error`
4. Composer 不锁死，允许用户继续输入“继续排查”或切换 mode

---

## 7. 会话列表视图

会话列表不需要单独一整页，首版可以是弹层或抽屉。

每个条目显示：

- `session_id`
- `current_mode`
- `updated_at`
- `summary_text`（截断）

支持动作：

- 回车恢复
- `d` 删除（后续再做）
- `esc` 关闭

---

## 8. 事件到 UI 的映射

| Event | TUI 行为 |
|------|-----------|
| `session_created` | 新建会话条、刷新 Header |
| `session_resumed` | 在 Transcript 中插入恢复标记，并刷新侧栏 |
| `turn_started` | 在事件流中插入分隔线 |
| `assistant_delta` | 追加到当前 assistant 气泡 |
| `tool_started` | 插入工具开始卡片 |
| `tool_finished` | 更新工具卡片结果 |
| `permission_required` | 锁定为待处理提示，并切 Header 状态 |
| `context_compacted` | 侧栏刷新 Context 区 |
| `session_finished` | Header 切回 idle，侧栏更新时间 |
| `session_error` | 高亮错误状态，并在侧栏显示 last_error |

---

## 9. Windows 7 终端约束

首版 TUI 必须适配较弱终端环境，因此：

- 不依赖鼠标
- 不依赖复杂 Unicode 边框
- 动画尽量少
- 保证无颜色环境下也能读
- 所有关键操作必须有键盘路径

建议：

- 用 `Rich` 做基础样式，但不要强依赖高级渲染特性
- 用 `prompt_toolkit` 做输入框、快捷键和布局
- 所有弹层都要有纯键盘退出路径

---

## 10. Phase 6 实现顺序

### 10.1 第一步

先做 `InProcessAdapter`，让现有 CLI 从“直接调 loop”变成“通过 adapter 调 loop”。

### 10.2 第二步

在 adapter 之上做最小 TUI：

- Header
- Transcript
- Composer
- Session Summary Side Panel

### 10.3 第三步

补：

- 会话列表弹层
- 权限确认交互
- 错误状态展示

stdio JSON-RPC adapter 放在这些都稳定后再接。

---

## 11. 当前结论

Phase 6 首版 TUI 的目标不是“终端 IDE”，而是：

**把 Session、Event、Permission、Context 这四类信息稳定地呈现出来。**

只要这四类信息组织清楚，用户就能真正感知 Core 的行为，而不是把交互层做成一个只会显示聊天记录的壳。
