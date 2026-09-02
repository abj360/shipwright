#!/usr/bin/env python3
"""
theme.py --- brand color tokens carried over from the retired web view

Contains:
    Palette: color tokens one display mode renders with
    DARK: default palette, carried over from the web view's stylesheet
    MONOCHROME: fallback palette for terminals that cannot show colour
    COLORLESS_TERMS: TERM values that mean "no colour available"
    supports_color(): decides whether a terminal should be sent colour
    palette_for(): picks the palette a terminal should render with
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    """Holds the color tokens a display mode renders with.

    Attributes:
        background: Canvas color behind every region.
        foreground: Default text color.
        accent: Highlight color for focused and active elements.
        add: Color for added diff lines.
        delete: Color for removed diff lines.
        hunk: Muted color for hunk headers and secondary text.
        status_error: Color marking a failed step.
        panel_background: Fill behind a bordered panel.
        panel_border: Border color of a panel.
        border_subtle: Border color for low-emphasis separators.
    """

    background: str
    foreground: str
    accent: str
    add: str
    delete: str
    hunk: str
    status_error: str
    panel_background: str
    panel_border: str
    border_subtle: str


DARK = Palette(
    background="#0d1117",
    foreground="#c9d1d9",
    accent="#6cb6ff",
    add="#2ea043",
    delete="#f85149",
    hunk="#8b949e",
    status_error="#f85149",
    panel_background="#161b22",
    panel_border="#21262d",
    border_subtle="#30363d",
)


MONOCHROME = Palette(
    background="",
    foreground="",
    accent="",
    add="",
    delete="",
    hunk="",
    status_error="",
    panel_background="",
    panel_border="",
    border_subtle="",
)
COLORLESS_TERMS = frozenset({"", "dumb", "unknown"})


def supports_color(environ: Mapping[str, str] | None = None) -> bool:
    """Decides whether this terminal should be sent colour at all.

    Honours the NO_COLOR convention first, then falls back to TERM, so a
    terminal that cannot render colour is never sent escape codes.

    Args:
        environ: Environment to inspect; defaults to the process environment.

    Returns:
        supports_color: True when colour output is appropriate.
    """
    source: Mapping[str, str] = os.environ if environ is None else environ
    if source.get("NO_COLOR") is not None:
        return False
    return source.get("TERM", "").strip().lower() not in COLORLESS_TERMS


def palette_for(environ: Mapping[str, str] | None = None) -> Palette:
    """Picks the palette this terminal should render with.

    Args:
        environ: Environment to inspect; defaults to the process environment.

    Returns:
        palette: DARK when colour is available, MONOCHROME otherwise.
    """
    return DARK if supports_color(environ) else MONOCHROME
