# 模块文档索引

> 状态：`active`
> 类型：`reference`
> 负责人：`project maintainers`
> 最后同步日期：`2026-04-08`
> 对应代码范围：`src/embedagent/`, `docs/modules/`

## 1. 当前已建立模块

- `agent-core.md`
- `session-runtime.md`
- `harness.md`
- `tools-and-tooling.md`
- `permissions-and-context.md`

## 2. 后续模块

- `protocol-and-core.md`
- `frontend-tui.md`
- `frontend-gui.md`
- `packaging-and-deployment.md`

## 3. 模块文档维护规则

- 模块文档记录长期有效的模块职责、入口文件、上下游边界、验证入口和相关契约。
- 当模块职责、入口文件、关键数据流或测试入口变化时，模块文档必须在同一轮变更中更新。
- 模块文档不替代根目录架构文档；它们负责把项目级结论落到具体代码域。

## 4. 与全局文档的关系

- 根目录架构文档定义全局主链路和正式术语。
- 模块文档定义具体代码域的稳定职责和映射关系。
- `docs/references/code-doc-matrix.md` 负责把两者连接起来。
