# Documentation Governance

> 状态：`active`
> 类型：`workflow`
> 负责人：`project maintainers`
> 最后同步日期：`2026-04-08`
> 对应代码范围：`README.md`, `AGENTS.md`, `docs/`

## 1. Purpose

本文件定义 EmbedAgent 仓库的文档治理规则，目标是把活动文档、切片文档和历史文档分层管理，并建立“代码与文档同步开发”的默认闭环。

## 2. Document Layers

### 2.1 `superpowers` process docs

- 位置：`docs/superpowers/specs/`、`docs/superpowers/plans/`
- 角色：当前一轮切片说明书
- 用途：记录本轮设计、计划、范围、约束、验收条件和 review 结果
- 规则：不作为长期架构真相；切片完成后必须回写全局文档并归档

### 2.2 global project docs

- 位置：`README.md`、`AGENTS.md`、`docs/` 活动文档、`docs/modules/`、`docs/workflows/`、`docs/references/`、`docs/templates/`
- 角色：长期 `source-of-truth`
- 用途：定义当前官方术语、架构边界、模块职责、维护规则和标准模板
- 规则：必须与当前代码和当前官方口径保持同步

### 2.3 archive docs

- 位置：`docs/archive/`
- 角色：历史留痕
- 用途：保存已完成切片的设计、计划、分析、实现说明、复盘和 handoff 文档
- 规则：可用于历史参考，但不能替代活动文档承担当前真相职责

## 3. Source-of-Truth Rules

- 产品级长期真相由 `README.md`、`AGENTS.md` 和根目录官方契约文档承担。
- 模块级长期真相由 `docs/modules/` 承担。
- 治理规则、术语、模板和流程由 `docs/` 活动文档承担。
- `superpowers` 文档只服务当前切片，不应直接被视为全局项目基线。

## 4. Active Document Types

- `architecture`：说明当前官方架构和系统主链路
- `module`：说明某个代码域的职责、边界和验证入口
- `workflow`：说明开发、同步、发布和归档流程
- `guide`：说明配置、部署、验证等操作方法
- `reference`：提供术语表、图表规范和代码-文档映射
- `adr`：记录长期有效的重要决策
- `tracker`：维护当前阶段和风险
- `changelog`：记录已发生的关键设计变更

## 5. Ownership And Update Rules

- 修改架构或 workflow 假设时，必须同步更新对应 `source-of-truth` 文档。
- 修改模块职责、入口文件、上下游边界或验证方式时，必须同步更新对应模块文档。
- 每轮切片设计完成后，活动期以 `superpowers` 文档为当前工作说明；切片完成后必须回写长期真相。
- 活动文档应始终使用当前官方词汇，不回流旧术语。

## 6. Code-Doc Sync Policy

- 任何会影响正式术语、协议、模块职责、部署方式、测试入口或用户可见工作流的变更，都必须评估文档影响面。
- 架构与协议类变化优先更新契约文档，再实施代码。
- 代码实现完成后，必须检查是否需要更新：
  - 全局项目文档
  - 模块文档
  - `development-tracker.md`
  - `design-change-log.md`
  - 必要时 `ADR`

## 7. Archive Policy

- 已完成切片的 `superpowers` 文档应移动到 `docs/archive/<topic>/`。
- 归档前必须先完成全局文档和模块文档回写。
- archive 应包含主题索引，便于回溯，但活动文档不应把 archive 当成当前真相依赖。

## 8. Related Documents

- `docs/documentation-style-guide.md`
- `docs/workflows/code-doc-sync.md`
- `docs/workflows/architecture-change-process.md`
- `docs/references/glossary.md`
- `docs/references/code-doc-matrix.md`
