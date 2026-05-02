from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List, Optional

from embedagent.session import Observation
from embedagent.tools._base import (
    DEFAULT_BUILD_TIMEOUT_SEC,
    ToolContext,
    ToolDefinition,
    ToolError,
)


def build_tools(ctx: ToolContext) -> List[ToolDefinition]:
    def _list_compilers(arguments: Dict[str, Any]) -> Observation:
        compilers = _discover_compilers(ctx)
        return Observation(
            tool_name="list_compilers",
            success=True,
            error=None,
            data={
                "compilers": compilers,
                "count": len(compilers),
                "primary": compilers[0]["name"] if compilers else "",
            },
        )

    def _configure_build_env(arguments: Dict[str, Any]) -> Observation:
        compiler_pref = str(arguments.get("compiler") or "").strip()
        build_type = str(arguments.get("build_type") or "").strip().lower()
        target = str(arguments.get("target") or "").strip()

        compilers = _discover_compilers(ctx)

        # Select compiler based on preference or default to first available
        selected = None
        if compiler_pref:
            for comp in compilers:
                if comp["name"] == compiler_pref or comp["name"].startswith(compiler_pref):
                    selected = comp
                    break
        if selected is None and compilers:
            selected = compilers[0]

        # Determine build type and recommended flags
        build_types = {
            "debug": {"c_flags": "-O0 -g", "cxx_flags": "-O0 -g", "linker_flags": ""},
            "release": {"c_flags": "-O3 -DNDEBUG", "cxx_flags": "-O3 -DNDEBUG", "linker_flags": ""},
            "relwithdebinfo": {"c_flags": "-O2 -g", "cxx_flags": "-O2 -g", "linker_flags": ""},
            "minsizerel": {
                "c_flags": "-Os -DNDEBUG",
                "cxx_flags": "-Os -DNDEBUG",
                "linker_flags": "",
            },
        }
        type_config = build_types.get(build_type, build_types["debug"])

        # Get environment with managed tools prepended to PATH
        env = ctx.build_process_env()

        # Build directory suggestion
        build_dir = "build"
        if build_type and build_type not in ("default", "build"):
            build_dir = "build/%s" % build_type.replace("\\", "/")

        config = {
            "compiler": selected,
            "compilers_available": compilers,
            "build_type": build_type or "debug",
            "c_flags": type_config["c_flags"],
            "cxx_flags": type_config["cxx_flags"],
            "linker_flags": type_config["linker_flags"],
            "environment": {
                "PATH": env.get("PATH", ""),
                "EMBEDAGENT_LLVM_ROOT": env.get("EMBEDAGENT_LLVM_ROOT", ""),
                "EMBEDAGENT_RUNTIME_SOURCE": env.get("EMBEDAGENT_RUNTIME_SOURCE", ""),
            },
            "build_dir": build_dir,
            "target": target,
        }

        return Observation(
            tool_name="configure_build_env",
            success=True,
            error=None,
            data=config,
        )

    def _run_build(arguments: Dict[str, Any]) -> Observation:
        command_text = str(arguments.get("command") or "").strip()
        if not command_text:
            raise ToolError("命令不能为空。")
        cwd_argument = str(arguments.get("cwd") or ".")
        timeout_sec = int(arguments.get("timeout_sec") or DEFAULT_BUILD_TIMEOUT_SEC)
        diagnostic = bool(arguments.get("diagnostic", True))

        cwd = ctx.resolve_directory(cwd_argument)
        if timeout_sec <= 0:
            raise ToolError("timeout_sec 必须大于 0。")

        resolved_command, managed_tool, _ = ctx.rewrite_command_for_managed_tools(command_text)

        progress_lines = []  # type: List[Dict[str, Any]]

        def _progress_callback(payload: Dict[str, Any]) -> None:
            progress_lines.append(payload)

        result = ctx.run_subprocess_streaming(
            command=resolved_command,
            cwd=cwd,
            timeout_sec=timeout_sec,
            shell=True,
            stop_event=ctx.get_interrupt_event(),
            progress_callback=_progress_callback,
        )

        if diagnostic:
            observation = ctx.build_diagnostic_observation(
                "run_build", resolved_command, cwd, result
            )
        else:
            observation = ctx.build_command_observation("run_build", resolved_command, cwd, result)

        if isinstance(observation.data, dict):
            data = dict(observation.data)
            data["requested_command"] = command_text
            if managed_tool:
                data["managed_primary_tool"] = managed_tool
            data["streaming_progress"] = progress_lines[:1000]
            data["streaming_progress_count"] = len(progress_lines)
            observation.data = data

        return observation

    def _run_build(arguments: Dict[str, Any]) -> Observation:
        command_text = str(arguments.get("command") or "").strip()
        if not command_text:
            raise ToolError("命令不能为空。")
        cwd_argument = str(arguments.get("cwd") or ".")
        timeout_sec = int(arguments.get("timeout_sec") or DEFAULT_BUILD_TIMEOUT_SEC)
        diagnostic = bool(arguments.get("diagnostic", True))

        cwd = ctx.resolve_directory(cwd_argument)
        if timeout_sec <= 0:
            raise ToolError("timeout_sec 必须大于 0。")

        resolved_command, managed_tool, _ = ctx.rewrite_command_for_managed_tools(command_text)

        progress_lines = []  # type: List[Dict[str, Any]]

        def _progress_callback(payload: Dict[str, Any]) -> None:
            progress_lines.append(payload)

        result = ctx.run_subprocess_streaming(
            command=resolved_command,
            cwd=cwd,
            timeout_sec=timeout_sec,
            shell=True,
            stop_event=ctx.get_interrupt_event(),
            progress_callback=_progress_callback,
        )

        if diagnostic:
            observation = ctx.build_diagnostic_observation(
                "run_build", resolved_command, cwd, result
            )
        else:
            observation = ctx.build_command_observation("run_build", resolved_command, cwd, result)

        if isinstance(observation.data, dict):
            data = dict(observation.data)
            data["requested_command"] = command_text
            if managed_tool:
                data["managed_primary_tool"] = managed_tool
            data["streaming_progress"] = progress_lines[:1000]
            data["streaming_progress_count"] = len(progress_lines)

            # Scan for build artifacts on success
            if result["exit_code"] == 0 and not result["timed_out"]:
                artifacts = _scan_build_artifacts(ctx, cwd)
                data["artifacts"] = artifacts
                data["artifact_count"] = len(artifacts)
            else:
                data["artifacts"] = []
                data["artifact_count"] = 0

            # Linker diagnostics already included by build_diagnostic_observation
            observation.data = data

        return observation

    return [
        ToolDefinition(
            name="list_compilers",
            description="列出当前可用的 C/C++ 编译器。用于确认工具链环境，包括 bundle、workspace 和 system 来源。",
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            handler=_list_compilers,
            read_only=True,
            concurrency_safe=True,
        ),
        ToolDefinition(
            name="configure_build_env",
            description="配置构建环境。根据可用编译器、构建类型和目标生成推荐的编译标志、环境变量和构建目录。",
            parameters={
                "type": "object",
                "properties": {
                    "compiler": {
                        "type": "string",
                        "description": "首选编译器名称（如 clang、gcc、cl）。如不可用则回退到第一个可用编译器。",
                    },
                    "build_type": {
                        "type": "string",
                        "description": "构建类型：debug、release、relwithdebinfo、minsizerel。默认 debug。",
                    },
                    "target": {
                        "type": "string",
                        "description": "构建目标名称（可选）。",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
            handler=_configure_build_env,
            read_only=True,
            concurrency_safe=True,
        ),
        ToolDefinition(
            name="run_build",
            description="运行构建命令并实时捕获输出。支持诊断解析、托管工具自动替换和流式进度上报。用于编译 C/C++ 项目或运行构建脚本。",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的构建命令。示例：clang -o demo demo.c",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "命令执行目录，相对于项目根目录。示例：.",
                    },
                    "timeout_sec": {
                        "type": "integer",
                        "description": "命令超时时间，单位为秒。默认 120。",
                    },
                    "diagnostic": {
                        "type": "boolean",
                        "description": "是否解析编译器诊断信息。默认 true。",
                    },
                },
                "required": ["command"],
                "additionalProperties": False,
            },
            handler=_run_build,
            read_only=False,
            concurrency_safe=False,
            interrupt_behavior="cancel",
        ),
    ]


