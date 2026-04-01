# EmbedAgent 内网环境部署指南

> 适用场景：物理隔离内网，无互联网访问，但可访问内网大模型服务
> 更新日期：2026-04-02

---

## 1. 部署概览

EmbedAgent 的离线交付物目标仍然是：

- 无需安装 Python
- 无需安装 Git
- 无需安装 LLVM/Clang
- 无需联网下载任何依赖
- 只需配置内网模型服务地址即可使用

但构建侧的公共操作入口已经收敛到：

```powershell
pwsh -File scripts/package.ps1 <command>
```

---

## 2. 维护人员如何构建内网交付包

### 2.1 推荐路径

```powershell
pwsh -File scripts/package.ps1 doctor
pwsh -File scripts/package.ps1 release
```

如果要把结果交给自动化消费：

```powershell
pwsh -File scripts/package.ps1 release -Json
```

### 2.2 构建结果判断

优先看：

- `build/offline-reports/latest.json`

其中最关键的字段是：

- `final_status`
- `blocking_issues`

只有 `final_status == "READY"` 时，才应把结果视为 release-ready 候选物。

---

## 3. 目标机部署步骤

### 3.1 传输 bundle 到内网

在构建机完成：

```powershell
pwsh -File scripts/package.ps1 release
```

然后把生成的 zip 传输到内网目标机。

### 3.2 内网机器部署

```powershell
# 1. 解压 bundle
Expand-Archive -Path embedagent-win7-x64.zip -DestinationPath C:\Tools

# 2. 按 bundle 自带文档执行预检
# docs\win7-preflight-checklist.md

# 3. 配置内网大模型服务
copy C:\Tools\EmbedAgent\config\config.json C:\Users\<username>\.embedagent\
```

### 3.3 配置内网模型服务

编辑 `%USERPROFILE%\.embedagent\config.json`：

```json
{
  "base_url": "http://192.168.1.100:8000/v1",
  "api_key": "your-internal-api-key",
  "model": "qwen3.5-coder",
  "timeout": 120,
  "default_mode": "code"
}
```

---

## 4. 目标机验证

### 4.1 启动验证

```powershell
cd C:\Tools\EmbedAgent
.\embedagent.cmd --help
.\embedagent-tui.cmd --workspace D:\Projects\MyProject --model qwen3.5-coder
.\embedagent-gui.cmd --workspace D:\Projects\MyProject --model qwen3.5-coder
```

### 4.2 Win7 / GUI 验证

按这些文档执行：

- [docs/win7-preflight-checklist.md](D:/Claude-project/ccode-win7/.worktrees/codex-package-control-plane-redesign/docs/win7-preflight-checklist.md)
- [docs/win7-gui-validation.md](D:/Claude-project/ccode-win7/.worktrees/codex-package-control-plane-redesign/docs/win7-gui-validation.md)

---

## 5. 常见问题

### Q1: 构建机上 `release` 失败

先运行：

```powershell
pwsh -File scripts/package.ps1 doctor -Json
```

再查看：

```text
build/offline-reports/latest.json
```

### Q2: 目标机启动时报缺少 DLL

通常是 Windows 7 CRT / UCRT 环境不完整，按 preflight 文档处理。

### Q3: GUI 启动失败

优先确认 bundle 中包含 Fixed Version WebView2 109，并按 `docs/win7-gui-validation.md` 复核。

### Q4: 无法连接内网模型服务

检查：

1. 地址是否可达
2. 端口是否开放
3. `config.json` 是否正确

---

## 6. 内部 Stage 说明

维护控制面时，底层仍然会复用：

- `scripts/export-dependencies.py`
- `scripts/prepare-offline.ps1`
- `scripts/build-offline-bundle.ps1`
- `scripts/validate-offline-bundle.ps1`
- `scripts/check-bundle-dependencies.py`

但面向维护人员的常规入口已经改成 `scripts/package.ps1`。
