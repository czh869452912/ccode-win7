"""EmbedAgent 配置加载模块。

支持两级配置文件：
  - 用户级：~/.embedagent/config.json
  - 项目级：<workspace>/.embedagent/config.json

加载优先级（后者覆盖前者）：代码默认值 < 用户级 < 项目级 < CLI 参数/环境变量。

配置文件 JSON 格式示例::

    {
        "base_url": "http://127.0.0.1:8000/v1",
        "model": "qwen3.5-coder",
        "timeout": 120,
        "max_context_tokens": 32000,
        "reserve_output_tokens": 3000,
        "chars_per_token": 3.0,
        "max_recent_turns": 4,
        "max_turns": 8,
        "default_mode": "code",
        "mode_writable_globs": {
            "code": ["**/*.py", "**/*.toml", "**/*.cfg"],
            "spec": ["**/*.md", "**/*.rst"]
        },
        "mode_extra_writable_globs": {
            "code": ["CMakeLists.txt", "**/*.cmake"]
        }
    }
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


_USER_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".embedagent")
_PROJECT_CONFIG_RELPATH = os.path.join(".embedagent", "config.json")


@dataclass
class AppConfig:
    # LLM 连接
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    timeout: Optional[float] = None
    # 上下文窗口
    max_context_tokens: Optional[int] = None
    reserve_output_tokens: Optional[int] = None
    chars_per_token: Optional[float] = None
    max_recent_turns: Optional[int] = None
    # 循环控制
    max_turns: Optional[int] = None
    default_mode: Optional[str] = None
    # 每个模式的可写路径 glob 覆盖
    mode_writable_globs: Dict[str, List[str]] = field(default_factory=dict)
    mode_extra_writable_globs: Dict[str, List[str]] = field(default_factory=dict)


def _load_json_file(path: str) -> dict:
    """Read a JSON file; return empty dict on any error."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (IOError, OSError, ValueError):
        return {}


def _merge(base: AppConfig, overrides: dict) -> AppConfig:
    """Apply overrides dict onto base, returning a new AppConfig."""
    simple_fields = (
        "base_url", "api_key", "model", "timeout",
        "max_context_tokens", "reserve_output_tokens",
        "chars_per_token", "max_recent_turns",
        "max_turns", "default_mode",
    )
    merged_globs = dict(base.mode_writable_globs)
    merged_extra_globs = dict(base.mode_extra_writable_globs)

    kwargs = {}
    for f in simple_fields:
        val = overrides.get(f)
        if val is not None:
            kwargs[f] = val
        else:
            kwargs[f] = getattr(base, f)

    globs_override = overrides.get("mode_writable_globs")
    if isinstance(globs_override, dict):
        for mode_name, globs in globs_override.items():
            if isinstance(globs, list):
                merged_globs[mode_name] = [str(g) for g in globs]
    kwargs["mode_writable_globs"] = merged_globs
    extra_globs_override = overrides.get("mode_extra_writable_globs")
    if isinstance(extra_globs_override, dict):
        for mode_name, globs in extra_globs_override.items():
            if isinstance(globs, list):
                merged_extra_globs[mode_name] = [str(g) for g in globs]
    kwargs["mode_extra_writable_globs"] = merged_extra_globs

    return AppConfig(**kwargs)


def load_config(workspace: str) -> AppConfig:
    """Load and merge user-level and project-level config files.

    Args:
        workspace: Absolute path to the project workspace directory.

    Returns:
        Merged AppConfig. Fields remain None when not set in any config file.
    """
    cfg = AppConfig()

    user_config_path = os.path.join(_USER_CONFIG_DIR, "config.json")
    if os.path.isfile(user_config_path):
        cfg = _merge(cfg, _load_json_file(user_config_path))

    project_config_path = os.path.join(workspace, _PROJECT_CONFIG_RELPATH)
    if os.path.isfile(project_config_path):
        cfg = _merge(cfg, _load_json_file(project_config_path))

    return cfg
