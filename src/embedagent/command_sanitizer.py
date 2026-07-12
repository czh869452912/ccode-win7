"""Product accessor for the Host-owned generic command sanitizer."""

from __future__ import annotations

from embedagent_host.runtime.command_sanitizer import CommandSanitizer

from embedagent.di_container import get_default_container


def get_command_sanitizer(fresh: bool = False) -> CommandSanitizer:
    """Return the product-composed sanitizer instance."""
    return get_default_container().resolve("command_sanitizer", fresh=fresh)


def _register_sanitizer_factory() -> None:
    get_default_container().register_factory(
        "command_sanitizer",
        lambda: CommandSanitizer(),
    )


_register_sanitizer_factory()
