# EmbedAgent 内网环境部署指南

> 适用场景：物理隔离内网，无互联网访问，但可访问内网大模型服务
> 更新日期：2026-03-30

---

## 1. 部署概览

EmbedAgent 打包后的 bundle 是**完全自包含**的，目标机上：

- ✅ 无需安装 Python
- ✅ 无需安装 Git
- ✅ 无需安装 LLVM/Clang
- ✅ 无需联网下载任何依赖
- ✅ 只需配置内网大模型服务地址即可使用

---

## 2. Bundle 内容物

```
EmbedAgent/
├── embedagent.cmd              # CLI 入口
├── embedagent-tui.cmd          # TUI 入口
├── embedagent-gui.cmd          # GUI 入口
├── manifests/                  # 组件清单与许可证
│   ├── bundle-manifest.json
│   ├── checksums.txt
│   └── licenses/
├── runtime/                    # Python 运行时
│   ├── python/                 # Python 3.8 embeddable
│   └── site-packages/          # 所有 Python 依赖（含传递依赖）
├── app/                        # EmbedAgent 应用代码
│   └── embedagent/
├── bin/                        # 外部工具
│   ├── git/                    # MinGit
│   ├── rg/                     # ripgrep
│   ├── ctags/                  # Universal Ctags
│   └── llvm/                   # LLVM/Clang 工具链
├── config/                     # 配置文件模板
│   ├── config.json
│   └── permission-rules.json
└── docs/                       # 文档
```

---

## 3. 内网部署步骤

### 3.1 传输 Bundle 到内网

```bash
# 在外网准备 bundle
powershell -File scripts\build-offline-bundle.ps1

# 将生成的 zip 传输到内网
# build/offline-dist/embedagent-win7-x64-<timestamp>.zip
```

### 3.2 内网机器部署

```powershell
# 1. 解压 bundle
Expand-Archive -Path embedagent-win7-x64.zip -DestinationPath C:\Tools

# 2. 验证 bundle 完整性
powershell -File C:\Tools\EmbedAgent\scripts\validate-offline-bundle.ps1 -RequireComplete

# 3. 配置内网大模型服务
copy C:\Tools\EmbedAgent\config\config.json C:\Users\<username>\.embedagent\
# 编辑 config.json，填入内网模型服务地址
```

### 3.3 配置内网大模型服务

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

**配置项说明**：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `base_url` | 内网大模型服务地址 | `http://192.168.1.100:8000/v1` |
| `api_key` | 内网服务 API Key | `sk-internal` |
| `model` | 模型名称 | `qwen3.5-coder`, `glm5-int4` |
| `timeout` | 请求超时（秒） | `120` |

### 3.4 验证安装

```powershell
# 验证 CLI
cd C:\Tools\EmbedAgent
.\embedagent.cmd --help

# 验证工具链
.\embedagent.cmd --version

# 启动 TUI（如果已安装依赖）
.\embedagent-tui.cmd --workspace D:\Projects\MyProject --model qwen3.5-coder

# 启动 GUI（如果已安装依赖）
.\embedagent-gui.cmd --workspace D:\Projects\MyProject --model qwen3.5-coder
```

---

## 4. 零依赖验证清单

部署后请确认：

- [ ] 目标机无 Python 安装或 Python 未添加到 PATH
- [ ] 目标机无 Git 安装
- [ ] 目标机无 LLVM/Clang 安装
- [ ] Bundle 可独立运行，不依赖外部网络
- [ ] 内网大模型服务可正常访问

---

## 5. 常见问题

### Q1: 启动时报缺少 DLL

**原因**：Windows 7 可能缺少 Visual C++ Runtime

**解决**：安装 Visual C++ Redistributable（可随 bundle 分发）

### Q2: GUI 启动失败

**原因**：Windows 7 缺少 WebView2 Runtime

**解决**：
- 方案 A：在内网机器上安装 WebView2 Runtime（Evergreen Standalone Installer）
- 方案 B：使用 TUI 模式（无需 WebView2）

### Q3: 内网模型服务连接失败

**排查步骤**：
1. 确认内网服务地址可 ping 通
2. 确认端口开放：`telnet 192.168.1.100 8000`
3. 确认 API Key 正确
4. 检查 config.json 格式是否正确

### Q4: 如何更新模型配置

编辑 `%USERPROFILE%\.embedagent\config.json`：

```json
{
  "base_url": "http://new-internal-server:8000/v1",
  "api_key": "new-key",
  "model": "new-model-name"
}
```

---

## 6. 内网安全注意事项

1. **API Key 管理**：内网 config.json 中的 API Key 应妥善保管
2. **权限控制**：建议在内网模型服务端配置 IP 白名单
3. **审计日志**：EmbedAgent 的会话摘要在 `.embedagent/memory/sessions/` 中，可用于审计

---

## 7. 打包构建说明（供维护人员）

```powershell
# 1. 导出所有依赖
python scripts\export-dependencies.py --output-dir build\offline-cache\site-packages-export

# 2. 准备离线 bundle
powershell -File scripts\prepare-offline.ps1 `
    -AssetIds python_embedded_x64,mingit_x64,ripgrep_x64,universal_ctags_x64 `
    -SitePackagesRoot build\offline-cache\site-packages-export\site-packages `
    -AllowDownload

# 3. 构建最终 zip
powershell -File scripts\build-offline-bundle.ps1

# 4. 验证 bundle
powershell -File scripts\validate-offline-bundle.ps1 -RequireComplete
```

---

## 8. 依赖完整性清单

Bundle 包含以下所有依赖（无需联网）：

### Python 运行时
- Python 3.8.10 embeddable x64
- 完整 site-packages（含传递依赖）

### Python 包（部分列表）
- prompt-toolkit 3.0.52
- rich 14.3.3
- pywebview >=4.0
- fastapi >=0.100
- uvicorn[standard] >=0.23
- websockets >=11.0
- pydantic >=2.0
- starlette >=0.27
- 及所有传递依赖...

### 外部工具
- MinGit 2.46.2
- ripgrep 14.1.1
- Universal Ctags p6.2.20251116.0
- LLVM/Clang（项目内 toolchains/llvm/current）

---

**确保零外部依赖，开箱即用！**
