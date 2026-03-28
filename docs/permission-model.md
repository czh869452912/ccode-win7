# EmbedAgent Permission Model（Phase 5）

> 更新日期：2026-03-28
> 适用阶段：Phase 5 最小权限模型

---

## 1. 文档目标

记录当前已经落地的最小权限控制策略，以及 CLI 如何向用户请求批准。

本版本聚焦：

- 文件写入确认
- 命令与工具链执行确认
- 用户拒绝后的结构化 Observation

---

## 2. 当前策略

### 2.1 默认允许

以下工具默认直接允许：

- `read_file`
- `list_files`
- `search_text`
- `git_status`
- `git_diff`
- `git_log`
- `report_quality`
- `switch_mode`

### 2.2 默认需要确认

以下工具会触发权限确认：

- `edit_file`
- `run_command`
- `compile_project`
- `run_tests`
- `run_clang_tidy`
- `run_clang_analyzer`
- `collect_coverage`

---

## 3. CLI 控制项

当前 CLI 支持：

- `--approve-all`
- `--approve-writes`
- `--approve-commands`

若未使用自动批准参数，CLI 会在执行前提示用户确认。

---

## 4. 拒绝时的行为

若用户拒绝执行：

- Loop 不会直接崩溃
- 系统返回失败 Observation
- Observation 中包含：
  - `permission_required`
  - `category`
  - `reason`
  - `details`

这样模型可以感知“被拒绝”，而不是误以为工具本身失效。

---

## 5. 当前结论

Phase 5 的权限模型已经具备最小可用形态：

- 高风险动作前确认
- 自动批准开关
- 拒绝后的结构化反馈

后续还需要继续补：

- 持久化规则
- allow / ask / deny 三值策略文件
- 更细粒度的路径与命令模式匹配
