from __future__ import annotations

import re
from typing import Any, List, Optional, Set

from embedagent.extensions import HarnessPrompt
from embedagent.harness import task_store
from embedagent.harness.runner import HarnessRunner
from embedagent.harness.task_graph import TaskGraph
from embedagent.session import Observation
from embedagent.tooling.packs import pack_tool_names


class CHarnessWorkflowExtension(object):
    def __init__(self, tools: Any = None, harness_runner: Optional[HarnessRunner] = None) -> None:
        self.tools = tools
        self.harness_runner = harness_runner or HarnessRunner()

    def should_inject_workflow(self, user_text: str, current_mode: str) -> bool:
        if current_mode in ("explore", "verify"):
            return False
        work_indicators = [
            "build",
            "compile",
            "fix",
            "debug",
            "implement",
            "create",
            "write",
            "generate",
            "refactor",
            "optimize",
            "test",
            "verify",
            "check",
            "run",
            "execute",
        ]
        text_lower = (user_text or "").lower()
        has_work_indicator = any(ind in text_lower for ind in work_indicators)
        chat_patterns = [
            r"^\s*hi\b",
            r"^\s*hello\b",
            r"^\s*hey\b",
            r"what can you do",
            r"who are you",
            r"help\s*$",
            r"^\s*thanks?\b",
            r"^\s*ok\b",
            r"^\s*bye\b",
        ]
        is_chat = any(re.search(pattern, text_lower) for pattern in chat_patterns)
        return has_work_indicator and not is_chat

    def describe_prompt(
        self,
        current_mode: str,
        workflow_state: str = "chat",
        session: Any = None,
    ) -> Optional[HarnessPrompt]:
        context = self._describe_context(current_mode, workflow_state=workflow_state)
        if context is None:
            return None
        del session
        return HarnessPrompt(
            mode_name=str(context.mode_name or ""),
            discipline_label=str(context.discipline_label or ""),
            pack_name=str(context.pack_name or ""),
            prompt_units=list(context.prompt_units or []),
        )

    def initialize_workflow_state(
        self,
        session: Any,
        user_text: str,
        current_mode: str,
        workflow_state: str = "chat",
    ) -> None:
        if not self.should_inject_workflow(user_text, current_mode):
            return
        graph = getattr(session, "task_graph", None)
        if graph is None or not graph.is_empty():
            return
        session.task_graph = TaskGraph.from_user_request(user_text, current_mode)
        self._sync_workflow_state(session)

    def sync_session_workflow(
        self,
        session: Any,
        current_mode: str,
        workflow_state: str = "chat",
        observations: Optional[List[Any]] = None,
    ) -> None:
        graph = getattr(session, "task_graph", None)
        if graph is None:
            return
        context = None
        if not graph.is_empty():
            context = self._describe_context(
                current_mode,
                workflow_state=workflow_state,
                current_phase=str(getattr(graph, "current_phase", "") or ""),
                observations=observations or [],
            )
        self._sync_workflow_state(session, context=context)

    def refresh_managed_session(
        self,
        managed_session: Any,
        workspace: str,
        observations: Optional[List[Any]] = None,
        task_store_module: Any = None,
    ) -> None:
        observations = list(observations or [])
        discipline_override = self._discipline_override(
            managed_session.current_mode,
            managed_session.workflow_state,
        )
        graph = self.harness_runner.update_task_graph(
            managed_session.session,
            managed_session.current_mode,
            observations=observations,
            discipline_override=discipline_override,
        )
        context = self._describe_context(
            managed_session.current_mode,
            workflow_state=managed_session.workflow_state,
            current_phase=str(getattr(graph, "current_phase", "") or ""),
            observations=[],
        )
        store = task_store_module or task_store
        if context is None:
            self._sync_workflow_state(managed_session.session)
            store.save_task_snapshot(
                workspace,
                managed_session.session.session_id,
                managed_session.current_mode,
                managed_session.workflow_state,
                "",
                "",
                "",
                [],
            )
            return
        self._sync_workflow_state(managed_session.session, context=context)
        workflow = managed_session.session.workflow_state.get("workflow") or {}
        metadata = workflow.get("metadata") or {}
        store.save_task_snapshot(
            workspace,
            managed_session.session.session_id,
            managed_session.current_mode,
            managed_session.workflow_state,
            str(metadata.get("discipline_profile") or ""),
            str(metadata.get("current_phase") or ""),
            str(workflow.get("summary") or ""),
            list(workflow.get("items") or []),
        )

    def build_mode_context(
        self,
        session: Any,
        current_mode: str,
        workflow_state: str = "chat",
    ) -> Any:
        graph = getattr(session, "task_graph", None)
        return self._describe_context(
            current_mode,
            workflow_state=workflow_state,
            current_phase=(
                str(getattr(graph, "current_phase", "") or "") if graph is not None else ""
            ),
        )

    def allowed_tool_names(self, mode_name: str, workflow_state: str = "chat") -> Set[str]:
        context = self._describe_context(mode_name, workflow_state=workflow_state)
        if context is None:
            return set()
        return set(pack_tool_names(context.pack_name))

    def handle_tool_call(
        self,
        session: Any,
        tool_name: str,
        current_mode: str,
        workflow_state: str = "chat",
    ) -> Optional[Observation]:
        if tool_name != "task_status":
            return None
        summary = ""
        phase = ""
        discipline = ""
        task_items = []  # type: List[Any]
        graph = getattr(session, "task_graph", None)
        if graph is not None and not graph.is_empty():
            mode_context = self._describe_context(current_mode, workflow_state=workflow_state)
            if mode_context is not None:
                summary = str(getattr(mode_context, "task_summary", "") or "")
                phase = str(getattr(mode_context, "current_phase", "") or "")
                discipline = str(getattr(mode_context, "discipline_label", "") or "")
                task_items = list(getattr(mode_context, "task_items", []) or [])
        if not summary:
            summary = "no active tasks"
        lines = [line for line in summary.splitlines() if line]
        return Observation(
            tool_name="task_status",
            success=True,
            error=None,
            data={
                "summary": summary,
                "preview": lines,
                "returned_count": len(lines),
                "total_count": len(lines),
                "has_more": False,
                "next_offset": 0,
                "result_ref": "",
                "current_mode": current_mode,
                "current_phase": phase,
                "discipline_profile": discipline,
                "tasks": task_items,
            },
        )

    def _describe_context(
        self,
        mode_name: str,
        workflow_state: str = "chat",
        current_phase: str = "",
        observations: Optional[List[Any]] = None,
    ) -> Any:
        if self.tools is not None:
            describe = getattr(self.tools, "describe_mode", None)
            if callable(describe):
                return describe(
                    mode_name,
                    workflow_state=workflow_state,
                    current_phase=current_phase,
                    observations=observations or [],
                )
        discipline_override = self._discipline_override(mode_name, workflow_state)
        return self.harness_runner.describe_mode(
            mode_name,
            discipline_override=discipline_override,
            current_phase=current_phase,
            observations=observations or [],
        )

    def _discipline_override(self, mode_name: str, workflow_state: str = "chat") -> Optional[str]:
        if str(mode_name or "") == "build" and str(workflow_state or "") == "plan":
            return "full_spec_tdd"
        return None

    def _sync_workflow_state(self, session: Any, context: Any = None) -> None:
        graph = getattr(session, "task_graph", None)
        if graph is None:
            return
        summary = str(graph.render_summary())
        items = list(graph.to_items())
        phase = str(getattr(graph, "current_phase", "") or "")
        discipline = str(getattr(graph, "discipline", "") or "")
        activity = ""
        if context is not None:
            summary = str(getattr(context, "task_summary", "") or summary)
            items = list(getattr(context, "task_items", []) or items)
            phase = str(getattr(context, "current_phase", "") or phase)
            discipline = str(getattr(context, "discipline_label", "") or discipline)
            activity = str(getattr(context, "current_activity", "") or "")
        session.workflow_state["workflow"] = {
            "id": "c_harness",
            "label": "C Harness",
            "state": "idle" if graph.is_empty() else "active",
            "summary": summary,
            "items": items,
            "activity": activity,
            "metadata": {
                "current_phase": phase,
                "discipline_profile": discipline,
            },
        }
