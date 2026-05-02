from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List, Optional

from embedagent.session import Observation
from embedagent.tools._base import ToolContext, ToolDefinition


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
