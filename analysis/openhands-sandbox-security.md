# OpenHands 权限管理与运行沙箱分析

> 源文件：`reference/OpenHands/openhands/runtime/`、`openhands/security/`、`openhands/core/config/`
> 核心结论：OpenHands 的"沙箱"是一个频谱，Docker 端是真隔离，CLI 端几乎无隔离，安全性主要靠人工确认机制

---

## 一、整体安全架构

OpenHands 的安全体系由两个相互独立的层组成：

```
┌─────────────────────────────────────────────┐
│  层 1：Action 执行前确认（Controller 层）       │
│  SecurityAnalyzer → ActionSecurityRisk        │
│  confirmation_mode → AWAITING_CONFIRMATION    │
├─────────────────────────────────────────────┤
│  层 2：Runtime 执行隔离（Runtime 层）           │
│  Docker/Kubernetes = 真容器隔离               │
│  CLIRuntime = 仅路径限制，无真实隔离            │
└─────────────────────────────────────────────┘
```

这两层完全解耦：Runtime 不关心权限判断，Controller 不关心执行隔离。

---

## 二、权限管理层（Controller 侧）

### 2.1 配置入口

```python
# openhands/core/config/security_config.py
class SecurityConfig(BaseModel):
    confirmation_mode: bool = False   # 是否开启确认模式
    security_analyzer: str | None = None  # 分析器名称: 'invariant'|'llm'|'grayswan'|None
```

仅两个字段，极为简洁。`security_analyzer` 是分析器的注册名，通过注册表查找实现类：

```python
# openhands/security/options.py
SecurityAnalyzers: dict[str, type[SecurityAnalyzer]] = {
    'invariant': InvariantAnalyzer,   # 基于规则引擎
    'llm': LLMRiskAnalyzer,           # 信任 LLM 自报风险
    'grayswan': GraySwanAnalyzer,     # 第三方商业服务
}
```

### 2.2 风险等级枚举

```python
class ActionSecurityRisk(str, Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    UNKNOWN = 'unknown'
```

### 2.3 SecurityAnalyzer 抽象接口

```python
# openhands/security/analyzer.py
class SecurityAnalyzer(ABC):
    async def security_risk(self, action: Action) -> ActionSecurityRisk:
        # 子类实现：分析 action，返回风险等级
        raise NotImplementedError

    def set_event_stream(self, event_stream) -> None:
        # 可选：某些分析器需要访问历史事件（如 Invariant）
        pass

    async def close(self) -> None:
        # 清理资源
        pass
```

### 2.4 三种分析器实现对比

#### LLMRiskAnalyzer（最轻量）

```python
# openhands/security/llm/analyzer.py
async def security_risk(self, action: Action) -> ActionSecurityRisk:
    # 直接读取 action 上的 security_risk 字段
    # 该字段由 LLM 在工具调用时自己填写
    security_risk = getattr(action, 'security_risk', ActionSecurityRisk.UNKNOWN)
    if security_risk in {LOW, MEDIUM, HIGH}:
        return security_risk
    return ActionSecurityRisk.UNKNOWN
```

**本质**：完全信任 LLM 自我评估风险。LLM 生成工具调用时，在参数里带上 `security_risk` 字段，分析器原样读取。

**问题**：恶意或错误的 LLM 可以自报 LOW 绕过确认。

#### InvariantAnalyzer（最重量）

- 启动一个 Docker 容器运行 `invariantlabs-ai/server` 镜像（外部策略引擎）
- 将 conversation history 转换为 trace 格式发送给该容器
- 由规则引擎判断是否违反策略（如"不能读取 /etc/passwd"）
- 返回 HIGH/LOW

**依赖**：Docker 必须运行。不适合离线/嵌入式环境。

#### GraySwanAnalyzer

- 第三方商业 API，调用远程服务判断风险
- 同样不适合离网环境

### 2.5 Controller 中的确认流程

```python
# agent_controller.py _step()
if action.runnable and self.state.confirmation_mode:
    if action_type in (CmdRunAction, FileEditAction, FileReadAction, ...):
        await self._handle_security_analyzer(action)

        security_risk = getattr(action, 'security_risk', UNKNOWN)
        is_high_risk = (security_risk == HIGH)
        is_ask_for_every = (security_risk == UNKNOWN and not self.security_analyzer)

        if is_high_risk or is_ask_for_every:
            action.confirmation_state = AWAITING_CONFIRMATION
```

