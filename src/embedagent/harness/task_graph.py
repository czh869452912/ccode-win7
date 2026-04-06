from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class TaskNode(object):
    task_id: str
    title: str
    status: str = "pending"
    note: str = ""


@dataclass
class TaskGraph(object):
    mode_name: str
    discipline: str
    tasks: List[TaskNode] = field(default_factory=list)

    @classmethod
    def for_mode(cls, mode_name, discipline):
        title = "%s:%s" % (str(mode_name or ""), str(discipline or ""))
        return cls(
            mode_name=str(mode_name or ""),
            discipline=str(discipline or ""),
            tasks=[TaskNode(task_id="task-1", title=title, status="in_progress")],
        )

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
