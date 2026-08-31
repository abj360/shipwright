#!/usr/bin/env python3
"""
test_footer.py --- covers the generated keybinding hint bar

Contains:
    _binding(): builds one visible binding
    test_hints_render_key_and_description(): each hint names its key
    test_hidden_bindings_are_skipped(): an internal key never reaches the bar
    test_no_bindings_render_empty(): an unbound app shows an empty bar
"""

from textual.binding import Binding

from tui.screens.footer import format_hints


def _binding(key: str, description: str, show: bool = True) -> Binding:
    """Builds one binding for the hint bar to render.

    Args:
        key: Key the binding is bound to.
        description: Wording shown beside the key.
        show: Whether the binding is user-visible.

    Returns:
        binding: Binding ready to hand to format_hints.
    """
    return Binding(key, "noop", description, show=show)


def test_hints_render_key_and_description() -> None:
    """Asserts each rendered hint names both its key and what it does."""
    line = format_hints([_binding("ctrl+c", "Quit")])

    assert "ctrl+c Quit" in line


def test_hidden_bindings_are_skipped() -> None:
    """Asserts a binding marked hidden never appears on the bar."""
    line = format_hints([_binding("f12", "Debug", show=False)])

    assert "Debug" not in line


def test_no_bindings_render_empty() -> None:
    """Asserts an app with nothing bound renders an empty hint bar."""
    assert format_hints([]) == ""
