#!/usr/bin/env python3
"""
test_layout_snapshot.py --- pins the order and shape of the four regions

Contains:
    EXPECTED_ORDER: the widget types composed down the screen, in order
    _composed_order(): the widget types the app actually mounts, in order
    test_region_order_matches_the_snapshot(): composition order is unchanged
    test_header_sits_above_the_composer(): the header is drawn before the input
"""

import asyncio
from pathlib import Path

from tui.app import ShipwrightApp
from tui.screens.composer import Composer
from tui.screens.footer import FooterBar
from tui.screens.header import HeaderBar
from tui.screens.timeline import Timeline

EXPECTED_ORDER = ["HeaderBar", "Timeline", "Composer", "FooterBar"]


async def _composed_order(repo_path: Path) -> list[str]:
    """Reports the four regions in the order the app mounts them.

    Args:
        repo_path: Checkout the app is pointed at.

    Returns:
        order: Region class names, top to bottom.
    """
    app = ShipwrightApp(repo_path, provider="anthropic")
    async with app.run_test() as pilot:
        await pilot.pause()
        wanted = (HeaderBar, Timeline, Composer, FooterBar)
        found = [(app.query_one(w).region.y, type(app.query_one(w)).__name__) for w in wanted]
    return [name for _, name in sorted(found)]


def test_region_order_matches_the_snapshot(tmp_path: Path) -> None:
    """Asserts the four regions are laid out in the documented order."""
    assert asyncio.run(_composed_order(tmp_path)) == EXPECTED_ORDER


def test_header_sits_above_the_composer(tmp_path: Path) -> None:
    """Asserts the status bar is drawn above the instruction input."""
    order = asyncio.run(_composed_order(tmp_path))

    assert order.index("HeaderBar") < order.index("Composer")
