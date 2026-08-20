"""
EmbedAgent Protocol - 前后端通信协议
定义 Agent Core 与 Frontend 之间的接口
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from embedagent_protocol.app_protocol import (
    AgentApplicationDescriptor as AgentApplicationDescriptor,
)
from embedagent_protocol.app_protocol import (
    AppBootstrap as AppBootstrap,
)
from embedagent_protocol.app_protocol import (
    CapabilitySnapshot as CapabilitySnapshot,
)
from embedagent_protocol.app_protocol import (
    CommandDescriptor as CommandDescriptor,
)
from embedagent_protocol.app_protocol import (
    InteractionActivity as InteractionActivity,
)
from embedagent_protocol.app_protocol import (
    InteractionDescriptor as InteractionDescriptor,
)
from embedagent_protocol.app_protocol import (
    KeybindingDescriptor as KeybindingDescriptor,
)
from embedagent_protocol.app_protocol import (
    ModeDescriptor as ModeDescriptor,
)
from embedagent_protocol.app_protocol import (
    SessionBootstrap as SessionBootstrap,
)
from embedagent_protocol.app_protocol import (
    ShellDescriptor as ShellDescriptor,
)
from embedagent_protocol.app_protocol import (
    SurfaceDescriptor as SurfaceDescriptor,
)
from embedagent_protocol.app_protocol import (
    ThreadShell as ThreadShell,
)
from embedagent_protocol.app_protocol import (
    TimelineItemDescriptor as TimelineItemDescriptor,
)
from embedagent_protocol.app_protocol import (
    ToolPresentation as ToolPresentation,
)
from embedagent_protocol.app_protocol import (
    WorkflowPackageDescriptor as WorkflowPackageDescriptor,
)
from embedagent_protocol.frontend_ports import (
    FrontendSessionPort as FrontendSessionPort,
)
from embedagent_protocol.frontend_ports import (
    FrontendWorkspacePort as FrontendWorkspacePort,
)
from embedagent_protocol.frontend_ports import SessionEventSink as SessionEventSink
from embedagent_protocol.frontend_interactions import (
    InteractionProjection as InteractionProjection,
)
from embedagent_protocol.frontend_notifications import (
    WorkspaceChangedNotification as WorkspaceChangedNotification,
)
from embedagent_protocol.session_events import FRONTEND_FAILURE_CODES as FRONTEND_FAILURE_CODES
from embedagent_protocol.session_events import FailureRecord as FailureRecord
from embedagent_protocol.session_events import (
    SessionEventEnvelope as SessionEventEnvelope,
)


@dataclass
class PermissionContext:
    """JSON-safe permission context exposed across the host protocol boundary."""

    session_id: str
    rules_path: str
    categories: List[str] = field(default_factory=list)
    rules: List[Dict[str, Any]] = field(default_factory=list)
    remembered_categories: List[str] = field(default_factory=list)
    auto_approve_all: bool = False
    auto_approve_writes: bool = False
    auto_approve_commands: bool = False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MessageType(Enum):
    """消息类型枚举"""

    USER = auto()  # 用户输入
    ASSISTANT = auto()  # AI 回复
    TOOL_START = auto()  # 工具开始
    TOOL_FINISH = auto()  # 工具完成
    TOOL_PROGRESS = auto()  # 工具进度
    SYSTEM = auto()  # 系统消息
    ERROR = auto()  # 错误消息
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
    timestamp: datetime = field(default_factory=_utc_now)
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
    workflow_state: Dict[str, Any] = field(default_factory=dict)
    has_active_plan: bool = False
    active_plan_ref: str = ""
    current_command_context: str = ""
    last_failure: Optional[Dict[str, Any]] = None
    runtime_source: str = ""
    bundled_tools_ready: bool = False
    fallback_warnings: List[str] = field(default_factory=list)
    runtime_environment: Optional[RuntimeEnvironmentSnapshot] = None
    compact_summary_text: str = ""
    context_analysis: Dict[str, Any] = field(default_factory=dict)
    context_usage: Dict[str, Any] = field(default_factory=dict)
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
    compaction_state: Dict[str, Any] = field(default_factory=dict)
    recovery_state: Dict[str, Any] = field(default_factory=dict)
    turn_experience: Dict[str, Any] = field(default_factory=dict)
    pending_interaction: Optional[Dict[str, Any]] = None
    pending_interaction_valid: bool = False


@dataclass
class WorkspaceInfo:
    """工作区信息"""

    path: str
    git_branch: str = ""
    git_dirty: int = 0
    file_count: int = 0
    dir_count: int = 0
