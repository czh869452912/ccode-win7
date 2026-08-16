# Pi-Shaped Generic Agent Architecture

> 状态：`proposed`
> 类型：`architecture-design`
> 日期：`2026-08-16`
> 基线：方案 A（沿用现有主干，收紧应用与工作流边界）

## 1. 目标

将 EmbedAgent 收敛为一个可以独立建库、独立导出、独立扩展的通用 Agent 平台：

- `embedagent-core` 类似 Pi 的 `agent`，只负责通用会话执行、持久化和恢复；
- Host 提供可替换的运行时实现，但不拥有具体应用语义；
- Generic application、C/C++ application 以及用户自定义 application 使用同一套应用边界；
- CLI、未来的 TUI/GUI 只是通用 shell，不假定工程语言、模式或工具链；
- `minimal-cli` 不携带、加载或提示任何 C/C++ 专属能力；
- C/C++ workflow 仍然是一等产品能力，但作为可选应用包加入；
- 每个导出制品只包含其选择闭包中的 distribution、runtime capability 和 shell。

本设计不重写已有的 durable session、journal/reducer、extension bus、protocol 和 frontend projection 主干，而是将仍然跨层的应用语义移回应用层。

## 2. 审计结论

当前拆分已经足够支撑后续独立建库，主要问题不是会话算法，而是默认注册、构建闭包和运行时能力仍然偏向 C++：

1. `compile_bundle_plan()` 使用固定的六个 project distributions，导出选择没有真正决定 wheel 集合。
2. 产品注册表直接导入并注册 C/C++ application，根 `embedagent` 包也声明了 C++ distribution 依赖。
3. Core、Host 和 product 仍共同解释五个模式；`modes.py` 还会固定注入中文模式提示框架。
4. Host 的 application profiles 和 workspace intelligence 默认集合包含应用级语义，Ctags/LLVM 也进入全局 runtime catalog。
5. 现有 composition helper 的 component ID 与正式 product catalog 不一致，通用导出 API 尚未成为唯一来源。
6. CLI 将未知运行时异常压缩成 `runtime_error`，不影响边界设计，但需要在迁移中补齐安全诊断契约。

已经确认应当保留的结构：

- `Agent` / `AgentSession` 与 `HostedSessionController`；
- `SessionJournal`、`SessionReducer`、transcript restore 和 event envelope；
- `ContextAssemblerPort`、`ToolRuntimePort`、permission 与 writable-path 分离；
- `AgentLoop` 的 prepare/commit/execute/resume 执行脊柱；
- `ExtensionManager`、`AgentExtensionHost` 和 source-aware event bus；
- Composition manifest/compiler/export 的传递依赖闭包能力；
- 通用 frontend protocol、shell descriptor 和 workflow projection。

## 3. 目标拓扑

```text
Generic CLI / TUI / GUI shell
            |
     Product bootstrap
            |
  Selected Agent Application
       /              \
Generic application   C/C++ application
       \              /
        Generic Host runtime
                |
          Agent Core SDK
```

依赖方向保持向下：Core 不依赖 Protocol、Host、Product、Shell 或 Workflow；Host 不依赖 Product 或 C++；Application 通过声明的 capability 和注入端口参与运行；Product 只负责选择、组合、启动和交付。

## 4. 边界职责

| 层 | 保留职责 | 明确不拥有 |
|---|---|---|
| Core | 通用 AgentSession、turn loop、事件日志、恢复、确定性 reducer、focused ports | profile、固定 mode、应用 prompt、C/C++、workspace intelligence |
| Protocol | JSON-safe DTO、session event、shell/capability projection | 激活工具、权限决定、workflow 默认值 |
| Host | provider/store/tool adapter、context 基础设施、permission、managed session hosting | generic/python/html profile、默认 Ctags/LLVM、产品注册表 |
| Application | prompt、toolset、context provider、可选 modes、workflow state、commands、shell contribution | 改写 Core durable truth、绕过权限或直接执行未声明工具 |
| Product | application catalog、selected registry、launcher、配置、offline assets、bundle plan | C++ 作为根依赖、默认注入应用语义到所有制品 |
| Shell | 收集用户意图、渲染 frozen projection、注册通用交互 | 假设 mode/task/recipe、执行工具、恢复 session |

