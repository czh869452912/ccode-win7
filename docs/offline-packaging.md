# EmbedAgent 离线打包与交付设计

> 更新日期：2026-03-29
> 适用阶段：Phase 7 设计基线

---

## 1. 文档目标

把 Phase 7 的离线打包目标、交付形态、目录布局、组件清单、构建流水线和验证口径固定下来，
避免后续在“先做安装器还是先做 portable bundle”“哪些工具必须随包交付”“如何证明 bundle 真的自包含”这些问题上反复摇摆。

本文件关注的是：

- Phase 7 的**交付设计**
- bundle 的**最小必须组成**
- 本地构建与目标机验收的**统一口径**

本文件不负责：

- 真实 C 工程默认 recipe 的确定
- Win7 实机最终验证结果本身
- 第三方二进制的下载与组装实现细节

---

## 2. 当前出发点

截至 2026-03-29，仓库中与 Phase 7 直接相关的现状如下：

| 项目 | 当前状态 | 备注 |
|------|----------|------|
| Python 运行时 | `integrated` | 已通过 `scripts/offline-assets.json` 接入官方 `3.8.10` embeddable zip，并进入 prepare/build/validate 流水线 |
| Python 依赖锁定 | `ready` | `uv.lock` + `pyproject.toml` 已存在，当前三方依赖面较小 |
| LLVM/Clang 工具链 | `provisional` | `toolchains/llvm/current` 已组装并通过本地 smoke test，但 Win7 与真实工程仍未收口 |
| MinGit portable | `integrated` | 已通过 `scripts/offline-assets.json` 接入 Win7 兼容的 `2.46.2.windows.1` MinGit zip，并进入 prepare/build/validate 流水线 |
| ripgrep | `integrated` | 已通过 `scripts/offline-assets.json` 接入官方 Windows x64 zip，并进入 prepare/build/validate 流水线 |
| Universal Ctags | `integrated` | 已通过 `scripts/offline-assets.json` 接入官方 x64 zip，并进入 prepare/build/validate 流水线 |
| 前端依赖 | `ready` | `prompt_toolkit` / `rich` 已在开发环境验证 |
| bundle 构建脚本 | `in_progress` | `prepare/build/validate` 三段脚本已落地，且 Python / MinGit / rg / ctags 四类核心资产已完成真实接入；当前缺口转为 site-packages 精简与 Win7 实机收口 |
| Win7 前置检查脚本 | `in_progress` | `scripts/validate-offline-bundle.ps1` 已能校验真实 Python / MinGit / rg / ctags / sources seed，仍待补最终 Win7 实机结果 |

当前代码面已经明确会在运行时直接或间接依赖：

- Python 3.8 解释器
- vendored Python 包
- `git.exe`
- `clang.exe`
- `clang-tidy.exe`
- `clang-analyzer.bat`
- `llvm-profdata.exe`
- `llvm-cov.exe`
- Windows 自带 `taskkill.exe`

虽然当前代码尚未直接调用 `rg.exe` 与 `ctags.exe`，但根据 `AGENTS.md` 的硬约束，最终离线交付仍必须包含它们。

---

## 3. Phase 7 MVP 决策

### 3.1 交付物主形态

Phase 7 的首个可交付物采用：

- **one-folder portable bundle**
- **x64 作为首个硬交付目标**
- **zip 压缩包 + 解压后的目录树** 作为发布形态

不在首个增量中追求：

- one-file 单 exe
- MSI / NSIS / Inno Setup 安装器
- 需要管理员权限的系统级安装

这样做的原因：

- 更符合“零外部依赖、解压即用”的硬约束
- 更容易核对缺失文件、License 和校验和
- 更便于排查 Win7 上的 DLL / PATH / 控制台宿主问题
- 与 clang/git/rg/ctags 这类外部二进制随包分发的形态天然一致

### 3.2 交付边界

Phase 7 MVP 只解决：

- 在**全新 Windows 7 x64** 机器上解压可运行
- 不依赖系统 Python / Git / LLVM / Node / Docker
- CLI 与 TUI 均能从 bundle 启动
- 运行时用到的第三方工具都在 bundle 内可定位

Phase 7 MVP 暂不承诺：

- x86 包同时交付
- 自动安装系统补丁
- 自动注册右键菜单、桌面快捷方式或文件关联

### 3.3 打包路线

Phase 7 采用“**manifest 驱动的 staging 打包**”：

1. 收集第三方原始资产
2. 归一化到 staging 目录
3. 复制应用代码与 vendored Python 依赖
4. 生成 bundle manifest / checksum / license 清单
5. 做 bundle 级验证
6. 压缩成 portable zip

该路线要求**先有 staging 再有压缩包**，不允许直接从开发环境目录“就地打包”。

---

