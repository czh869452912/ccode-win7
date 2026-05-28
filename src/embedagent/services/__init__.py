from importlib import import_module

from embedagent.services.event_emitter import EventEmitter
from embedagent.services.session_lifecycle import SessionLifecycleManager
from embedagent.services.shadow_git import ShadowGitSnapshot
from embedagent.services.workspace_file_service import WorkspaceFileService

__all__ = [
    "EventEmitter",
    "HarnessStateSynchronizer",
    "SessionLifecycleManager",
    "ShadowGitSnapshot",
    "WorkspaceFileService",
]


def __getattr__(name):
    if name == "HarnessStateSynchronizer":
        module = import_module("embedagent.services.harness_state_synchronizer")
        return getattr(module, name)
    raise AttributeError("module %r has no attribute %r" % (__name__, name))
