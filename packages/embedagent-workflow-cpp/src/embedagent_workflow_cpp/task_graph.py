from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class TaskNode(object):
    task_id: str
    title: str
    kind: str = "phase"
    status: str = "pending"
    source: str = "harness"
    note: str = ""
    evidence_refs: List[str] = field(default_factory=list)


@dataclass
class TaskGraph(object):
    mode_name: str
    discipline: str
    current_phase: str = ""
    tasks: List[TaskNode] = field(default_factory=list)

    @classmethod
    def empty(cls):
        return cls(mode_name="", discipline="", current_phase="", tasks=[])

    def is_empty(self):
        return not self.tasks or len(self.tasks) == 0

    def clone(self):
        return TaskGraph(
            mode_name=str(self.mode_name or ""),
            discipline=str(self.discipline or ""),
            current_phase=str(self.current_phase or ""),
            tasks=[
                TaskNode(
                    task_id=str(task.task_id or ""),
                    title=str(task.title or ""),
                    kind=str(getattr(task, "kind", "phase") or "phase"),
                    status=str(task.status or "pending"),
                    source=str(getattr(task, "source", "harness") or "harness"),
                    note=str(getattr(task, "note", "") or ""),
                    evidence_refs=list(getattr(task, "evidence_refs", []) or []),
                )
                for task in list(self.tasks or [])
            ],
        )

    @classmethod
    def from_workflow_projection(cls, workflow: Any):
        if not isinstance(workflow, dict):
            return None
        metadata = workflow.get("metadata")
        metadata = dict(metadata) if isinstance(metadata, dict) else {}
        raw_items = workflow.get("items")
        if not isinstance(raw_items, list):
            raw_items = []
        tasks = []
        mode_name = ""
        for index, raw_item in enumerate(raw_items, start=1):
            if not isinstance(raw_item, dict):
                continue
            title = str(raw_item.get("content") or raw_item.get("title") or "").strip()
            if not mode_name and ":" in title:
                mode_name = title.split(":", 1)[0].strip()
            status = str(raw_item.get("status") or "pending").strip() or "pending"
            tasks.append(
                TaskNode(
                    task_id=str(raw_item.get("task_id") or raw_item.get("id") or index),
                    title=title,
                    kind=str(raw_item.get("kind") or "phase"),
                    status=status,
                    source=str(raw_item.get("source") or "harness"),
                    note=str(raw_item.get("note") or ""),
                    evidence_refs=list(raw_item.get("evidence_refs") or []),
                )
            )
        return cls(
            mode_name=mode_name,
            discipline=str(metadata.get("discipline_profile") or metadata.get("discipline") or ""),
            current_phase=str(metadata.get("current_phase") or ""),
            tasks=tasks,
        )

    @classmethod
    def from_user_request(cls, user_text, mode_name):
        """Create task graph from explicit user request."""
        tasks = [
            TaskNode(
                task_id="task-1",
                kind="request",
                title="%s: %s" % (str(mode_name or ""), str(user_text or "")[:50]),
                status="in_progress",
                source="user",
            )
        ]
        return cls(
            mode_name=str(mode_name or ""),
            discipline="",
            current_phase="request",
            tasks=tasks,
        )

    @classmethod
    def for_mode(cls, mode_name, discipline, track=None, current_phase=""):
        phases = []
        for item in list(track or []):
            phases.append(str(getattr(item, "value", item) or ""))
        if phases:
            current_value = str(current_phase or phases[0] or "")
            try:
                current_index = phases.index(current_value)
            except ValueError:
                current_index = 0
            tasks = []
            for index, phase in enumerate(phases):
                status = "pending"
                if index < current_index:
                    status = "completed"
                elif index == current_index:
                    status = "in_progress"
                tasks.append(
                    TaskNode(
                        task_id="task-%s" % (index + 1),
                        kind="phase",
                        title="%s:%s" % (str(mode_name or ""), phase),
                        status=status,
                        source="harness",
                    )
                )
            return cls(
                mode_name=str(mode_name or ""),
                discipline=str(discipline or ""),
                current_phase=current_value,
                tasks=tasks,
            )
        title = "%s:%s" % (str(mode_name or ""), str(discipline or ""))
        return cls(
            mode_name=str(mode_name or ""),
            discipline=str(discipline or ""),
            current_phase=str(current_phase or ""),
            tasks=[
                TaskNode(
                    task_id="task-1",
                    kind="phase",
                    title=title,
                    status="in_progress",
                    source="harness",
                )
            ],
        )

    def replace_with(self, other):
        self.mode_name = str(other.mode_name or "")
        self.discipline = str(other.discipline or "")
        self.current_phase = str(other.current_phase or "")
        self.tasks = [
            TaskNode(
                task_id=str(task.task_id),
                kind=str(getattr(task, "kind", "phase") or "phase"),
                title=str(task.title or ""),
                status=str(task.status or "pending"),
                source=str(getattr(task, "source", "harness") or "harness"),
                note=str(getattr(task, "note", "") or ""),
                evidence_refs=list(getattr(task, "evidence_refs", []) or []),
            )
            for task in list(other.tasks or [])
        ]

    def current_task(self):
        for task in self.tasks:
            if task.status == "in_progress":
                return task
        return None

    def complete_current(self, note):
        current = self.current_task()
        if current is None:
            return
        current.status = "completed"
        current.note = str(note or "")

    def start_next(self, title):
        self.tasks.append(
            TaskNode(
                task_id="task-%s" % (len(self.tasks) + 1),
                title=str(title or ""),
                status="in_progress",
            )
        )

    def render_summary(self):
        lines = []
        for task in self.tasks:
            lines.append("%s %s" % (task.status, task.title))
        return "\n".join(lines)

    def to_items(self) -> List[Dict[str, object]]:
        items = []
        for index, task in enumerate(self.tasks, start=1):
            items.append(
                {
                    "id": index,
                    "content": task.title,
                    "status": task.status,
                    "done": task.status == "completed",
                    "note": task.note,
                }
            )
        return items
