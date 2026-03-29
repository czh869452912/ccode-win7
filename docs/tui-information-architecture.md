# EmbedAgent TUI 信息架构（Phase 6）

> 更新日期：2026-03-29
> 适用阶段：Phase 6 交互层设计

---

## 1. 文档目标

定义当前终端前端的信息结构、子模块边界和关键交互流，保证：

- 交互层不反向侵蚀 Core 设计
- TUI 已经从单文件原型收敛成可维护模块
- Windows 7 终端环境下的保底体验始终可用

本文件关注“当前终端前端应该呈现什么、怎样组织信息、哪些边界已经固定”。

---

## 2. 当前设计原则

### 2.1 单会话优先，多会话可切换

当前终端前端仍以一个活跃会话为中心：

- 一个活跃会话的清晰推进
- 最近会话的快速恢复
- 会话列表作为 explorer 子视图，而不是多标签并发编排

### 2.2 先保证可观测，再增加浏览与编辑能力

当前前端优先解决：

- Session / Mode / Permission / Error 可见
- Timeline 可回看
- Workspace 可浏览
- Artifact 可浏览
- 单文件可编辑

### 2.3 不做终端 IDE 的全量野心

当前仍然**不是**完整终端 IDE，不承担：

- 多标签会话并发运行
- 多缓冲文件编辑
- 内嵌 merge editor
- 图形化 diff
- HTTP/Web 前端复用层

---

## 3. 当前包结构

当前终端前端已从单文件 `src/embedagent/tui.py` 迁移为模块包：

```text
src/embedagent/
├── tui.py                          # 兼容 shim，懒加载终端前端
└── frontends/
    └── terminal/
        ├── __init__.py
        ├── bootstrap.py            # run_tui / 依赖加载 / 宿主保护
        ├── app.py                  # TerminalApp 主协调器
        ├── state.py                # UI 状态真相
        ├── reducer.py              # 纯状态变换
        ├── controller.py           # 输入路由与副作用
        ├── commands.py             # slash command 解析
        ├── completion.py           # /、@文件、artifact、session 补全
        ├── host.py                 # raw-console / conemu 能力识别
        ├── theme.py                # Win7-safe 主题
        ├── layout.py               # prompt_toolkit 布局和快捷键
        ├── models.py               # ExplorerItem / ArtifactRow / EditorBuffer
        ├── services/
        │   ├── sessions.py
        │   ├── workspace.py
        │   ├── timeline.py
        │   ├── artifacts.py
        │   └── editor.py
        └── views/
            ├── header.py
            ├── explorer.py
            ├── timeline.py
            ├── inspector.py
            ├── composer.py
            ├── editor.py
            └── dialogs.py
```

边界约束固定为：

- `views/` 不直接调 adapter
- `reducer.py` 不触碰 prompt_toolkit 对象
- `controller.py` 负责副作用和服务调用
- `bootstrap.py` 之外不直接 new LLM / ToolRuntime

---

## 4. 当前页面结构

当前终端前端采用“三栏主体 + 底部 composer”的布局。

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Header / Session Bar                                                 │
├───────────────────────┬─────────────────────────┬────────────────────┤
│ Explorer              │ Main View               │ Inspector          │
│                       │                         │                    │
│ Workspace             │ Timeline                │ Status             │
│ Sessions              │ Preview                 │ Plan               │
│ Todos                 │ Editor                  │ Artifacts          │
│                       │                         │ Permission / Diff  │
├───────────────────────┴─────────────────────────┴────────────────────┤
│ Composer / Command Line                                              │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 5. 当前主要区域

### 5.1 Header / Session Bar

显示：

- 当前 `session_id`（短 ID）
- 当前 mode
- 当前状态：`idle / running / waiting_permission / error`
- 当前工作区
- host mode：`raw-console / conemu`
- git branch / dirty 计数
- follow output 状态
- editor dirty 状态

### 5.2 Explorer

当前 explorer 有 3 个主标签：

- `Workspace`
- `Sessions`
- `Todos`

当前支持：

- 列表/树状文本浏览
- 选中项移动
- 目录下钻
- 选中文件预览
- 选中文件进入编辑
- 选中会话恢复

### 5.3 Main View

当前主视图支持 3 种模式：

- `Timeline`
- `Preview`
- `Editor`

其中：

- Timeline 负责显示 user / assistant / tool / permission / context 事件
- Preview 负责显示文件或 artifact 文本
- Editor 负责单缓冲文件编辑

### 5.4 Inspector

