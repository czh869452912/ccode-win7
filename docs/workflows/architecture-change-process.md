# Architecture Change Process

> 状态：`active`
> 类型：`workflow`
> 负责人：`project maintainers`
> 最后同步日期：`2026-04-08`
> 对应代码范围：`README.md`, `AGENTS.md`, `docs/`, `src/embedagent/`

## 1. When This Workflow Applies

当改动会影响以下任一项时，使用本流程：

- 官方架构主链路
- 正式术语
- 模式、权限、协议、任务或会话模型
- 模块边界或长期维护规则

## 2. Required Inputs

- 当前问题陈述
- 受影响代码区域
- 当前活动 `source-of-truth` 文档
- 本轮 `superpowers` 设计与计划文档

## 3. `superpowers` Design Output

- 使用 `superpowers` 产出当前切片 design/spec
- 明确范围、非目标、长期结论与验收条件
- 明确哪些结论最终需要进入全局项目文档

## 4. Global Doc Sync Rules

- `superpowers` 文档只服务当前切片，不直接替代全局真相
- 实现完成后，长期有效的结论必须回写：
  - `README.md`
  - `AGENTS.md`
  - 对应根目录契约文档
  - 对应模块文档
- 若变更属于长期决策，应补 `ADR`

## 5. Review Gates

- 设计获批后再进入实现
- 实现完成后必须通过代码验证与文档验证
- 在归档前必须确认全局文档已完成同步

## 6. Closeout Rules

- 更新 `development-tracker.md`
- 更新 `design-change-log.md`
- 必要时新增或更新 `ADR`
- 完成后把本轮 `superpowers` 文档移入 `docs/archive/`
