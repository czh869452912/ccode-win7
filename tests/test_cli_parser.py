import sys
from dataclasses import FrozenInstanceError

import pytest


def test_parser_returns_immutable_chat_options_and_preserves_unset_overrides(tmp_path):
    from embedagent.cli.options import CliOptions
    from embedagent.cli.parser import build_parser

    options = build_parser().parse_args(
        [
            "chat",
            "--workspace",
            str(tmp_path),
            "--resume",
            "latest",
            "--mode",
            "debug",
            "--approve-writes",
        ]
    )

    assert isinstance(options, CliOptions)
    assert options.command == "chat"
    assert options.resume == "latest"
    assert options.mode == "debug"
    assert options.launch.workspace == str(tmp_path.resolve())
    assert options.launch.approve_writes is True
    overrides = options.launch.to_overrides()
    assert overrides.model is None
    assert overrides.base_url is None
    assert overrides.api_key is None
    with pytest.raises(FrozenInstanceError):
        options.command = "run"


def test_parser_covers_run_and_every_session_management_command():
    from embedagent.cli.parser import build_parser

    parser = build_parser()
    run = parser.parse_args(["run", "--output", "json", "--resume", "s1", "fix it"])
    assert (run.command, run.task, run.output, run.resume) == ("run", "fix it", "json", "s1")

    listed = parser.parse_args(["sessions", "list", "--limit", "7", "--output", "json"])
    assert (listed.command, listed.sessions_action, listed.limit, listed.output) == (
        "sessions",
        "list",
        7,
        "json",
    )
    shown = parser.parse_args(["sessions", "show", "latest"])
    assert (shown.sessions_action, shown.reference) == ("show", "latest")
    renamed = parser.parse_args(["sessions", "rename", "s1", "New title"])
    assert (renamed.sessions_action, renamed.reference, renamed.title) == (
        "rename",
        "s1",
        "New title",
    )
    archived = parser.parse_args(["sessions", "archive", "s1"])
    assert (archived.sessions_action, archived.reference) == ("archive", "s1")
    forked = parser.parse_args(["sessions", "fork", "s1", "--title", "Branch"])
    assert (forked.sessions_action, forked.reference, forked.title) == (
        "fork",
        "s1",
        "Branch",
    )


@pytest.mark.parametrize(
    "argv",
    [
        ["hello"],
        ["--tui"],
        ["--gui"],
        ["--list-sessions"],
        ["run"],
        ["sessions"],
    ],
)
def test_parser_rejects_retired_or_incomplete_grammar(argv):
    from embedagent.cli.parser import build_parser

    with pytest.raises(SystemExit) as exc_info:
        build_parser().parse_args(argv)
    assert exc_info.value.code == 2


def test_main_returns_integer_without_calling_sys_exit(monkeypatch):
    import embedagent.cli.app as cli_app

    application = type("Application", (), {"run": lambda self: 17})()
    monkeypatch.setattr(
        cli_app.CliApplication,
        "from_options",
        classmethod(lambda cls, options: application),
    )
    monkeypatch.setattr(
        sys,
        "exit",
        lambda code=0: (_ for _ in ()).throw(AssertionError("sys.exit called")),
    )

    assert cli_app.main(["run", "hello"]) == 17


def test_main_prepares_standard_streams_before_parsing(monkeypatch):
    import embedagent.cli.app as cli_app

    calls = []
    application = type("Application", (), {"run": lambda self: 0})()

    class Parser(object):
        def parse_args(self, argv):
            calls.append(("parse", argv))
            return object()

    monkeypatch.setattr(cli_app, "prepare_cli_standard_streams", lambda: calls.append("prepare"))
    monkeypatch.setattr(cli_app, "build_parser", lambda: Parser())
    monkeypatch.setattr(
        cli_app.CliApplication,
        "from_options",
        classmethod(lambda cls, options: application),
    )

    assert cli_app.main(["run", "hello"]) == 0
    assert calls == ["prepare", ("parse", ["run", "hello"])]