def _discover_compilers(ctx: ToolContext) -> List[Dict[str, Any]]:
    """Discover available C/C++ compilers in managed toolchain and system PATH."""
    compilers = []  # type: List[Dict[str, Any]]
    seen_paths = set()  # type: set[str]

    # Check managed LLVM toolchain
    llvm_root, llvm_source = ctx.resolve_managed_tool_path("llvm")
    if llvm_root:
        bin_dir = os.path.join(llvm_root, "bin")
        if os.path.isdir(bin_dir):
            for name in (
                "clang",
                "clang.exe",
                "clang++",
                "clang++.exe",
                "clang-cl",
                "clang-cl.exe",
            ):
                executable = os.path.join(bin_dir, name)
                if os.path.isfile(executable):
                    resolved = os.path.realpath(executable)
                    if resolved not in seen_paths:
                        seen_paths.add(resolved)
                        version = _get_compiler_version(ctx, resolved)
                        compilers.append(
                            {
                                "name": os.path.splitext(name)[0],
                                "path": ctx.display_path(resolved),
                                "version": version,
                                "source": llvm_source,
                                "family": "llvm",
                            }
                        )

    # Check system PATH for other compilers
    system_compilers = [
        ("gcc", "gcc", "gnu"),
        ("g++", "g++", "gnu"),
        ("clang", "clang", "llvm"),
        ("clang++", "clang++", "llvm"),
    ]
    if os.name == "nt":
        system_compilers.extend(
            [
                ("cl", "cl", "msvc"),
                ("clang-cl", "clang-cl", "llvm"),
            ]
        )

    for command_name, display_name, family in system_compilers:
        executable = _find_in_path(command_name)
        if executable:
            resolved = os.path.realpath(executable)
            if resolved not in seen_paths:
                seen_paths.add(resolved)
                version = _get_compiler_version(ctx, resolved)
                compilers.append(
                    {
                        "name": display_name,
                        "path": resolved,
                        "version": version,
                        "source": "system",
                        "family": family,
                    }
                )

    return compilers


