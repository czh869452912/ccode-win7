from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout
from prompt_toolkit.layout.containers import ConditionalContainer, Float, FloatContainer, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea

from embedagent.frontend.tui.completion import TerminalCompleter


def _prompt_toolkit_keys(value):
    keys = []
    for raw in str(value or "").strip().lower().split():
        if raw.startswith("ctrl+"):
            raw = "c-" + raw[5:]
        elif raw.startswith("shift+"):
            raw = "s-" + raw[6:]
        keys.extend(raw.split())
    return tuple(keys)


class TerminalLayout(object):
    core_region_ids = ("header", "timeline", "composer", "status")

    def __init__(self, owner) -> None:
        self.owner = owner
        self.secondary_region_ids = tuple(owner.state.contributions)
        completer = TerminalCompleter(lambda: self.owner.state)
        self.header = TextArea(read_only=True, focusable=False, height=2)
        self.main = TextArea(read_only=True, focusable=True, scrollbar=True, wrap_lines=True)
        self.composer = TextArea(
            multiline=False,
            prompt="user> ",
            height=1,
            completer=completer,
            complete_while_typing=True,
        )
        self.status = TextArea(read_only=True, focusable=False, height=1)
        self.command_palette = TextArea(
            read_only=True,
            focusable=True,
            width=72,
            height=16,
            scrollbar=True,
            wrap_lines=False,
        )
        self.contribution = TextArea(
            read_only=True,
            focusable=True,
            width=72,
            height=20,
            scrollbar=True,
            wrap_lines=False,
        )
        self.composer.accept_handler = self.owner.controller.accept_input
        self.application = self._create_application()

    def _create_application(self):
        kwargs = {
            "layout": self._build_layout(),
            "key_bindings": self._build_key_bindings(),
            "full_screen": not self.owner.headless,
            "mouse_support": self.owner.state.capability.allow_mouse,
        }
        if self.owner.headless:
            kwargs["input"] = self.owner.pipe_input
            kwargs["output"] = self.owner.dummy_output
        return Application(**kwargs)

    def _build_layout(self):
        content = HSplit(
            [
                Window(content=FormattedTextControl(text=lambda: self.header.text), height=2),
                Window(height=1, char=self.owner.theme.horizontal),
                self.main,
                Window(height=1, char=self.owner.theme.horizontal),
                self.composer,
                self.status,
            ]
        )
        return Layout(
            FloatContainer(
                content=content,
                floats=[
                    Float(
                        content=ConditionalContainer(
                            content=self.command_palette,
                            filter=Condition(lambda: self.owner.state.shell.command_palette.open),
                        ),
                        top=3,
                        left=4,
                    ),
                    Float(
                        content=ConditionalContainer(
                            content=self.contribution,
                            filter=Condition(self._contribution_open),
                        ),
                        top=3,
                        left=4,
                    ),
                ],
            )
        )

    def _contribution_open(self):
        active_id = self.owner.state.overlay.active_id
        return active_id in self.owner.state.contributions

    def _build_key_bindings(self):
        bindings = KeyBindings()

        @bindings.add("c-q")
        def _(event):
            event.app.exit()

        @bindings.add("tab")
        def _(event):
            event.app.layout.focus_next()

        @bindings.add("s-tab")
        def _(event):
            event.app.layout.focus_previous()

        @bindings.add("escape")
        def _(event):
            self.owner.controller.close_overlay()

        for descriptor in self.owner.state.shell.keybindings:
            command = next(
                (
                    item
                    for item in self.owner.shell_descriptor.commands
                    if item.id == descriptor.command_id
                ),
                None,
            )
            if command is not None:
                from embedagent.frontend.runtime.commands import is_command_available

                if not is_command_available(command, self.owner.controller._availability()):
                    continue
            keys = _prompt_toolkit_keys(descriptor.keys)
            if not keys:
                continue

            def execute_registered_command(event, command_id=descriptor.command_id):
                self.owner.controller.execute_shell_command(command_id)
                event.app.invalidate()

            bindings.add(*keys)(execute_registered_command)

        return bindings