## 5. Core 设计

### 5.1 无模式核心

`mode` 不再是 Core 执行所必需的概念。Core 可以传递应用状态和 capability metadata，但不解释 `explore`、`spec`、`build`、`debug` 或 `verify`。

目标行为：

- `RuntimeDefinition` 不要求 `default_mode`；
- session 创建、turn dispatch、restore 和 projection 不因缺少 mode 而失败；
- mode transition 不再是 Core 内置 command 或 reducer 分支；
- application state 通过现有 workflow/application state carrier 持久化，由 application extension 解释；
- 前端只有在 capability projection 声明 mode command 时才显示模式 UI。

五模式仍可作为 C/C++ application 的实现细节，但不再是平台词汇或通用默认值。

### 5.2 调用方控制 system prompt

Core 只消费调用方提供的 system prompt/context units，不生成产品提示框架。上层 application resource loader 负责：

- 默认 prompt；
- prompt replacement；
- append prompt；
- context files、skills、tool snippets 和 provider-specific guidelines。

Generic application 的默认 prompt 可以为空或由产品配置提供，但不得自动描述模式、只读权限或 C/C++ 工程上下文。

### 5.3 保持现有执行与恢复不变量

迁移不得改变以下事实：

- event append 在 live reducer publication 之前；
- restore 使用同一组 event families 和 reducer；
- Tool activation、execution、permission、write-path authorization 仍然分离；
- frozen turn snapshot 是 provider request 的唯一解释来源；
- Host 不接收 mutable Core Session，也不创建第二套历史真相。

## 6. Host 与 Application 设计

### 6.1 Host 变成通用运行时

Host 的 built-in registry 只保留通用实现和注册协议。generic/python/html profile factory、模式 tool policy 和应用 empty state 应迁移到对应 application package 或 product application definition。

Host runtime 接收选定 application 的：

- prompt/resource loader；
- active tool names 或 selector；
- workspace intelligence providers；
- runtime capability requirements；
- extension manager/application hooks。

不能通过一个新的通用 service bag 恢复旧耦合；继续使用现有 focused ports 和 extension boundary。

### 6.2 Application Definition

现有 `AgentProductDefinition`/component manifest 应收敛为正式的 application composition contract，至少声明：

- application identity/version；
- prompt/resource sources；
- provider、toolset、context provider 和 extension capability；
- optional mode/command/shell contributions；
- workflow state schema/projection；
- runtime requirements；
- owning distribution 和 registration entry。

通用 application 不需要声明 mode 或 workflow。C/C++ application 可以在同一 contract 中声明五模式、TaskGraph、recipes、quality tools 和 Clang runtime。

### 6.3 Workspace intelligence 与 managed tools

`WorkspaceIntelligenceBroker` 改为基于 capability 注入 provider，默认集合只包含真正通用且被选中的 provider。Ctags、Recipe、Diagnostics、LLVM 等由 C/C++ application 注册。

managed runtime 不再用全局 `MANAGED_RUNTIME_TOOL_KEYS` 判断所有制品的就绪状态，而是根据 selected runtime requirements 检查。`offline-runtime-contract.json` 仍是资产真相，但 bundle plan 只选择其闭包中的 requirement 子集。

## 7. Product、Composition 与 Distribution

### 7.1 按依赖闭包导出

移除固定的 `PORTABLE_PROJECT_DISTRIBUTIONS` 作为正式 bundle 选择依据。编译流程应：

1. 从 recipe/application/shell 解析 component closure；
2. 将 closure 中的 distribution owner 投影为 `project_distribution_ids`；
3. 只构建、安装、staging 和 hash 这些 distribution；
4. 只检查这些 distribution 声明的 runtime requirements；
5. 将实际选中的 distribution 集合写入 `agent.lock.json` 和 release identity。

CI 可以为了验证构建全部 workspace wheels，但任何独立导出制品都不能因 CI 便利而携带未选择的 application package。

### 7.2 C++ 延迟注册

根 product package 不再在模块导入时依赖 C++ workflow。C++ application 通过选定 component 的显式 registration entry 注入；未选择 C++ component 时：

