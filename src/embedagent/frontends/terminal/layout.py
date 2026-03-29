from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit
from prompt_toolkit.layout.containers import ConditionalContainer, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea

from embedagent.frontends.terminal.completion import TerminalCompleter


class TerminalLayout(object):
    def __init__(self, owner) -> None:
        self.owner = owner
        completer = TerminalCompleter(lambda: self.owner.state)
        self.header = TextArea(read_only=True, focusable=False, height=2)
        self.explorer = TextArea(read_only=True, focusable=True, width=32, scrollbar=True, wrap_lines=False)
        self.main = TextArea(read_only=True, focusable=True, scrollbar=True, wrap_lines=True)
        self.editor = TextArea(read_only=False, focusable=True, scrollbar=True, wrap_lines=False)
        self.inspector = TextArea(read_only=True, focusable=True, width=44, scrollbar=True, wrap_lines=True)
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
        except Exception:
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
        body = VSplit(
            [
                self.explorer,
                Window(width=1, char=self.owner.theme.vertical),
                preview_container,
                editor_container,
                Window(width=1, char=self.owner.theme.vertical),
                self.inspector,
            ]
        )
        return Layout(
            HSplit(
                [
                    header_window,
                    Window(height=1, char=self.owner.theme.horizontal),
                    body,
                    Window(height=1, char=self.owner.theme.horizontal),
                    self.composer,
                ]
            )
        )

    def _build_key_bindings(self):
        bindings = KeyBindings()

        @bindings.add("c-c")
        @bindings.add("c-q")
        def _(event):
            event.app.exit()

        @bindings.add("tab")
        def _(event):
            event.app.layout.focus_next()

        @bindings.add("s-tab")
        def _(event):
            event.app.layout.focus_previous()

        @bindings.add("f1")
        def _(event):
            self.owner.controller.show_help()

        @bindings.add("f2")
        def _(event):
            self.owner.controller.create_new_session()

        @bindings.add("f3")
        def _(event):
            self.owner.controller.resume_latest_session()

        @bindings.add("f4")
        def _(event):
            self.owner.controller.show_sessions_explorer()

        @bindings.add("f5")
        def _(event):
            self.owner.controller.activate_selection()

        @bindings.add("f6")
        def _(event):
            self.owner.controller.show_snapshot()

        @bindings.add("f7")
        def _(event):
            self.owner.controller.open_selected_preview()

        @bindings.add("f8")
        def _(event):
            self.owner.controller.edit_selected_item()

        @bindings.add("f9")
        def _(event):
            self.owner.controller.show_artifacts()

        @bindings.add("f10")
        def _(event):
            self.owner.controller.toggle_follow_output()

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

        return bindings