def _find_in_path(command_name: str) -> Optional[str]:
    """Find an executable in system PATH."""
    executable = shutil.which(command_name)
    if executable:
        return executable
    if os.name == "nt" and not command_name.endswith(".exe"):
        executable = shutil.which(command_name + ".exe")
        if executable:
            return executable
    return None


def _get_compiler_version(ctx: ToolContext, executable: str) -> str:
    """Run compiler with --version (or equivalent) and return version string."""
    try:
        basename = os.path.basename(executable).lower()
        if basename in ("cl.exe", "cl"):
            # MSVC cl.exe does not support --version; version is in stderr
            result = ctx.run_subprocess(
                command=[executable],
                cwd=ctx.workspace,
                timeout_sec=5,
                shell=False,
            )
            output = (result.get("stderr") or "") + "\n" + (result.get("stdout") or "")
            for line in output.splitlines():
                line = line.strip()
                if "Microsoft" in line and ("C/C++" in line or "Optimizing" in line):
                    return line
                if "Version" in line and any(ch.isdigit() for ch in line):
                    return line
            return ""
        else:
            result = ctx.run_subprocess(
                command=[executable, "--version"],
                cwd=ctx.workspace,
                timeout_sec=5,
                shell=False,
            )
            output = result.get("stdout") or ""
            for line in output.splitlines():
                line = line.strip()
                if line:
                    return line
            return ""
    except Exception:
        return ""


ARTIFACT_EXTENSIONS = frozenset(
    (".exe", ".dll", ".lib", ".a", ".so", ".o", ".obj", ".elf", ".bin", ".out", ".wasm")
)
MAX_ARTIFACTS = 50


def _format_size(size_bytes: int) -> str:
    """Format a byte size into human-readable string."""
    if size_bytes < 1024:
        return "%d B" % size_bytes
    if size_bytes < 1024 * 1024:
        return "%.1f KB" % (size_bytes / 1024.0)
    return "%.1f MB" % (size_bytes / 1024.0 / 1024.0)


def _scan_build_artifacts(ctx: ToolContext, build_dir: str) -> List[Dict[str, Any]]:
    """Scan build directory for artifact files and return their info."""
    artifacts = []  # type: List[Dict[str, Any]]
    if not os.path.isdir(build_dir):
        return artifacts
    for root, _dirnames, filenames in os.walk(build_dir):
        for filename in filenames:
            if not any(filename.lower().endswith(ext) for ext in ARTIFACT_EXTENSIONS):
                continue
            full_path = os.path.join(root, filename)
            try:
                size = os.path.getsize(full_path)
            except OSError:
                continue
            rel_path = ctx.display_path(full_path)
            artifacts.append(
                {
                    "path": rel_path,
                    "size_bytes": size,
                    "size_human": _format_size(size),
                }
            )
            if len(artifacts) >= MAX_ARTIFACTS:
                break
        if len(artifacts) >= MAX_ARTIFACTS:
            break
    artifacts.sort(key=lambda a: a["path"])
    return artifacts