**关键逻辑**：
- 有安全分析器 → 只有 HIGH 风险才需确认
- 无安全分析器（默认）→ UNKNOWN 风险也需确认 → **实际上每个 action 都需确认**（fail-safe）
- `cli_mode=True` → 跳过 Controller 确认逻辑，由 TUI 层自己处理

**状态流转**：

```
action.confirmation_state = AWAITING_CONFIRMATION
→ Controller: set_agent_state_to(AWAITING_USER_CONFIRMATION)
→ 等待用户操作
    ├─ 确认 → set_agent_state_to(USER_CONFIRMED)
    │          → action 重新发布到 EventStream → Runtime 执行
    └─ 拒绝 → set_agent_state_to(USER_REJECTED)
               → set_agent_state_to(AWAITING_USER_INPUT)
               → Agent 等待新指令
```

---

## 三、运行沙箱层（Runtime 侧）

### 3.1 Runtime 实现频谱

OpenHands 内置 5 种 Runtime，隔离程度差异极大：

| Runtime | 隔离机制 | 适用场景 | Windows 可用 |
|---------|---------|---------|-------------|
| `DockerRuntime` | Docker 容器完整隔离 | 生产环境 | 需要 Docker |
| `KubernetesRuntime` | K8s Pod 隔离 | 云原生部署 | 需要 K8s |
| `RemoteRuntime` | 远程服务器执行 | 分布式 | 网络访问 |
| `LocalRuntime` | 本地进程，仅路径限制 | 开发调试 | ✅（有限制） |
| `CLIRuntime` | 本地进程，仅路径限制 | CLI/TUI 场景 | ✅（PowerShell） |

**代码中的明确警告**（CLIRuntime）：
```python
logger.warning(
    'Initializing CLIRuntime. WARNING: NO SANDBOX IS USED. '
    'This runtime executes commands directly on the local system. '
    'Use with caution in untrusted environments.'
)
```

### 3.2 CLIRuntime 的实际隔离机制

CLIRuntime 是与我们项目最接近的实现，其"沙箱"实质上只有两件事：

#### 机制 1：Workspace 路径限制（_sanitize_filename）

```python
def _sanitize_filename(self, filename: str) -> str:
    # 路径映射：/workspace/ → 实际 workspace 目录
    if filename.startswith('/workspace/'):
        actual = os.path.join(self._workspace_path, filename[len('/workspace/'):])
    elif filename.startswith('/'):
        if not filename.startswith(self._workspace_path):
            raise PermissionError(f'Invalid path: {filename}.')
        actual = filename
    else:
        actual = os.path.join(self._workspace_path, filename.lstrip('/'))

    # 解析符号链接和 .. 等，防路径穿越
    resolved = os.path.realpath(actual)

    # 最终检查：必须在 workspace 内
    if not resolved.startswith(self._workspace_path):
        raise PermissionError(
            f'Invalid path traversal: {filename}. '
            f'Resolved: {resolved}, Workspace: {self._workspace_path}'
        )
    return resolved
```

**保护范围**：文件读/写/编辑操作。
**不保护的**：Shell 命令（`run()` 方法）——bash 命令可以访问系统任意路径。

#### 机制 2：命令超时控制

```python
# 默认超时：sandbox_config.timeout = 120 秒
effective_timeout = action.timeout or self.config.sandbox.timeout

# 超时后的处理（Unix）
os.killpg(pgid, signal.SIGTERM)  # 先发 SIGTERM 给进程组
# 若还未退出 → SIGKILL
```

超时用 `select()` + 单调时钟实现，不依赖信号：
```python
while process.poll() is None:
    if (time.monotonic() - start_time) > timeout:
        self._safe_terminate_process(process, SIGTERM)
        timed_out = True
        break
    ready, _, _ = select.select([process.stdout], [], [], 0.1)
    if ready:
        output_lines.append(process.stdout.readline())
```

