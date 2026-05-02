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
            for name in ("clang", "clang.exe", "clang++", "clang++.exe", "clang-cl", "clang-cl.exe"):
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
