#!/usr/bin/env python3
"""
theme.py --- brand color tokens carried over from the retired web view

Contains:
    Palette: color tokens one display mode renders with
    BRAND_BLUE: the single blue the project wordmark is drawn in
    DARK: default palette, carried over from the web view's stylesheet
    MONOCHROME: fallback palette for terminals that cannot show colour
    COLORLESS_TERMS: TERM values that mean "no colour available"
    _term_name(): normalizes the TERM value for comparison
    supports_color(): decides whether a terminal should be sent colour
    palette_for(): picks the palette a terminal should render with
    CSS_VARIABLE_NAMES: which Textual design token each palette field feeds
    css_variables(): renders a palette as Textual design tokens
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


# Sampled from docs/media/wordmark.png, and the same blue the README badges use.
BRAND_BLUE = "#2f81f7"

DARK = Palette(
    background="#000000",
    foreground="#d4d4d4",
    accent=BRAND_BLUE,
    add="#2ea043",
    delete="#f85149",
    hunk="#8b949e",
    status_error="#f85149",
    panel_background="#0a0a0a",
    panel_border=BRAND_BLUE,
    border_subtle="#1c4f8f",
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


def _term_name(environ: Mapping[str, str]) -> str:
    """Normalizes the reported TERM value for comparison.

    Args:
        environ: Environment carrying the TERM variable.

    Returns:
        term: Lowercased TERM value with surrounding whitespace removed.
    """
    return environ.get("TERM", "").strip().lower()


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
    return _term_name(source) not in COLORLESS_TERMS


def palette_for(environ: Mapping[str, str] | None = None) -> Palette:
    """Picks the palette this terminal should render with.

    Args:
        environ: Environment to inspect; defaults to the process environment.

    Returns:
        palette: DARK when colour is available, MONOCHROME otherwise.
    """
    return DARK if supports_color(environ) else MONOCHROME


# Textual resolves widget CSS against these design tokens, so feeding the palette
# through them themes every widget at once instead of per-widget colour literals.
CSS_VARIABLE_NAMES: dict[str, str] = {
    "background": "background",
    "surface": "panel_background",
    "panel": "panel_background",
    "text": "foreground",
    "accent": "accent",
    "success": "add",
    "error": "status_error",
    "warning": "hunk",
    "panel-border": "panel_border",
    "border-subtle": "border_subtle",
}


def css_variables(palette: Palette) -> dict[str, str]:
    """Renders a palette as the Textual design tokens widgets resolve against.

    Fields that are blank are omitted rather than emitted empty, so a
    monochrome terminal falls back to Textual's own defaults instead of being
    handed unusable values.

    Args:
        palette: Palette to translate into design tokens.

    Returns:
        variables: Token name to colour, omitting anything the palette leaves blank.
    """
    rendered: dict[str, str] = {}
    for token, field_name in CSS_VARIABLE_NAMES.items():
        value = str(getattr(palette, field_name))
        if value:
            rendered[token] = value
    return rendered