超时的 `exit_code = -1`，作为识别标志返回给 Agent。

**进程组终止**（`start_new_session=True`）：
```python
process = subprocess.Popen(
    ['bash', '-c', command],
    start_new_session=True,  # 新进程组 → killpg 可以杀死所有子进程
    ...
)
```

#### 机制 3：二进制文件保护

```python
from binaryornot.check import is_binary

if is_binary(file_path):
    return ErrorObservation('ERROR_BINARY_FILE')
```

防止 Agent 意外读取或破坏可执行文件、库等。

#### 机制 4：PermissionError 捕获

```python
# base.py _handle_action()
try:
    observation = await call_sync_from_async(self.run_action, event)
except PermissionError as e:
    observation = ErrorObservation(content=str(e))  # 转换为 ErrorObservation
```

文件操作的 `PermissionError`（包括路径穿越）不会 crash，而是以 ErrorObservation 形式反馈给 Agent，让 Agent 自行调整。

### 3.3 Windows 支持（PowerShell Session）

CLIRuntime 在 Windows 上用 `WindowsPowershellSession` 替代 `bash -c`：

```python
if self._is_windows and self._powershell_session is not None:
    return self._execute_powershell_command(action.command, timeout)
else:
    return self._execute_shell_command(action.command, timeout)
```

`WindowsPowershellSession` 维护一个持久的 PowerShell 进程，通过管道通信：
- `no_change_timeout_seconds=30`：30 秒无输出视为命令完成（启发式判断）
- `max_memory_mb=None`：无内存限制
- 依赖 .NET SDK（Windows 7 兼容性存疑）

### 3.4 环境变量注入

```python
def add_env_vars(self, env_vars: dict[str, str]) -> None:
    # CLIRuntime 直接修改当前进程的 os.environ
    for key, value in env_vars.items():
        if isinstance(value, SecretStr):
            os.environ[key] = value.get_secret_value()
        else:
            os.environ[key] = value
    # 不写入 .bashrc（与 Base Runtime 的 Unix 实现不同）
```

日志只记录 key 不记录 value，避免 token 等敏感信息泄露。

### 3.5 可信目录配置（trusted_dirs）

```python
# sandbox_config.py
trusted_dirs: list[str] = Field(default_factory=list)
# 允许在这些目录下启动 OpenHands CLI
```

防止 Agent 在任意目录启动时篡改系统文件（配合 workspace 路径限制）。

---

## 四、Docker Runtime 的真实沙箱（参考）

Docker Runtime 才是真正的沙箱，关键机制（不适合我们，但值得了解）：

1. **容器隔离**：每个 session 一个独立容器，用户无法访问宿主机
2. **用户 ID 映射**：`SandboxConfig.user_id`，容器内以指定 UID 运行（避免 root）
3. **网络隔离**：可选 `use_host_network=False`，容器无网络访问
4. **卷挂载限制**：只将 workspace 目录挂载进容器，宿主机其他路径不可见
5. **资源限制**：`remote_runtime_resource_factor`，可限制 CPU/内存
6. **gVisor/sysbox**：`remote_runtime_class='gvisor'` 可用内核级沙箱（比 Docker 更强）

---

## 五、完整流程图

```
Agent 生成 Action (含 security_risk 字段)
    │
    ▼
Controller._step()
    ├─ action.runnable=True?
    │   └─ confirmation_mode=True?
    │       └─ SecurityAnalyzer.security_risk(action)
    │           ├─ LLMRiskAnalyzer: 读 action.security_risk 字段
    │           ├─ InvariantAnalyzer: 发给 Docker 容器判断
    │           └─ 无分析器: 返回 UNKNOWN
    │
    ├─ HIGH 或 UNKNOWN(无分析器) → AWAITING_USER_CONFIRMATION
    │   └─ 等待用户确认/拒绝
    │
    └─ 确认 → EventStream.add_event(action)
                │
                ▼
            Runtime.on_event(action)
                │
                ▼
            _handle_action(action)
                ├─ 设置 timeout（默认 120s）
                │
                ├─ CmdRunAction → run(action)
                │   ├─ [Unix] subprocess.Popen(['bash','-c',...], start_new_session=True)
                │   │   + select() 轮询输出 + 超时 killpg
                │   └─ [Win]  PowerShellSession.execute(action)
                │
                ├─ FileReadAction → read(action)
                │   ├─ _sanitize_filename() ← 路径穿越检查
                │   ├─ is_binary() 检查
                │   └─ open() 读取
                │
                ├─ FileEditAction → write(action) / edit(action)
                │   └─ _sanitize_filename() ← 路径穿越检查
                │
                └─ PermissionError → ErrorObservation（不 crash）
                │
                ▼
            EventStream.add_event(observation)
```

