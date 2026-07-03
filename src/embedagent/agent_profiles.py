from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class AgentModeDescriptor(object):
    slug: str
    label: str
    description: str
    system_prompt: str
    allowed_tools: List[str] = field(default_factory=list)
    writable_globs: List[str] = field(default_factory=list)
    icon_key: str = "circle"
    color_token: str = "info"

    def to_mode_definition(self) -> Dict[str, object]:
        return {
            "slug": self.slug,
            "system_prompt": self.system_prompt,
            "allowed_tools": list(self.allowed_tools),
            "writable_globs": list(self.writable_globs),
            "label": self.label,
            "description": self.description,
            "icon_key": self.icon_key,
            "color_token": self.color_token,
        }

    def to_capability_metadata(self, profile_id: str, order: int = 0) -> Dict[str, object]:
        return {
            "id": self.slug,
            "label": self.label,
            "description": self.description,
            "icon_key": self.icon_key,
            "color_token": self.color_token,
            "order": int(order),
            "command_id": "mode.%s" % self.slug,
            "dispatch": {"kind": "mode.set", "mode": self.slug},
            "source_type": "agent_profile",
            "source_id": profile_id,
        }


@dataclass(frozen=True)
class AgentProfile(object):
    profile_id: str
    label: str
    default_mode: str
    modes: List[AgentModeDescriptor]

    def mode_registry(self) -> Dict[str, Dict[str, object]]:
        return dict((item.slug, item.to_mode_definition()) for item in self.modes)

    def require_mode(self, mode_name: str) -> AgentModeDescriptor:
        requested = str(mode_name or "").strip()
        for item in self.modes:
            if item.slug == requested:
                return item
        raise ValueError("Unknown mode %r" % (mode_name,))

    def allowed_tools_for(self, mode_name: str) -> List[str]:
        return list(self.require_mode(mode_name).allowed_tools)

    def writable_globs_for(self, mode_name: str) -> List[str]:
        return list(self.require_mode(mode_name).writable_globs)

    def mode_descriptor_payloads(self) -> List[Dict[str, object]]:
        return [
            item.to_capability_metadata(self.profile_id, order=index)
            for index, item in enumerate(self.modes)
        ]


BASE_READ_TOOLS = ["read_file", "list_dir", "glob_files", "grep_text"]
BASE_DISCUSSION_TOOLS = BASE_READ_TOOLS + ["git_status", "git_log", "ask_user"]
BASE_WRITE_TOOLS = BASE_READ_TOOLS + [
    "write_file",
    "edit_file",
    "bash",
    "author_local_capability",
    "ask_user",
]
BASE_VERIFY_TOOLS = BASE_READ_TOOLS + ["bash", "ask_user"]

SPEC_WRITABLE_GLOBS = ["**/*.md", "**/*.rst", "**/*.txt"]
DEVELOPMENT_WRITABLE_GLOBS = SPEC_WRITABLE_GLOBS + [
    "**/*.c",
    "**/*.cc",
    "**/*.cpp",
    "**/*.cxx",
    "**/*.h",
    "**/*.hh",
    "**/*.hpp",
    "**/*.hxx",
    "**/*.py",
    "**/*.pyi",
    "**/*.ps1",
    "**/*.bat",
    "**/*.toml",
    "**/*.cfg",
    "**/*.ini",
    "**/*.json",
    "**/*.yaml",
    "**/*.yml",
    "**/*.cmake",
    "CMakeLists.txt",
    "**/CMakeLists.txt",
    "Makefile",
    "**/Makefile",
    "makefile",
    "**/makefile",
    "meson.build",
    "**/meson.build",
]


GENERIC_DEVELOPMENT_WRITABLE_GLOBS = ["**/*"]
PYTHON_DEVELOPMENT_WRITABLE_GLOBS = SPEC_WRITABLE_GLOBS + [
    "**/*.py",
    "**/*.pyi",
    "**/*.toml",
    "**/*.cfg",
    "**/*.ini",
    "**/*.json",
    "**/*.yaml",
    "**/*.yml",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "requirements-*.txt",
]
HTML_DEVELOPMENT_WRITABLE_GLOBS = SPEC_WRITABLE_GLOBS + [
    "**/*.html",
    "**/*.htm",
    "**/*.css",
    "**/*.js",
    "**/*.jsx",
    "**/*.ts",
    "**/*.tsx",
    "**/*.json",
    "**/*.svg",
    "**/*.toml",
    "**/*.yaml",
    "**/*.yml",
]