## 4. 目标目录布局

建议的 bundle 根目录如下：

```text
EmbedAgent/
├── embedagent.cmd
├── embedagent-tui.cmd
├── manifests/
│   ├── bundle-manifest.json
│   ├── checksums.txt
│   └── licenses/
├── runtime/
│   ├── python/
│   └── site-packages/
├── app/
│   └── embedagent/
├── bin/
│   ├── git/
│   ├── rg/
│   ├── ctags/
│   └── llvm/
├── config/
│   ├── config.json
│   └── permission-rules.json
├── data/
│   └── workspace-template/
└── docs/
    ├── configuration-guide.md
    └── win7-preflight-checklist.md
```

说明：

- `embedagent.cmd`
  - CLI 统一入口
  - 负责设置 `PATH`、`PYTHONHOME`、工作目录与默认环境变量
- `embedagent-tui.cmd`
  - TUI 统一入口
  - 在 CLI 入口基础上补 `--tui`
- `runtime/python/`
  - Python 3.8 embeddable distribution
- `runtime/site-packages/`
  - 从 `uv.lock` 和构建环境导出的 vendored 三方包
- `app/embedagent/`
  - 从 `src/embedagent/` 复制出的运行时代码
- `bin/git/` / `bin/rg/` / `bin/ctags/` / `bin/llvm/`
  - 所有外部工具的 bundle 内固定位置

---

## 5. 必须随包交付的组件清单

| 组件 | 目标位置 | 来源基线 | 当前状态 |
|------|----------|----------|----------|
| Python 3.8 embeddable distribution | `runtime/python/` | Python 官方嵌入式发行包 | `integrated` |
| vendored Python packages | `runtime/site-packages/` | `uv.lock` + 构建脚本导出结果 | `integrated` |
| EmbedAgent 应用代码 | `app/embedagent/` | `src/embedagent/` | `ready` |
| MinGit portable | `bin/git/` | Git for Windows / MinGit 便携包 | `integrated` |
| ripgrep | `bin/rg/` | 官方 Windows 可执行文件 | `integrated` |
| Universal Ctags | `bin/ctags/` | 官方 Windows 可执行文件 | `integrated` |
| LLVM/Clang bundle | `bin/llvm/` | 当前 `toolchains/llvm/current` 收敛版 | `provisional` |
| 默认配置模板 | `config/` | 仓库模板文件 | `integrated` |
| bundle manifest / checksums / licenses | `manifests/` | Phase 7 构建脚本生成 | `working` |

附加约束：

- 任一运行时路径如果会调用某个工具，该工具必须能在 bundle 内定位到。
- 不允许依赖目标机环境变量中的 `PATH` 提供 `git`、`clang`、`python`、`rg`、`ctags`。
- Python 包必须以“已经解包可导入”的形式随包带入，不能把“目标机再离线安装”当作交付步骤。

---

## 6. Launcher 与运行时引导设计

### 6.1 launcher 职责

`embedagent.cmd` / `embedagent-tui.cmd` 需要负责：

- 定位 bundle 根目录
- 把 `bin/git/`、`bin/rg/`、`bin/ctags/`、`bin/llvm/bin/` 预置到 `PATH`
- 调用 bundled Python 解释器
- 把 `app/` 与 `runtime/site-packages/` 注入 Python 搜索路径
- 预设 `EMBEDAGENT_HOME`、默认配置目录和工作区模板位置

### 6.2 Python 搜索路径策略

优先方案：

- 使用 embeddable distribution 自带的 `._pth` 文件固定 `app/` 与 `runtime/site-packages/`

备选方案：

- launcher 显式设置 `PYTHONPATH`

设计原则：

- 不能依赖系统已安装 Python
- 不能依赖 `pip install`
- 不能依赖用户手动复制 `.venv`

### 6.3 配置文件策略

首个 portable bundle 默认只带模板配置：

- `config/config.json`
- `config/permission-rules.json`

用户级、项目级实际配置仍由运行时按现有代码逻辑读取：

- 用户级：`~/.embedagent/config.json`
- 项目级：`<workspace>/.embedagent/config.json`

portable bundle 自带的 `config/` 主要用于：

- 提供参考模板
- 给“开箱即用演示环境”提供默认样例

---

## 7. 构建流水线设计

### 7.1 建议脚本分工

当前与计划脚本如下：

| 脚本 | 作用 |
|------|------|
| `scripts/prepare-offline.ps1` | 已落地；生成 `build/offline-staging/EmbedAgent/`、launcher、模板配置、`bundle-manifest.json` 与 `checksums.txt`，并可按参数复制可选资产 |
| `scripts/build-offline-bundle.ps1` | 已落地；把 staging bundle 复制到 `build/offline-dist/<artifact>/`，重写 dist 上下文 manifest，重算 checksum，并生成 zip |
| `scripts/validate-offline-bundle.ps1` | 已落地；可校验 bundle 根目录、manifest、checksum、关键文件存在性，并支持 `-RequireComplete` 切换到严格门禁 |

