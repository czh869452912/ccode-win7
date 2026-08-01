# Documentation Style Guide

> 状态：`active`
> 类型：`reference`
> 负责人：`project maintainers`
> 最后同步日期：`2026-08-01`

## Write For Navigation

先写读者意图、权威结论和下一跳链接。入口和全局文档使用渐进披露：概述只保留理解边界所需的信息，文件、控制器、事件字段和局部规则放入拥有它们的模块或契约文档。

## Metadata

活跃 authority、guide、workflow 和 current-work 文档应在标题后给出：

```markdown
> 状态：`active|target|archive`
> 类型：`architecture|contract|module|guide|workflow|status|roadmap|reference`
> 负责人：`...`
> 最后同步日期：`YYYY-MM-DD`
```

归档包用归档日期和当前真相入口替代活跃状态信息。

## Language And Terms

- 中文用于协作说明，代码标识、命令、路径、协议字段和官方英文术语保持原样。
- 使用项目官方词汇；退役名称只能出现在明确的 removed/forbidden 历史语境中。
- 命令必须可复制，路径必须仓库相对且可验证。
- 结论优先于过程；避免“最近做了什么”式叙事。

## Structure By Owner

- Entry：产品/约束摘要、常用命令、任务导航。
- Map：意图、首读文档、下一跳、禁止作为当前真相的来源。
- Architecture：范围、所有权、跨层数据流、不变量、验证触发器。
- Module/contract：代码范围、入口、数据流、约束、测试、相关权威。
- Current status：当前状态、焦点、阻塞、下一步、证据边界。
- Roadmap：开放项目、顺序、退出条件。
- Workflow/guide：触发条件、步骤、验证、失败/回滚边界。
- Archive index：材料清单、归档原因、当前权威入口。

## Prohibited Patterns

- 不在活跃文档追加 completion chronology、逐日期验证流水或已完成阶段目录。
- Entry、architecture 和 current-work 文档不得出现 `Recent Work`、`Completion`、`Completed Phases` 或每个切片一个日期章节。
- 不在多个文档重复组件、控制器、文件或工具清单；清单只放在拥有它的模块或契约。
- 不把 archive 链接描述成当前 contract、required reading 或实施入口。
- 不创建新的全局 tracker/change-log 文档作为每次变更的强制回填点。
- 不接受没有拆分计划和所有者说明的上下文预算例外。

## Tables And Diagrams

只有当比较、所有权或数据流比短段落更清楚时才使用表格或 Mermaid。图中的节点名必须对应官方边界，且正文说明谁拥有状态和决策。不要用图重复源码目录树。

## Review Checklist

- 是否能从 `docs/README.md` 按意图到达？
- 是否只更新了事实的一个所有者？
- 是否删除了被替代的旧表述？
- 是否满足上下文预算并避免完成流水？
- 路径、命令、名称和链接是否可机械验证？
- 已关闭材料是否进入带索引的 archive package？
