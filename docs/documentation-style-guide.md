# Documentation Style Guide

> 状态：`active`
> 类型：`reference`
> 负责人：`project maintainers`
> 最后同步日期：`2026-07-19`
> 对应代码范围：`docs/`

## 1. Language Rules

- 采用中文主叙述。
- 路径、类名、函数名、字段名、模式名、工具名、接口名保留英文原文，并使用反引号。
- 文档说明使用现在时，描述当前生效状态；历史说明必须显式标注。

## 2. Metadata Block

活动文档在标题下方应至少提供以下元信息：

- `状态`
- `类型`
- `负责人`
- `最后同步日期`
- `对应代码范围`

示例：

```md
> 状态：`active`
> 类型：`module`
> 负责人：`project maintainers`
> 最后同步日期：`2026-04-08`
> 对应代码范围：`packages/embedagent-workflow-cpp/src/embedagent_workflow_cpp/`
```

## 3. Required Sections By Document Type

`architecture`、`module`、`workflow` 文档应至少包含：

1. 目的与范围
2. 适用对象
3. 官方结论 / 当前规则
4. 代码对应关系
5. 关键流程或数据流
6. 验证与回归入口
7. 变更触发条件
8. 相关文档

`guide`、`reference`、`adr`、`tracker` 可使用更合适的结构，但仍应保持职责单一、标题稳定。

## 4. Terminology Rules

- 活动文档必须使用当前官方词汇。
- 历史术语只允许出现在“兼容说明”或“历史说明”中。
- 下列历史词汇不得在活动文档中作为正式术语使用；若必须提及，
  必须同时说明它们已被移除、禁止或不属于当前架构：
  - `code` 作为 first-class mode
  - retired todo vocabulary
  - retired todo-management tool name（禁止作为当前正式术语）

## 5. Code Mapping Rules

每篇模块文档必须显式提供：

- 代码目录
- 入口文件
- 核心对象
- 上游依赖
- 下游影响
- 相关测试
- 相关契约文档

这部分应使用稳定字段名，便于人工 review 与后续脚本检查。

## 6. Mermaid And Diagram Rules

- 优先使用 Markdown 内嵌 Mermaid。
- 架构总览文档至少包含 1 张系统分层或主链路图。
- 模块文档在存在多组件交互时至少包含 1 张组件图或时序图。
- 工作流文档至少包含 1 张流程图。
- 状态密集型主题优先使用 `stateDiagram-v2` 或 `sequenceDiagram`。

## 7. Historical Content Rules

- superseded 内容应迁入 `docs/archive/`，而不是长期留在活动入口中平铺。
- 如活动文档必须提及历史路径，应明确写出“历史说明”或“兼容说明”。
- archive 负责保留上下文，活动文档负责保留当前真相。

## 8. Review Checklist

- 标题、元信息和章节是否完整
- 是否使用当前官方术语
- 路径、类型名、工具名是否与代码一致
- 是否包含必要的代码映射块
- 是否在要求场景下提供 Mermaid 图
- 是否错误地把历史内容写成当前口径
