from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from embedagent_host import FrontendPortError
from embedagent_protocol import (
    FailureRecord,
    FrontendSessionPort,
    FrontendWorkspacePort,
    ShellDescriptor,
)

from embedagent.bundle_policy import load_current_bundle_policy
from embedagent.cli.options import CliOptions
from embedagent.cli.parser import build_parser
from embedagent.cli.renderer import write_result
from embedagent.cli.result import CliResult, write_failure
from embedagent.frontend.runtime import SessionClientRuntime
from embedagent.hosted import create_hosted_runtime, resolve_launch_config
from embedagent.product_catalog import (
    product_agent_application_registry,
    product_shell_compiler,
)


@dataclass(frozen=True)
class CliApplication(object):
    options: CliOptions
    launch_config: Any
    client_runtime: SessionClientRuntime
    session_port: FrontendSessionPort
    workspace_port: FrontendWorkspacePort
    shell_descriptor: ShellDescriptor

    @classmethod
    def from_options(cls, options: CliOptions) -> "CliApplication":
        if not isinstance(options, CliOptions):
            raise TypeError("options must be CliOptions")
        policy = load_current_bundle_policy(__file__)
        policy.require_shell("cli")
        launch_config = resolve_launch_config(
            options.launch.workspace,
            options.launch.to_overrides(),
        )
        client_runtime = SessionClientRuntime()
        try:
            hosted = create_hosted_runtime(launch_config, event_sink=client_runtime)
            client_runtime.bind_session_port(hosted.session)
            allowed_ids = policy.allowed_agent_application_ids if policy.bundled else None
            registry = product_agent_application_registry(allowed_ids)
            application = registry.record_by_id(launch_config.agent_application_id)
            capabilities = client_runtime.get_session_capabilities("")
            descriptor = product_shell_compiler()(
                application.application_id,
                capabilities.to_dict(),
            )
            if not isinstance(descriptor, ShellDescriptor):
                raise TypeError("shell compiler must return a ShellDescriptor")
            return cls(
                options=options,
                launch_config=launch_config,
                client_runtime=client_runtime,
                session_port=hosted.session,
                workspace_port=hosted.workspace,
                shell_descriptor=descriptor,
            )
        except Exception:
            client_runtime.close()
            raise

    def run(self) -> int:
        try:
            if self.options.command == "run":
                from embedagent.cli.run import run_command

                return int(run_command(self))
            if self.options.command == "sessions":
                from embedagent.cli.sessions import run_sessions_command

                return int(run_sessions_command(self))
            if self.options.command == "chat":
                from embedagent.cli.chat import run_chat_command

                return int(run_chat_command(self))
            raise ValueError("unsupported CLI command")
        finally:
            self.close()

    def close(self) -> None:
        self.client_runtime.close()


def _failure(code: str, source: str) -> FailureRecord:
    return FailureRecord(code=code, message="", retryable=False, source=source)


def main(argv: Optional[List[str]] = None) -> int:
    options = build_parser().parse_args(argv)
    try:
        return CliApplication.from_options(options).run()
    except FrontendPortError as exc:
        failure = exc.failure
    except ValueError:
        failure = _failure("configuration_error", "cli")
    except KeyboardInterrupt:
        failure = _failure("cancelled", "cli")
    except (ImportError, RuntimeError, TypeError):
        failure = _failure("runtime_error", "cli")
    if options.output == "json":
        return write_result(CliResult.from_failure("", failure), output="json")
    return write_failure(failure)