当前边界：

- `prepare-offline.ps1` 已支持 `-SkipBuild`，可在资产尚未收齐时先生成稳定的 staging 布局和组件状态清单。
- `build-offline-bundle.ps1` 已支持直接消费现有 staging，输出 `offline-dist` 目录和 zip。
- `validate-offline-bundle.ps1` 默认允许 skeleton bundle 以告警形式通过；当前在 Python / MinGit / rg / ctags 已接入后，`-RequireComplete` 已可通过本轮 slice 的正式验收。

### 7.2 建议工作目录

```text
build/
├── offline-cache/      # 原始压缩包、wheel、二进制缓存
├── offline-staging/    # 解包后的中间目录
└── offline-dist/       # 最终 bundle 和 zip 产物
```

这些目录：

- 不作为运行时路径
- 默认不提交到 Git
- 仅服务构建过程

### 7.3 建议流水线

#### Step 1：准备第三方资产

输入：

- Python 3.8 embeddable distribution
- MinGit portable
- ripgrep
- Universal Ctags
- LLVM/Clang 工具链
- vendored Python wheel / site-packages

输出：

- `build/offline-cache/`
- 原始资产 checksum 记录

#### Step 2：组装 staging bundle

操作：

- 复制 `src/embedagent/` 到 `app/embedagent/`
- 复制 embeddable Python 到 `runtime/python/`
- 复制 vendored packages 到 `runtime/site-packages/`
- 复制外部工具到 `bin/*`
- 生成 launcher、默认配置模板和文档

输出：

- `build/offline-staging/EmbedAgent/`

#### Step 3：生成 manifest 与 license 材料

至少包含：

- 每个组件的版本
- 原始来源 URL 或内部来源说明
- 目标路径
- SHA256
- License 文件或 License 归属说明

输出：

- `manifests/bundle-manifest.json`
- `manifests/checksums.txt`
- `manifests/licenses/`

#### Step 4：做 bundle 级验证

建议验证内容：

- Python import
- CLI 启动
- 工具版本检查
- PATH 不依赖系统
- 配置模板存在
- bundle 内文件完整性

#### Step 5：生成发布产物

建议产物：

- `build/offline-dist/embedagent-win7-x64/`
- `build/offline-dist/embedagent-win7-x64.zip`

---

## 8. bundle 级验证口径

### 8.1 构建机静态检查

必须验证：

- manifest 中列出的文件都存在
- checksum 可重算
- `python.exe`、`git.exe`、`rg.exe`、`ctags.exe`、`clang.exe` 都存在
- `prompt_toolkit` / `rich` 及其传递依赖可导入

### 8.2 构建机动态检查

建议至少覆盖：

- `embedagent.cmd --help`
- `embedagent.cmd --list-sessions --workspace <temp>`
- `bin\git\...\git.exe --version`
- `bin\rg\rg.exe --version`
- `bin\ctags\ctags.exe --version`
- `bin\llvm\bin\clang.exe --version`

### 8.3 目标机验收检查

必须在全新 Windows 7 x64 虚拟机上验证：

- 不依赖预装开发工具
- 解压后可直接启动 CLI
- TUI 至少能进入和退出
- 工具链版本可见
- 配置与工作区目录可写

目标机检查细则见 `docs/win7-preflight-checklist.md`。

---

## 9. 当前开放问题

1. `toolchains/llvm/current` 仍是混合版本组合，Phase 7 打包前需要决定是否继续沿用。
2. Python 3.8 embeddable distribution 的 CRT / UCRT 本地部署策略需要明确。
3. 当前 site-packages 直接复制自 `.venv\Lib\site-packages`，后续需要决定是否导出为更精简的运行时集合。
4. 当前还没有真实 C 工程默认 recipe，因此 bundle 级验证暂时仍以工具存在性和最小运行检查为主。
5. TUI 在 Win7 / ConEmu / 原生 console 的宿主兼容性仍需与 Phase 6 收口联动处理。

---

## 10. 当前结论

Phase 7 现在的正确起点不是“直接写打包脚本”，而是先固定：

- 交付物主形态：one-folder portable bundle
- 目录布局：runtime / app / bin / manifests / config
- 组件清单：Python + vendored packages + MinGit + rg + ctags + LLVM/Clang
- 构建方法：manifest 驱动 staging 组装
- 验收口径：构建机静态/动态检查 + Win7 目标机 preflight

在这套基线下，后续脚本实现就不会再偏离“零外部依赖、解压即用、目标机无需预装软件”的主约束。
