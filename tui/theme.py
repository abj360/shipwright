#!/usr/bin/env python3
"""
theme.py --- brand color tokens carried over from the retired web view

Contains:
    Palette: color tokens one display mode renders with
    DARK: default palette, carried over from the web view's stylesheet
"""

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