def _standard_profile_modes(
    domain_label: str,
    build_description: str,
    debug_description: str,
    writable_globs: List[str],
) -> List[AgentModeDescriptor]:
    return [
        AgentModeDescriptor(
            slug="explore",
            label="Explore",
            description="Read project context and discuss design without writing files.",
            system_prompt=(
                "你当前处于 explore 模式（默认模式）。"
                "负责阅读工程上下文、解释逻辑、讨论设计方案，以及帮助用户理清思路。"
                "不要预设固定技术栈；当前场景是%s。"
                "当用户需要修改文件时，询问应切换到哪个模式，"
                "提供 2-4 个选项（如 spec / build / debug），等待用户用 /mode 切换。"
                "不要擅自写文件。"
            )
            % domain_label,
            allowed_tools=list(BASE_DISCUSSION_TOOLS),
            writable_globs=[],
            icon_key="search",
            color_token="info",
        ),
        AgentModeDescriptor(
            slug="spec",
            label="Spec",
            description="Write requirements, boundaries, and design documentation.",
            system_prompt=(
                "你当前处于 spec 模式，负责整理%s场景的需求、边界条件、验收标准和文档。"
                "先用 list_dir / glob_files 探测现有文档目录；若工作区为空或无文档目录，可在 docs/ 下创建。"
                "不要擅自切到实现模式；若需要实现，告知用户需要切换模式。"
            )
            % domain_label,
            allowed_tools=BASE_READ_TOOLS + ["write_file", "ask_user"],
            writable_globs=list(SPEC_WRITABLE_GLOBS),
            icon_key="file-text",
            color_token="accent",
        ),
        AgentModeDescriptor(
            slug="build",
            label="Build",
            description=build_description,
            system_prompt=(
                "你当前处于 build 模式，负责完成%s场景的开发闭环。"
                "你拥有该场景配置的读写边界，但不要因为进入 build 模式而预设任务或固定阶段。"
                "仅在用户提出明确开发、修复、重构、运行或验证请求时推进相应工作流。"
                "应复用现有工程结构，不要假设固定目录；如遇关键分歧，请求用户确认。"
            )
            % domain_label,
            allowed_tools=list(BASE_WRITE_TOOLS),
            writable_globs=list(writable_globs),
            icon_key="hammer",
            color_token="success",
        ),
        AgentModeDescriptor(
            slug="debug",
            label="Debug",
            description=debug_description,
            system_prompt=(
                "你当前处于 debug 模式，负责复现%s场景中的问题、定位根因并做最小修复。"
                "先根据当前工程结构和诊断缩小范围，不要假设固定目录。"
                "若需要更大范围重构，告知用户建议切换到 build 模式。"
            )
            % domain_label,
            allowed_tools=list(BASE_WRITE_TOOLS),
            writable_globs=list(writable_globs),
            icon_key="bug",
            color_token="warning",
        ),
        AgentModeDescriptor(
            slug="verify",
            label="Verify",
            description="Run read-only quality gates and report evidence.",
            system_prompt=(
                "你当前处于 verify 模式，负责执行%s场景的构建、测试、静态检查并给出质量门结论。"
                "本模式不改代码；发现问题时只说明证据与建议，并告知用户需要切换到哪个模式修复。"
            )
            % domain_label,
            allowed_tools=list(BASE_VERIFY_TOOLS),
            writable_globs=[],
            icon_key="badge-check",
            color_token="verify",
        ),
    ]


def generic_agent_profile() -> AgentProfile:
    return AgentProfile(
        profile_id="embedagent.generic",
        label="Generic Agent",
        default_mode="explore",
        modes=_standard_profile_modes(
            "通用工程",
            "Implement and refactor within a general workspace write boundary.",
            "Reproduce, diagnose, and minimally repair general project failures.",
            GENERIC_DEVELOPMENT_WRITABLE_GLOBS,
        ),
    )