---

## 六、对我们项目的具体建议

### 沙箱设计决策

**结论：我们的项目不需要、也无法实现真正的沙箱（Windows 7 + 无 Docker），应当像 CLIRuntime 一样明确承认这一点，并依靠以下三层软隔离。**

#### 第一层：Workspace 路径限制

这是 CLIRuntime 最重要的保护，必须实现：

```python
def sanitize_path(path: str, workspace: str) -> str:
    # 解析绝对路径
    if not os.path.isabs(path):
        path = os.path.join(workspace, path)
    resolved = os.path.realpath(path)
    if not resolved.startswith(os.path.realpath(workspace)):
        raise PermissionError(f'路径越界: {path}')
    return resolved
```

嵌入式 C 项目的工作目录是固定的（项目根目录），Agent 应只能操作该目录内的文件。

#### 第二层：命令超时

编译、链接等长时操作必须有超时保护。Windows 7 下用 `subprocess.Popen` + 时间检查：

```python
process = subprocess.Popen(command, shell=True,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
try:
    stdout, _ = process.communicate(timeout=120)
except subprocess.TimeoutExpired:
    process.kill()
    stdout, _ = process.communicate()
    return CmdOutput(content=stdout.decode(), exit_code=-1, timed_out=True)
```

Windows 7 没有 `os.killpg`，直接 `process.kill()` 即可（`shell=True` 下可能残留子进程，需注意）。

#### 第三层：人工确认模式（最重要的保护）

对于**危险操作**，在 TUI 中弹出确认提示：

危险操作分类（参考 OpenHands 的 `action.runnable` 逻辑）：

| 操作 | 建议策略 |
|------|---------|
| 普通 bash 命令（gcc, make）| 自动执行，显示输出 |
| 文件写/编辑 | 显示 diff，可选确认 |
| `git reset --hard` / `git clean` | 强制确认 |
| `rm -rf` 或批量删除 | 强制确认 |
| 超出 workspace 的路径操作 | 直接拒绝（PermissionError） |

无需实现 SecurityAnalyzer 机制，直接在 TUI 层的 `execute_action()` 中用简单的命令关键字匹配即可：

```python
DANGEROUS_PATTERNS = ['rm -rf', 'git reset --hard', 'git clean -f', 'mkfs', 'dd if=']

def is_dangerous(command: str) -> bool:
    return any(p in command for p in DANGEROUS_PATTERNS)
```

### 不需要实现的

- SecurityAnalyzer 三种实现（Invariant/GraySwanAnalyzer）：依赖 Docker/网络，不适用
- `action.security_risk` 字段机制：过于复杂，简单关键字匹配即可
- Binary file 检测（`binaryornot`）：嵌入式项目有 `.bin`/`.elf`/`.hex` 等，Agent 不应读取它们，但用文件扩展名判断更直接
- Windows PowerShell Session（复杂，依赖 .NET）：Windows 7 下直接用 `subprocess` + `cmd.exe` 或 `bash.exe`（如果装了 Git Bash）

### Windows 7 特殊注意

- `subprocess.TimeoutExpired` 在 Python 3.3+ 可用（Windows 7 支持 Python 3.8），✅
- `process.kill()` 在 Windows 会终止进程但不会终止子进程树，需要用 `taskkill /F /T /PID` 来递归终止：

```python
import subprocess
subprocess.call(['taskkill', '/F', '/T', '/PID', str(process.pid)])
```

- `os.path.realpath()` 在 Windows 7 下能正确处理符号链接和 `..`，✅
- 路径分隔符：用 `os.path.normpath()` 统一处理 `\` 和 `/` 的混用
