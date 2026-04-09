# EmbedAgent 离线打包操作指南

> 目标：通过统一控制面构建完全自包含、零外部依赖、可交付的离线 bundle
> 适用：物理隔离内网环境（无互联网，仅有内网大模型服务）
> 更新日期：2026-04-02

---

## 1. 公共入口

离线打包现在对外统一使用：

```powershell
pwsh -File scripts/package.ps1 <command>
```

公开子命令：

```powershell
pwsh -File scripts/package.ps1 doctor
pwsh -File scripts/package.ps1 deps
pwsh -File scripts/package.ps1 assemble -Profile dev
pwsh -File scripts/package.ps1 verify -BundleRoot build/offline-dist/embedagent-win7-x64
pwsh -File scripts/package.ps1 release
```

操作层面不再推荐直接记忆和串联：

- `scripts/export-dependencies.py`
- `scripts/prepare-offline.ps1`
- `scripts/build-offline-bundle.ps1`
- `scripts/validate-offline-bundle.ps1`
- `scripts/check-bundle-dependencies.py`

这些脚本仍然存在，但现在属于内部 stage 或兼容入口，不是主要操作界面。

---

## 2. 命令说明

### `doctor`

检查当前开发机是否具备打包条件，并输出控制面可见的配置/脚本路径状态。

```powershell
pwsh -File scripts/package.ps1 doctor
pwsh -File scripts/package.ps1 doctor -Json
```

### `deps`

准备 Python 依赖导出和第三方资产所需的缓存/前置结果。

```powershell
pwsh -File scripts/package.ps1 deps
```

### `assemble`

组装 bundle，但默认偏开发态。

```powershell
pwsh -File scripts/package.ps1 assemble -Profile dev
```

适合：

- 本机快速验证
- 先看包体结构
- 不急着出最终 release zip

### `verify`

只验证已有 bundle，不重新构建。

```powershell
pwsh -File scripts/package.ps1 verify -BundleRoot build/offline-dist/embedagent-win7-x64
```

### `release`

正式推荐入口。默认走更严格的 release 流程。

```powershell
pwsh -File scripts/package.ps1 release
pwsh -File scripts/package.ps1 release -Json
```

`release` 会统一完成：

1. 依赖准备
2. bundle 组装
3. bundle 验证
4. 报告输出
5. 最终状态判定

---

## 3. 推荐工作流

### 3.1 日常开发打包

```powershell
pwsh -File scripts/package.ps1 doctor
pwsh -File scripts/package.ps1 assemble -Profile dev
pwsh -File scripts/package.ps1 verify -Profile dev -BundleRoot build/offline-dist/embedagent-win7-x64-dev
```

这条路径的目标是：

- 快速出一个本机可验证的 bundle
- 尽量缩短迭代时间
- 不宣称 release ready

### 3.2 正式发布打包

```powershell
pwsh -File scripts/package.ps1 release
```

如果需要给自动化或上层脚本消费：

```powershell
pwsh -File scripts/package.ps1 release -Json
```

---

## 4. Profile 与最终状态

### `dev`

面向：

- 本机构建
- 调试 bundle
- 迭代验证

可能得到的最终状态：

- `DEV_ONLY`
- `NOT_READY`

### `release`

面向：

- 正式打包
- Win7 交付准备

可能得到的最终状态：

- `READY`
- `NOT_READY`

### 最终状态含义

- `READY`
  - 当前 bundle 满足 release 门禁
- `DEV_ONLY`
  - 当前 bundle 可用于开发验证，但不能视为正式交付物
- `NOT_READY`
  - 当前 bundle 未通过必需门禁

---

## 5. 报告输出

控制面会把机器可读报告写到：

```text
build/offline-reports/latest.json
build/offline-reports/<timestamp>-<command>.json
```

报告至少包含：

- `command`
- `profile`
- `final_status`
- `blocking_issues`
- `warnings`
- `report_path`
- 阶段级结果（如已执行）

如果你只想知道这次打包是否可交付，优先看：

- `final_status`
- `blocking_issues`

---

## 6. 常见操作

### 6.1 检查打包环境

```powershell
pwsh -File scripts/package.ps1 doctor -Json
```

### 6.2 做一次 dev 组装

```powershell
pwsh -File scripts/package.ps1 assemble -Profile dev
```

### 6.3 对已有 bundle 复验

```powershell
pwsh -File scripts/package.ps1 verify -BundleRoot build/offline-dist/embedagent-win7-x64
```

### 6.4 输出一份 release 结果给自动化消费

```powershell
pwsh -File scripts/package.ps1 release -Json > build/offline-reports/release-console.json
```

---

## 7. 内网部署简表

在外网/构建机：

```powershell
pwsh -File scripts/package.ps1 release
```

在内网目标机：

1. 解压 zip
2. 按 [docs/win7-preflight-checklist.md](D:/Claude-project/ccode-win7/.worktrees/codex-package-control-plane-redesign/docs/win7-preflight-checklist.md) 检查环境
3. 按 [docs/intranet-deployment.md](D:/Claude-project/ccode-win7/.worktrees/codex-package-control-plane-redesign/docs/intranet-deployment.md) 配置内网模型服务
4. 用 bundle 内 launcher 启动 CLI/TUI/GUI

---

## 8. 故障排查

### `doctor` 就失败

通常说明：

- `scripts/package.config.json` 路径不对
- 资产 manifest 路径不对
- 某个内部 stage 脚本缺失

优先看：

```powershell
pwsh -File scripts/package.ps1 doctor -Json
```

### `release` 返回 `NOT_READY`

优先看：

- `build/offline-reports/latest.json`
- 其中的 `blocking_issues`

### 想知道底层到底调用了哪些 stage

控制面当前仍会复用内部 stage 脚本，因此可以在报告里看到阶段级摘要和路径；但日常操作不需要直接调用它们。

---

## 9. 内部 Stage 说明

以下脚本仍然保留，用于控制面内部复用或兼容：

- `scripts/export-dependencies.py`
- `scripts/prepare-offline.ps1`
- `scripts/build-offline-bundle.ps1`
- `scripts/validate-offline-bundle.ps1`
- `scripts/check-bundle-dependencies.py`

除非你在维护控制面本身，否则不建议把它们当作主要操作入口。

---

## 10. 一句话口径

离线打包的公共操作方式现在是：

```powershell
pwsh -File scripts/package.ps1 release
```

如果不是在调试控制面本身，就从这条命令开始。