- 不导入 `embedagent_workflow_cpp`；
- 不生成 C++ application record；
- 不激活 Ctags、LLVM、recipes 或 TaskGraph；
- 不把对应 wheel 或 runtime asset 放进 minimal 制品。

### 7.3 独立建库准备

第一阶段只要求源码和 distribution 依赖方向满足独立建库，不立即拆物理 Git repository。后续拆库时，各 application/shell/repository 只需要实现已冻结的 composition、protocol 和 extension contracts，不应再访问 product 私有模块。

## 8. Generic CLI/TUI/GUI 与用户扩展

所有 shell 使用同一套通用 session/projection 协议。应用声明 command、mode、surface、tool presentation 或 interaction 后，shell 才显示对应内容。

用户可以通过以下方式定义上层应用：

- workspace-bound prompt/context/skill/resource 文件；
- manifest-gated、disabled-by-default 的本地 Python extension；
- 离线打包时选择的 application component；
- 显式声明的工具、权限和 runtime requirements。

不引入 remote marketplace、运行时依赖安装、隐式代码执行或内置工具替换。

## 9. 迁移阶段与验收

### Phase 0：契约与护栏

- 新增 architecture boundary tests，拒绝 product->Core 反向依赖和 Host->C++ 默认依赖；
- 增加 minimal artifact 的“无 C++ distribution、无 Ctags/LLVM capability、无 mode prompt”断言；
- 定义新的 application registration 和 runtime requirement contract。

### Phase 1：导出闭包

- 替换固定六 wheel 逻辑；
- 修正 composition helper 与正式 catalog 的 component ID；
- 让 lock、staging、identity、release gates 使用同一 selected distribution 集合。

### Phase 2：Product/Host 解耦

- 删除 product 对 C++ 的硬导入和硬依赖；
- 将 application profiles 从 Host 迁移到 application/product definition；
- 让 C++ 只在选定 component 注册。

### Phase 3：Core 无模式化

- 移除 Core 对 default/current mode 的强制路径；
- 移除 product `_DEFAULT_PROMPT_FRAME`；
- 让 prompt/resource loader 由 application 注入；
- 更新 session projection、CLI、TUI、GUI 的可选 mode capability 处理。

### Phase 4：工具与工作区能力注入

- 将 Ctags/LLVM/recipe/diagnostics provider 移到 C++ application；
- 将 runtime readiness 改为 selected requirement 检查；
- 验证 generic application 只启动显式选择的工具。

### Phase 5：用户应用与诊断

- 暴露通用 application definition/export API；
- 增加 prompt replacement/append 和资源加载测试；
- 将 `runtime_error` 改为带 phase、safe exception type/message、correlation id 的 credential-free failure record；
- 完成文档、release runbook 和独立建库说明同步。

## 10. 必须通过的验收条件

1. `embedagent-core` 可在无 Host、Product、Workflow、Ctags、LLVM 的环境下单独构建和运行 standalone session。
2. `minimal-cli` 的启动输出不出现 `explore`、五模式、C/C++ project memory 或 Ctags capability，除非用户应用显式声明。
3. minimal artifact 的 wheel/runtime/asset/gate 集合不含 C++ workflow 和 LLVM。
4. cpp-desktop 仍能显式获得五模式、TaskGraph、recipes、Ctags、Clang 和对应 shell contribution。
5. 任意用户 application definition 可以替换/追加 system prompt、选择工具并声明 runtime requirements，而无需修改 Core。
6. restore、permission、write-path、event envelope、frontend projection 和 offline Win7 contract 不被破坏。
7. 所有 distribution owner、component manifest、release lock 和 runtime contract 的选择来自同一份 compiled bundle plan。

## 11. 非目标

- 不在本阶段引入通用多 Agent orchestration；
- 不把 workflow state、capability registry 或 snapshot 变成执行权威；
- 不为了兼容旧的内部 mode/profile/reducer 形状而增加代理层；
- 不改变 Windows 7、Python 3.8、offline 和 C/C++ 默认产品的交付要求；
- 不立即进行物理 repository 拆分，先冻结可独立建库的 package contracts。
