"""
EmbedAgent Protocol - 前后端通信协议
定义 Agent Core 与 Frontend 之间的接口
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Protocol


class MessageType(Enum):
    """消息类型枚举"""
    USER = auto()           # 用户输入
    ASSISTANT = auto()      # AI 回复
    TOOL_START = auto()     # 工具开始
    TOOL_FINISH = auto()    # 工具完成
    TOOL_PROGRESS = auto()  # 工具进度
    SYSTEM = auto()         # 系统消息
    ERROR = auto()          # 错误消息
    CONTEXT_COMPACTED = auto()  # 上下文压缩


class SessionStatus(Enum):
    """会话状态枚举"""
    IDLE = "idle"
    RUNNING = "running"
    WAITING_PERMISSION = "waiting_permission"
    WAITING_INPUT = "waiting_user_input"
    ERROR = "error"


@dataclass
class Message:
    """结构化消息"""
    id: str
    type: MessageType
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    collapsed: bool = False
    group_id: Optional[str] = None


@dataclass
class ToolCall:
    """工具调用信息"""
    tool_name: str
    arguments: Dict[str, Any]
    call_id: str
    turn_id: str = ""
    step_id: str = ""
    step_index: int = 0
    runtime_source: str = ""
    resolved_tool_roots: Dict[str, Any] = field(default_factory=dict)
    

@dataclass
class ToolResult:
    """工具执行结果"""
    tool_name: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: int = 0
    call_id: str = ""
    turn_id: str = ""
    step_id: str = ""
    step_index: int = 0
    runtime_source: str = ""
    resolved_tool_roots: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PermissionRequest:
    """权限请求"""
    permission_id: str
    tool_name: str
    category: str
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    turn_id: str = ""
    step_id: str = ""
    step_index: int = 0


@dataclass
class UserInputRequest:
    """用户输入请求"""
    request_id: str
    tool_name: str
    question: str
    options: List[Dict[str, Any]] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    turn_id: str = ""
    step_id: str = ""
    step_index: int = 0


@dataclass
class CommandResult:
    """Slash command / workflow result"""
    command_name: str
    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    turn_id: str = ""
    step_id: str = ""
    step_index: int = 0


@dataclass
class PlanSnapshot:
    """当前会话的计划快照"""
    session_id: str
    title: str
    content: str
    updated_at: str
    workflow_state: str = "plan"
    path: str = ""
    summary: str = ""


@dataclass
class TimelineItem:
    """前端可消费的统一时间线条目"""
    id: str
    kind: str
    content: str = ""
    status: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentStepRecord:
    """单个用户 turn 下的一次 agent 迭代"""
    step_id: str
    step_index: int = 0
    reasoning: str = ""
    assistant_text: str = ""
    status: str = "in_progress"
    projection_kind: str = "recorded_step"
    synthetic: bool = False
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    transitions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TurnRecord:
    """结构化 turn 记录"""
    turn_id: str
    user_text: str
    reasoning: str = ""
    assistant_text: str = ""
    status: str = "completed"
    projection_kind: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    steps: List[AgentStepRecord] = field(default_factory=list)
    transitions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RuntimeEnvironmentSnapshot:
    """托管运行环境摘要"""
    runtime_source: str = ""
    bundled_tools_ready: bool = False
    fallback_warnings: List[str] = field(default_factory=list)
    resolved_tool_roots: Dict[str, Any] = field(default_factory=dict)
    tool_sources: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PermissionContextView:
    """前端展示权限上下文所需的数据"""
    session_id: str
    rules_path: str
    categories: List[str] = field(default_factory=list)
    rules: List[Dict[str, Any]] = field(default_factory=list)
    remembered_categories: List[str] = field(default_factory=list)
    auto_approve_all: bool = False
    auto_approve_writes: bool = False
    auto_approve_commands: bool = False


@dataclass
class DiffPreview:
    """Diff 预览"""
    path: str
    old_content: str
    new_content: str
    unified_diff: str
    file_type: str = "text"


@dataclass
class SessionSnapshot:
    """会话快照"""
    session_id: str
    status: SessionStatus
    current_mode: str
    created_at: str
    updated_at: str
    workflow_state: str = "chat"
    has_active_plan: bool = False
    active_plan_ref: str = ""
    current_command_context: str = ""
    has_pending_permission: bool = False
    has_pending_input: bool = False
    pending_permission: Optional[PermissionRequest] = None
    pending_input: Optional[UserInputRequest] = None
    last_error: Optional[str] = None
    runtime_source: str = ""
    bundled_tools_ready: bool = False
    fallback_warnings: List[str] = field(default_factory=list)
    runtime_environment: Optional[RuntimeEnvironmentSnapshot] = None
    compact_summary_text: str = ""
    context_analysis: Dict[str, Any] = field(default_factory=dict)
    compact_boundary_count: int = 0
    workspace_intelligence: List[Dict[str, Any]] = field(default_factory=list)
    context_pipeline_steps: List[str] = field(default_factory=list)
    last_transition_reason: str = ""
    last_transition_message: str = ""
    last_transition_display_reason: str = ""
    recent_transition_reasons: List[str] = field(default_factory=list)
    recent_transitions: List[Dict[str, Any]] = field(default_factory=list)
    compact_retry_count: int = 0
    restore_stop_reason: str = ""
    restore_consumed_event_count: int = 0
    restore_transcript_event_count: int = 0
    pending_interaction: Optional[Dict[str, Any]] = None
    timeline_replay_status: str = "replay"
    timeline_first_seq: int = 0
    timeline_last_seq: int = 0
    timeline_integrity: str = "healthy"
    pending_interaction_valid: bool = False


@dataclass  
class WorkspaceInfo:
    """工作区信息"""
    path: str
    git_branch: str = ""
    git_dirty: int = 0
    file_count: int = 0
    dir_count: int = 0


# ============ 回调接口 ============

class FrontendCallbacks(Protocol):
    """前端回调协议 - Core 调用 Frontend"""
    
    def on_message(self, message: Message) -> None:
        """新消息到达"""
        ...
    
    def on_tool_start(self, call: ToolCall) -> None:
        """工具开始执行"""
        ...
    
    def on_tool_progress(self, call_id: str, progress: Dict[str, Any]) -> None:
        """工具进度更新"""
        ...
    
    def on_tool_finish(self, result: ToolResult) -> None:
        """工具执行完成"""
        ...
    
    def on_permission_request(self, request: PermissionRequest) -> bool:
        """请求用户权限，返回是否批准"""
        ...
    
    def on_user_input_request(self, request: UserInputRequest) -> Optional[str]:
        """请求用户输入，返回答案"""
        ...
    
    def on_session_status_change(self, snapshot: SessionSnapshot) -> None:
        """会话状态变化"""
        ...
    
    def on_stream_delta(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """流式输出增量"""
        ...

    def on_reasoning_delta(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """thinking / reasoning 流式增量"""
        ...

    def on_thinking_state_change(self, active: bool, reason: str = "") -> None:
        """模型是否处于 thinking 阶段"""
        ...

    def on_command_result(self, result: CommandResult) -> None:
        """slash command / workflow 结果"""
        ...

    def on_plan_updated(self, plan: PlanSnapshot) -> None:
        """计划更新"""
        ...

    def on_todos_refresh(self) -> None:
        """Notify frontend to refetch todos list."""
        ...

    def on_artifacts_refresh(self) -> None:
        """Notify frontend to refetch artifacts list."""
        ...


class CoreInterface(ABC):
    """Core 接口抽象 - Frontend 调用 Core"""
    
    @abstractmethod
    def create_session(self, mode: str) -> SessionSnapshot:
        """创建新会话"""
        pass
    
    @abstractmethod
    def resume_session(self, reference: str, mode: str) -> SessionSnapshot:
        """恢复会话"""
        pass
    
    @abstractmethod
    def list_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """列出会话"""
        pass

    @abstractmethod
    def get_session_snapshot(self, session_id: str) -> SessionSnapshot:
        """获取会话快照"""
        pass
    
    @abstractmethod
    def submit_message(self, session_id: str, text: str) -> None:
        """提交用户消息（异步）"""
        pass
    
    @abstractmethod
    def cancel_session(self, session_id: str) -> None:
        """取消会话"""
        pass
    
    @abstractmethod
    def set_mode(self, session_id: str, mode: str) -> None:
        """设置会话模式"""
        pass
    
    @abstractmethod
    def approve_permission(self, session_id: str, permission_id: str) -> None:
        """批准权限请求"""
        pass
    
    @abstractmethod
    def reject_permission(self, session_id: str, permission_id: str) -> None:
        """拒绝权限请求"""
        pass
    
    @abstractmethod
    def reply_user_input(self, session_id: str, request_id: str, 
                        answer: str, **kwargs) -> None:
        """回复用户输入请求"""
        pass
    
    @abstractmethod
    def get_workspace_snapshot(self) -> WorkspaceInfo:
        """获取工作区快照"""
        pass

    @abstractmethod
    def list_workspace_recipes(self) -> Dict[str, Any]:
        """列出工作区 recipe"""
        pass
    
    @abstractmethod
    def list_files(self, path: str = ".", max_depth: int = 3) -> List[Dict[str, Any]]:
        """列出文件"""
        pass

    @abstractmethod
    def list_file_children(self, path: str = ".", limit: int = 200) -> List[Dict[str, Any]]:
        """列出目录的直接子项"""
        pass
    
    @abstractmethod
    def read_file(self, path: str) -> Dict[str, Any]:
        """读取文件"""
        pass
    
    @abstractmethod
    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """写入文件"""
        pass

    @abstractmethod
    def get_session_timeline(self, session_id: str, limit: int = 200) -> Dict[str, Any]:
        """获取会话时间线"""
        pass

    @abstractmethod
    def build_structured_timeline(self, session_id: str, limit: int = 200) -> Dict[str, Any]:
        """获取结构化 turn/step 时间线"""
        pass

    @abstractmethod
    def list_artifacts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """列出工件"""
        pass

    @abstractmethod
    def read_artifact(self, reference: str) -> Dict[str, Any]:
        """读取工件"""
        pass
    
    @abstractmethod
    def get_diff_preview(self, path: str, new_content: str) -> DiffPreview:
        """获取 diff 预览"""
        pass
    
    @abstractmethod
    def list_todos(self, session_id: str = "") -> List[Dict[str, Any]]:
        """列出待办事项"""
        pass

    @abstractmethod
    def get_session_plan(self, session_id: str) -> Optional[PlanSnapshot]:
        """获取会话计划"""
        pass

    @abstractmethod
    def get_permission_context(self, session_id: str) -> PermissionContextView:
        """获取当前会话的权限上下文"""
        pass

    @abstractmethod
    def get_tool_catalog(self) -> List[Dict[str, Any]]:
        """获取当前工具目录"""
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """关闭 Core"""
        pass
