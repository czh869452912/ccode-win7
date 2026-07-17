from __future__ import annotations

from embedagent_core.profile import AgentModeDescriptor, AgentProfile
from embedagent_host.runtime.profiles import (
    BASE_DISCUSSION_TOOLS,
    BASE_READ_TOOLS,
    BASE_VERIFY_TOOLS,
    BASE_WRITE_TOOLS,
    SPEC_WRITABLE_GLOBS,
)

C_CPP_DEVELOPMENT_WRITABLE_GLOBS = SPEC_WRITABLE_GLOBS + [
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
                writable_globs=list(C_CPP_DEVELOPMENT_WRITABLE_GLOBS),
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
                writable_globs=list(C_CPP_DEVELOPMENT_WRITABLE_GLOBS),
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
                color_token="info",
            ),
        ],
    )
