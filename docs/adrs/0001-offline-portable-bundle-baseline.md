# ADR-0001: Phase 7 离线交付采用 one-folder portable bundle 基线

- 状态：`accepted`
- 日期：2026-03-29
- 相关文档：
  - `README.md`
  - `docs/overall-solution-architecture.md`
  - `docs/implementation-roadmap.md`
  - `docs/offline-packaging.md`
  - `docs/win7-preflight-checklist.md`

## 背景

项目的硬约束要求最终交付物在 Windows 7 离线环境中零外部依赖运行，
但当前仓库尚未进入真正的 Phase 7 组包实现阶段。

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

Installer、one-file 单 exe 和 x86 包均不作为首个交付增量的前提条件。

## 影响

收益：

- 与“解压即用、零外部依赖”的目标一致
- 更容易做缺件排查、checksum 校验和 license 追踪
- 更适合携带 clang/git/rg/ctags 等外部工具

代价：

- 产物目录较大
- 需要维护 manifest、checksums 和第三方来源记录
- 首个版本的“安装体验”不如 installer 方案简洁

受影响模块：

- Phase 7 构建脚本
- launcher 设计
- toolchain/bundle manifest
- Win7 验收流程

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

## 后续动作

1. 建立 `docs/offline-packaging.md` 作为 Phase 7 设计基线
2. 建立 `docs/win7-preflight-checklist.md` 作为目标机验收清单
3. 规划 `prepare/build/validate` 三类打包脚本
4. 固化第三方二进制来源、版本、校验和与 License 清单
5. 在 Win7 虚拟机上按 preflight 口径完成首轮 bundle 验收