当前 inspector 标签：

- `status`
- `plan`
- `artifacts`
- `help`
- `snapshot`
- `diff`

当前含义：

- `status`：当前 session、workspace、summary、permission、error
- `plan`：最近 assistant 完整回复 + todo 列表
- `artifacts`：artifact 索引列表与当前选中引用
- `snapshot`：当前前端状态快照
- `diff`：编辑器保存前后差异预览

### 5.5 Composer / Command Line

当前底部输入统一承载：

- 普通用户消息
- slash command
- 权限确认回复

当前命令集至少包括：

- `/help`
- `/new [mode]`
- `/resume latest|selected|<session_id>`
- `/workspace [path]`
- `/sessions`
- `/todos`
- `/artifacts`
- `/artifact <ref>`
- `/open <path>`
- `/edit <path>`
- `/save`
- `/explorer <workspace|sessions|todos>`
- `/inspector <status|plan|artifacts|help|snapshot|diff>`
- `/follow <on|off>`
- `/mode <name>`
- `/quit`

当前补全集包括：

- slash command 补全
- `@文件` 路径补全
- `artifact:<ref>` 补全
- `session:<id>` 补全

---

## 6. 当前交互流

### 6.1 新建会话

1. 进入 TUI
2. 创建新 session
3. Header 切到当前 session
4. Timeline 显示后续事件流
5. Inspector 默认显示状态摘要

### 6.2 恢复会话

1. 切到 `Sessions` explorer 或使用 `/resume`
2. 恢复选中 session
3. Timeline 从持久化 timeline 重新装载
4. Inspector 可继续查看 summary / plan / artifacts

### 6.3 浏览工作区

1. `Workspace` explorer 展示目录树
2. 选中文件后可预览
3. 选中目录后可继续下钻
4. 可在 composer 中通过 `@文件` 引用路径

### 6.4 编辑单文件

1. 选中文件后进入 `Editor`
2. 在单缓冲中修改内容
3. 保存时通过 adapter 写回工作区
4. Inspector `diff` 可查看保存前 diff 预览

### 6.5 权限确认

1. 收到 `permission_required`
2. Header 切到 `waiting_permission`
3. Composer prompt 切换到 `confirm(y/n)>`
4. 用户输入 `y` / `n`
5. Timeline 继续推进

---

## 7. 事件到 UI 的映射

| Event | 当前 UI 行为 |
|------|--------------|
| `session_created` | 刷新当前 session 与 explorer |
| `session_resumed` | 刷新快照、重载 timeline |
| `turn_started` | Timeline 追加用户输入 |
| `assistant_delta` | 追加到流式 assistant 行 |
| `tool_started` | Timeline 插入工具开始事件 |
| `tool_finished` | Timeline 插入 Observation 摘要 |
| `permission_required` | Header 切 waiting，Composer 切 confirm prompt |
| `context_compacted` | Timeline 追加 context 事件，Inspector 刷新 context 概况 |
| `session_finished` | 刷新 snapshot / summary / artifacts / todos / timeline |
| `session_error` | 记录错误并刷新 Inspector |

---

## 8. Core 数据入口

当前终端前端除了会话型命令，还依赖以下浏览型 adapter 接口：

- `get_workspace_snapshot`
- `list_workspace_tree`
- `read_workspace_file`
- `write_workspace_file`
- `get_session_timeline`
- `list_artifacts`
- `read_artifact`
- `list_todos`

其中：

- timeline 来自 `SessionTimelineStore`
- artifact 来自 `ArtifactStore.index.json` 与 artifact 文件本体
- 文件保存仍通过 adapter 边界，而不是在前端里散落文件写入逻辑

---

## 9. Windows 7 终端约束

当前终端前端继续遵循 Win7 弱宿主约束：

- 不依赖复杂 Unicode 边框
- 不依赖鼠标作为关键路径
- 所有关键操作有纯键盘路径
- 低颜色和 ASCII 环境可读
- `ConEmu` 只是增强宿主，不承载应用逻辑

当前 host 识别分为：

- `raw-console`
- `conemu`

---

## 10. 当前结论

Phase 6 当前终端前端已经不再是“单文件聊天壳”，而是：

**一个围绕 session / workspace / timeline / artifacts / editor 组织的模块化终端前端。**

后续继续细化的重点将是：

- 真实 Win7 控制台与 ConEmu 手工验证
- explorer / editor / plan 交互打磨
- stdio adapter 与未来原生桌面壳复用同一协议
