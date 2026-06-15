from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape


@dataclass(frozen=True)
class SkillRecord:
    name: str
    description: str
    path: str
    base_dir: str
    disable_model_invocation: bool
    prompt_visible: bool
    source: str
    metadata: Dict[str, Any]


class SkillIndex(object):
    def __init__(self, records: List[SkillRecord]) -> None:
        self._records = list(records or [])

    def records(self) -> List[SkillRecord]:
        return list(self._records)

    def visible_records(self) -> List[SkillRecord]:
        records = [item for item in self._records if item.prompt_visible]
        return sorted(records, key=lambda item: item.name)

    def record_by_name(self, name: str) -> Optional[SkillRecord]:
        target = str(name or "").strip().lower()
        if not target:
            return None
        for record in self._records:
            if record.name.lower() == target:
                return record
        return None

    def prompt_text(self) -> str:
        visible = [
            item
            for item in self.visible_records()
            if item.name and item.description and item.path
        ]
        if not visible:
            return ""
        lines = [
            "The following workspace-local skills provide specialized instructions for specific tasks.",
            "Use read_file to load a skill file when the task matches its description.",
            "When a skill file references a relative path, resolve it against the skill directory.",
            "",
            "<available_skills>",
        ]
        for item in visible:
            lines.extend(
                [
                    "  <skill>",
                    "    <name>%s</name>" % escape(item.name),
                    "    <description>%s</description>" % escape(item.description),
                    "    <location>%s</location>" % escape(item.path),
                    "  </skill>",
                ]
            )
        lines.append("</available_skills>")
        return "\n".join(lines)

    def command_specs(self) -> List[Any]:
        from embedagent.slash_commands import SlashCommandSpec

        specs = []
        for item in self.visible_records():
            if not item.name or not item.description:
                continue
            specs.append(
                SlashCommandSpec(
                    "skill:%s" % item.name,
                    "/skill:%s [args]" % item.name,
                    item.description,
                )
            )
        return specs

    def safe_summary(self) -> Dict[str, Any]:
        names = [item.name for item in self.visible_records() if item.name]
        return {
            "skill_count": len(self._records),
            "visible_skill_count": len(names),
            "visible_skill_names": names,
        }


def build_skill_index(resources: Any) -> SkillIndex:
    if isinstance(resources, dict):
        items = list(resources.get("skills") or [])
    else:
        items = list(resources or [])
    records = []
    for item in items:
        if not isinstance(item, dict):
            continue
        record = _record_from_dict(item)
        if record is not None:
            records.append(record)
    return SkillIndex(records)


def _record_from_dict(item: Dict[str, Any]) -> Optional[SkillRecord]:
    name = str(item.get("name") or "").strip()
    path = str(item.get("path") or "").strip()
    if not name or not path:
        return None
    return SkillRecord(
        name=name,
        description=str(item.get("description") or "").strip(),
        path=path,
        base_dir=str(item.get("base_dir") or "").strip(),
        disable_model_invocation=bool(item.get("disable_model_invocation", False)),
        prompt_visible=bool(item.get("prompt_visible", False)),
        source=str(item.get("source") or "local_resource").strip() or "local_resource",
        metadata=dict(item),
    )
