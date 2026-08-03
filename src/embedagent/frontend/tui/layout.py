from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit
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
        elif raw.startswith("alt+"):
            raw = "escape " + raw[4:]
        keys.extend(raw.split())
    return tuple(keys)


class TerminalLayout(object):
    # Layout ratios: main chat area dominates
    MAIN_AREA_RATIO = 0.75
    AUX_AREA_RATIO = 0.25

    def __init__(self, owner) -> None:
        self.owner = owner
        self._aux_panels_visible = False
        completer = TerminalCompleter(lambda: self.owner.state)
        self.header = TextArea(read_only=True, focusable=False, height=2)
        self.explorer = TextArea(
            read_only=True, focusable=True, width=32, scrollbar=True, wrap_lines=False
        )
        self.main = TextArea(read_only=True, focusable=True, scrollbar=True, wrap_lines=True)
        self.editor = TextArea(read_only=False, focusable=True, scrollbar=True, wrap_lines=False)
        self.inspector = TextArea(
            read_only=True, focusable=True, width=44, scrollbar=True, wrap_lines=True
        )
        self.command_palette = TextArea(
            read_only=True,
            focusable=True,
            width=72,
            height=16,
            scrollbar=True,
            wrap_lines=False,
        )
        self.composer = TextArea(
            multiline=False,
            prompt="user> ",
            height=1,
            completer=completer,
            complete_while_typing=True,
        )
        self.composer.accept_handler = self.owner.controller.accept_input
        try:
            self.editor.buffer.on_text_changed += self.owner.controller.on_editor_text_changed
        except (ValueError, TypeError):
            pass
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
        preview_container = ConditionalContainer(
            content=self.main,
            filter=Condition(lambda: self.owner.state.main_view != "editor"),
        )
        editor_container = ConditionalContainer(
            content=self.editor,
            filter=Condition(lambda: self.owner.state.main_view == "editor"),
        )
        header_window = Window(
            content=FormattedTextControl(text=lambda: self.header.text),
            height=2,
        )
        explorer_container = ConditionalContainer(
            content=self.explorer,
            filter=Condition(lambda: self._aux_panels_visible),
        )
        inspector_container = ConditionalContainer(
            content=self.inspector,
            filter=Condition(lambda: self._aux_panels_visible),
        )
        body = VSplit(
            [
                explorer_container,
                ConditionalContainer(
                    content=Window(width=1, char=self.owner.theme.vertical),
                    filter=Condition(lambda: self._aux_panels_visible),
                ),
                preview_container,
                editor_container,
                ConditionalContainer(
                    content=Window(width=1, char=self.owner.theme.vertical),
                    filter=Condition(lambda: self._aux_panels_visible),
                ),
                inspector_container,
            ]
        )
        base_layout_content = HSplit(
            [
                header_window,
                Window(height=1, char=self.owner.theme.horizontal),
                body,
                Window(height=1, char=self.owner.theme.horizontal),
                self.composer,
            ]
        )
        return Layout(
            FloatContainer(
                content=base_layout_content,
                floats=[
                    Float(
                        content=ConditionalContainer(
                            content=self.command_palette,
                            filter=Condition(
                                lambda: self.owner.state.workbench.command_palette.open
                            ),
                        ),
                        top=3,
                        left=8,
                    )
                ],
            )
        )

    def toggle_auxiliary_panels(self):
        """Toggle visibility of explorer and inspector panels."""
        self._aux_panels_visible = not self._aux_panels_visible
        self.application.invalidate()

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

        @bindings.add("c-s", filter=has_focus(self.editor))
        def _(event):
            self.owner.controller.save_editor()

        @bindings.add("c-up", filter=has_focus(self.explorer))
        def _(event):
            self.owner.controller.move_selection(-1)

        @bindings.add("c-down", filter=has_focus(self.explorer))
        def _(event):
            self.owner.controller.move_selection(1)

        @bindings.add("escape")
        def _(event):
            self.owner.controller.close_aux_view()

        @bindings.add(
            "escape",
            filter=Condition(lambda: self.owner.state.workbench.command_palette.open),
        )
        def _(event):
            self.owner.controller.close_command_palette()

        for descriptor in self.owner.state.workbench.keybindings:
            keys = _prompt_toolkit_keys(descriptor.keys)
            if not keys:
                continue

            def execute_registered_command(event, command_id=descriptor.command_id):
                self.owner.controller.execute_workbench_command(command_id)
                event.app.invalidate()

            bindings.add(*keys)(execute_registered_command)

        return bindings
