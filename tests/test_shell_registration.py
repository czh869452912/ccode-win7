import unittest

from embedagent_protocol import (
    CommandDescriptor,
    KeybindingDescriptor,
    SurfaceDescriptor,
)

from embedagent.frontend.shell import (
    CommandContribution,
    ShellContribution,
    ShellContributionRegistry,
    SurfaceContribution,
    compile_shell_descriptor,
)


def command(command_id, dispatch_kind, order, capability_id=""):
    availability = {"capability_id": capability_id} if capability_id else {}
    return CommandContribution(
        descriptor=CommandDescriptor(
            id=command_id,
            label=command_id,
            group="tests",
            dispatch={"kind": dispatch_kind},
            availability=availability,
        ),
        order=order,
    )


def surface(surface_id, renderer_key, order):
    return SurfaceContribution(
        descriptor=SurfaceDescriptor(
            id=surface_id,
            label=surface_id,
            placement="overlay",
            renderer_key=renderer_key,
        ),
        order=order,
    )


class ShellRegistrationTests(unittest.TestCase):
    def test_compiler_merges_generic_and_selected_application_records(self):
        registry = ShellContributionRegistry(
            generic=ShellContribution(
                commands=(command("session.new", "session.create", order=10),),
                surfaces=(surface("session.commands", "command_palette", order=10),),
            ),
            applications={
                "embedagent.default_c_cpp": ShellContribution(
                    commands=(
                        command(
                            "workflow.verify",
                            "session.command",
                            order=50,
                            capability_id="workflow.verify",
                        ),
                    )
                )
            },
        )

        descriptor = compile_shell_descriptor(
            registry,
            application_id="embedagent.default_c_cpp",
            session_capabilities={"commands": [{"id": "workflow.verify", "active": True}]},
        )

        self.assertEqual(
            [item.id for item in descriptor.commands],
            ["session.new", "workflow.verify"],
        )
        self.assertEqual([item.id for item in descriptor.surfaces], ["session.commands"])

    def test_compiler_filters_only_declared_dynamic_commands(self):
        registry = ShellContributionRegistry(
            generic=ShellContribution(
                commands=(command("session.new", "session.create", order=10),)
            ),
            applications={
                "tests.app": ShellContribution(
                    commands=(
                        command(
                            "workflow.verify",
                            "session.command",
                            order=20,
                            capability_id="workflow.verify",
                        ),
                    )
                )
            },
        )

        descriptor = registry.compile("tests.app", {"commands": []})

        self.assertEqual([item.id for item in descriptor.commands], ["session.new"])

    def test_compiler_rejects_duplicate_ids_and_ordering_keys(self):
        invalid_registries = (
            ShellContributionRegistry(
                generic=ShellContribution(
                    commands=(
                        command("session.new", "session.create", order=10),
                        command("session.new", "session.cancel", order=20),
                    )
                )
            ),
            ShellContributionRegistry(
                generic=ShellContribution(
                    surfaces=(
                        surface("commands", "command_palette", order=10),
                        surface("commands", "interaction", order=20),
                    )
                )
            ),
            ShellContributionRegistry(
                generic=ShellContribution(
                    commands=(
                        command("session.new", "session.create", order=10),
                        command("session.cancel", "session.cancel", order=10),
                    )
                )
            ),
        )
        for index, registry in enumerate(invalid_registries):
            with self.subTest(index=index):
                with self.assertRaises(ValueError):
                    registry.compile("", {})

    def test_compiler_rejects_unknown_renderer_and_dispatch(self):
        invalid_registries = (
            ShellContributionRegistry(
                generic=ShellContribution(surfaces=(surface("commands", "unknown", order=10),))
            ),
            ShellContributionRegistry(
                generic=ShellContribution(commands=(command("session.new", "unknown", order=10),))
            ),
        )
        for index, registry in enumerate(invalid_registries):
            with self.subTest(index=index):
                with self.assertRaises(ValueError):
                    registry.compile("", {})

    def test_compiler_rejects_dangling_keybinding_after_availability_filter(self):
        registry = ShellContributionRegistry(
            generic=ShellContribution(
                commands=(
                    command(
                        "workflow.verify",
                        "session.command",
                        order=10,
                        capability_id="workflow.verify",
                    ),
                ),
                keybindings=(
                    KeybindingDescriptor(
                        command_id="workflow.verify",
                        keys="ctrl+shift+v",
                    ),
                ),
            )
        )

        with self.assertRaisesRegex(ValueError, "unknown_keybinding_command:workflow.verify"):
            registry.compile("", {"commands": []})

    def test_compiler_rejects_unknown_application(self):
        registry = ShellContributionRegistry(applications={"tests.app": ShellContribution()})

        with self.assertRaisesRegex(ValueError, "unknown_shell_application:missing"):
            registry.compile("missing", {})


if __name__ == "__main__":
    unittest.main()
