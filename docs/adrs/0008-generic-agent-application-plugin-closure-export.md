# ADR-0008: 通用 Agent、应用插件与依赖闭包导出

- 状态：`accepted`
- 日期：2026-08-17
- 相关文档：
  - `docs/superpowers/specs/2026-08-16-pi-shaped-generic-agent-architecture-design.md`
  - `docs/overall-solution-architecture.md`
  - `docs/platform/agent-platform-blueprint.md`

## 背景

项目已经完成 Core session、replay、permission、Host boundary 和 extension bus 的多轮收敛，
但产品选择层仍把通用 Agent 与 C/C++ workflow 绑定在一起。固定六 wheel、product 对 C++ 的
模块级导入、Host 默认 C++ workspace provider、Core 的固定 mode/prompt 以及重复的 application
catalog，使得 generic agent 无法独立导出，也阻碍 C/C++ workflow 以后独立建库。

Pi 将通用 agent runtime 与 coding application 分开；DeepSeek Harness 将模型、工具、session、
loop 和 shell 作为可组合插件，并要求依赖驱动加载和可逆注册。本项目吸收这些边界思想，但
保留 Python 3.8、Windows 7、offline、确定性 restore 和 focused ports，不引入动态共享 service
bag、远程 marketplace 或运行时依赖安装。

## 决策

1. `embedagent-core` 保持 workflow-neutral，只负责 Agent/AgentSession、turn execution、durable
   event、restore、确定性 reducer 和 focused extension contracts。mode、profile、产品 prompt、
   workspace intelligence 和 C/C++ 不属于 Core。
2. `embedagent-host` 只提供通用 provider、store、tool/runtime、permission、context 和 hosted
   session 实现。应用级 provider 必须由 selected application 注册。
3. 通用 shell/bootstrap 成为运行时基线，目标名称为 `embedagent-shell`。它只消费 frozen
   projection 和 capability descriptors，不认识 C/C++ 语义。
4. 每个 application plugin 由静态 manifest 加显式 registration entry 组成。依赖、capability、
   prompt/resource、shell contribution、runtime requirement 和 asset ownership 都在 manifest 中
   声明；注册通过 `AgentExtensionHost`、focused ports 和 source-aware event bus 完成，并可逆卸载。
5. C/C++ workflow 是 selected application plugin。它拥有 mode、TaskGraph、recipes、Ctags、
   diagnostics、Clang/LLVM 和 C++ shell contribution，generic product 不得导入或依赖它。
6. `embedagent-composition` 只负责构建期 manifest/compiler/export；运行时和发布制品不再固定
   携带它或其他未选择 distribution。
7. bundle export、wheel staging、runtime assets、release gates、lock 和 evidence 全部消费同一份
   closure-derived compiled plan。固定六 wheel 不再是正式产品契约。
8. 暂不立即拆物理 Git repository；先冻结 application/plugin contract，使 C++ 仓库之后只依赖
   公共 Core/Protocol/Composition contract。

## 影响

收益：generic agent 可以在没有 C++ wheel、Clang、Ctags、mode prompt 或 C++ registry 的环境中
独立运行；C++ workflow 可以作为默认产品 flavor 继续交付，也可以从主仓库独立发布；新增工作流
不需要修改 Core、Host 或通用 shell；每个 offline artifact 的依赖和资产都可审计。

代价：需要删除旧的六 wheel、profile/mode、默认 registry 和 product import 路径；现有 C++ 默认
产品的 catalog、shell 和 runtime tests 需要迁移到 application plugin；release 文档和 `AGENTS.md`
中的固定六 wheel 表述必须同步修订。

## 备选方案

- **完整 Cordis 化**：采用动态共享 context、运行时 HMR 和 service registry。放弃，因为它会扩大
  Core surface，削弱 Python 3.8/offline 可验证性，并与 focused ports 冲突。
- **只做条件依赖**：保留六 wheel和 mode/profile，只在未安装 C++ 时跳过导入。放弃，因为物理
  依赖、runtime catalog 和产品语义仍然耦合，不能支持真正独立导出。
- **立即拆成多个 Git 仓库**：放弃作为当前步骤；先冻结契约和 closure export，避免把未收敛的
  内部形状复制到多个仓库。

## 后续动作

- 按已接受 spec 的阶段拆分实施计划；
- 先建立 application manifest、registration entry、runtime requirement 和 closure plan 的
  测试护栏，再删除旧固定契约；
- 完成 Core/Host/Product 解耦后，更新 packaging、Win7 runbook、code-doc matrix 和独立建库说明。