def python_agent_profile() -> AgentProfile:
    return AgentProfile(
        profile_id="embedagent.python",
        label="Python Agent",
        default_mode="explore",
        modes=_standard_profile_modes(
            "Python 工程",
            "Implement and refactor Python code within the configured write boundary.",
            "Reproduce, diagnose, and minimally repair Python failures.",
            PYTHON_DEVELOPMENT_WRITABLE_GLOBS,
        ),
    )


def html_agent_profile() -> AgentProfile:
    return AgentProfile(
        profile_id="embedagent.html",
        label="HTML Agent",
        default_mode="explore",
        modes=_standard_profile_modes(
            "HTML/Web 前端工程",
            "Implement and refactor HTML, CSS, and frontend code within the configured write boundary.",
            "Reproduce, diagnose, and minimally repair HTML/Web frontend failures.",
            HTML_DEVELOPMENT_WRITABLE_GLOBS,
        ),
    )


def default_c_cpp_agent_profile() -> AgentProfile:
    return AgentProfile(
        profile_id="embedagent.default_c_cpp",
        label="Default C/C++ Agent",
        default_mode="explore",
        modes=[
            AgentModeDescriptor(
                slug="explore",
                label="Explore",
                description="Read code and discuss design without writing files.",
                system_prompt=(
                    "你当前处于 explore 模式（默认模式）。"
                    "负责阅读代码、解释逻辑、讨论设计方案，以及帮助用户理清思路。"
                    "当用户需要修改文件时，询问应切换到哪个模式，"
                    "提供 2-4 个选项（如 spec / build / debug），等待用户用 /mode 切换。"
                    "不要擅自写文件。"
                ),
                allowed_tools=list(BASE_DISCUSSION_TOOLS),
                writable_globs=[],
                icon_key="search",
                color_token="info",
            ),
            AgentModeDescriptor(
                slug="spec",
                label="Spec",
                description="Write requirements, boundaries, and design documentation.",
                system_prompt=(
                    "你当前处于 spec 模式，负责整理需求、边界条件、验收标准和文档。"
                    "先用 list_dir / glob_files 探测现有文档目录；若工作区为空或无文档目录，可在 docs/ 下创建。"
                    "不要擅自切到实现模式；若需要实现，告知用户需要切换模式。"
                ),
                allowed_tools=BASE_READ_TOOLS + ["write_file", "ask_user"],
                writable_globs=list(SPEC_WRITABLE_GLOBS),
                icon_key="file-text",
                color_token="accent",
            ),
            AgentModeDescriptor(
                slug="build",
                label="Build",
                description="Implement and refactor within the configured write boundary.",
                system_prompt=(
                    "你当前处于 build 模式，负责完成开发闭环。"
                    "你拥有开发所需的读写边界，但不要因为进入 build 模式而预设任务或固定阶段。"
                    "仅在用户提出明确开发、修复、重构、运行或验证请求时推进相应工作流。"
                    "应复用现有工程结构，不要假设固定目录；如遇关键分歧，请求用户确认。"
                ),
                allowed_tools=list(BASE_WRITE_TOOLS),
                writable_globs=list(DEVELOPMENT_WRITABLE_GLOBS),
                icon_key="hammer",
                color_token="success",
            ),
            AgentModeDescriptor(
                slug="debug",
                label="Debug",
                description="Reproduce, diagnose, and minimally repair failures.",
                system_prompt=(
                    "你当前处于 debug 模式，负责复现问题、定位根因并做最小修复。"
                    "先根据当前工程结构和诊断缩小范围，不要假设固定目录。"
                    "若需要更大范围重构，告知用户建议切换到 build 模式。"
                ),
                allowed_tools=list(BASE_WRITE_TOOLS),
                writable_globs=list(DEVELOPMENT_WRITABLE_GLOBS),
                icon_key="bug",
                color_token="warning",
            ),
            AgentModeDescriptor(
                slug="verify",
                label="Verify",
                description="Run read-only quality gates and report evidence.",
                system_prompt=(
                    "你当前处于 verify 模式，负责执行构建、测试、静态检查并给出质量门结论。"
                    "本模式不改代码；发现问题时只说明证据与建议，并告知用户需要切换到哪个模式修复。"
                ),
                allowed_tools=list(BASE_VERIFY_TOOLS),
                writable_globs=[],
                icon_key="badge-check",
                color_token="verify",
            ),
        ],
    )
