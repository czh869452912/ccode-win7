# ADR-0001: Phase 7 离线交付采用 one-folder portable bundle 基线

- 状态：`accepted`
- 日期：2026-03-29（2026-07-12 同步 Python distribution staging 基线）
- 相关文档：
  - `README.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/modules/packaging-and-deployment.md`
  - `docs/guides/win7-preflight-checklist.md`

## 背景

项目的硬约束要求最终交付物在 Windows 7 离线环境中零外部依赖运行。
当前仓库已经实现 portable bundle 组包和仓库侧验证门禁，但真实 Win7 /
WebView2 目标机证据仍是独立的发布条件。

如果不先固定交付物主形态，后续很容易在以下问题上反复变更：

- 先做 portable bundle 还是先做 installer
- 是否允许依赖系统 Python / Git / LLVM
- 如何证明 bundle 的组成完整
- 目标机验收到底以什么为准

## 决策

Phase 7 的首个正式交付基线采用：

1. one-folder portable bundle 作为主交付形态
2. x64 作为首个硬交付目标
3. manifest 驱动的 staging 组包流程
4. launcher 负责设置 PATH 与 Python 运行环境，不依赖系统预装软件
5. bundle 级验证和 Win7 preflight 作为正式验收门
6. 项目 Python 代码以五个独立、已检查的 wheel 进入离线 staging：Core、
   Protocol、Host、Composition 和产品聚合包
7. dependency export 只从 clean wheelhouse 安装项目 distribution，禁止把
   editable 开发树或未经检查的源码目录作为 bundle 输入
8. 第三方 Python 依赖是独立、受控的构建时步骤，可构建 lock 固定的
   sdist；五个项目 distribution 自身必须只从已检查 wheel 安装

Installer、one-file 单 exe 和 x86 包均不作为首个交付增量的前提条件。

## 影响

收益：

- 与“解压即用、零外部依赖”的目标一致
- 更容易做缺件排查、checksum 校验和 license 追踪
- 更适合携带 clang/git/rg/ctags 等外部工具
- wheel 内容归属、依赖方向和离线安装可以在组包前独立验证

代价：

- 产物目录较大
- 需要维护 manifest、checksums 和第三方来源记录
- 需要同步维护五个 distribution 的 metadata、wheel 边界和隔离导入门禁
- 首个版本的“安装体验”不如 installer 方案简洁

受影响模块：

- Phase 7 构建脚本
- launcher 设计
- toolchain/bundle manifest
- Win7 验收流程
- Python workspace metadata、wheel build/check/smoke 和 dependency export

## 备选方案

### 方案 A：one-file 单 exe

放弃原因：

- 对 clang/git/rg/ctags 这类外部工具不友好
- DLL 与缺件问题更难排查
- 不适合作为 Win7 首个交付形态

### 方案 B：installer-first

放弃原因：

- 会把“安装器逻辑”和“bundle 自包含能力”混在一起
- 增加管理员权限、系统写入和回滚复杂度
- 不利于先证明“解压即用”

### 方案 C：依赖系统预装 Python / Git / LLVM

放弃原因：

- 直接违反项目硬约束
- 目标机环境不可控，无法形成正式交付

## 当前验收边界

仓库侧必须通过 clean wheel build、wheel ownership/dependency 检查、精确
Python 3.8 的 no-index/no-deps 隔离安装、bundle 静态/动态检查，以及
bundle-local C smoke。外部 wheelhouse 只能包含普通 wheel 文件，不能经过
reparse point；任何未知文件都应使构建失败而不是被删除。

wheel dependency 检查证明五个项目 distribution 之间的 exact DAG，不代表
对所有第三方依赖版本的完整审计。隔离安装场景覆盖五个项目 distribution
的导入边界，但不启动完整 GUI、provider 或 hosted runtime。正式组包由独立
`doctor` 预检后运行一次 `release`，后者内部执行 deps、assemble、verify。
当前 `proxy-tools==0.1.0` 需要锁定 sdist 构建；为全部第三方依赖策划可审计
的 binary wheel 来源、license 与 hash 是 release hardening，不是 Phase 2
已完成声明。构建结果进入 bundle 后，目标 runtime 仍不得访问网络或编译依赖。

这些结果不替代目标机证据。正式 Win7 GUI 声明仍要求在 clean target-style
bundle 上完成 windowed smoke，并证明 renderer 使用 bundle 内 Fixed Version
WebView2 109。该证据和更广泛真实 C/C++ 项目验证仍是发布前剩余项。
