#!/usr/bin/env python3
"""
capture_media.py --- records the interface into the images the README shows

Textual can export a screen as SVG; GitHub renders a still better as PNG and an
animation only as GIF. This reads that SVG back into a grid of coloured cells
and draws it with a monospace font, which keeps the real colours without
needing a browser or a screen recorder.

Usage:
    python scripts/capture_media.py wordmark docs/media/wordmark.png
    python scripts/capture_media.py session docs/media/session.gif --task "..."
    python scripts/capture_media.py approval docs/media/approval.png

Contains:
    CELL_WIDTH / CELL_HEIGHT: the SVG's own character cell, in points
    FONT_PATHS: monospace fonts to draw with, in order of preference
    Cell: one run of text at a column, in one colour
    class_colours(): reads the SVG stylesheet into class-to-colour
    parse_screen(): turns one exported SVG into rows of cells
    render(): draws rows of cells onto an image
    capture_wordmark(): the block-capital mark on its own, transparently
    capture_session(): a real run, frame by frame, as a GIF
    capture_approval(): the approval prompt on a proposed command
    main(): picks one of the above
"""

from __future__ import annotations

import argparse
import asyncio
import html
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.env_file import load_env_file  # noqa: E402
from agent.permissions import PermissionMode  # noqa: E402
from tui.app import ShipwrightApp  # noqa: E402
from tui.theme import BRAND_BLUE, DARK  # noqa: E402
from tui.widgets.approval_panel import ApprovalPanel  # noqa: E402
from tui.widgets.wordmark import PROJECT_NAME, render_word  # noqa: E402

CELL_WIDTH = 12.2
CELL_HEIGHT = 20.4
FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
)
FONT_SIZE = 17
PADDING = 12
# The mark is drawn larger than the recordings, with room around the letters.
MARK_PADDING = 10
MARK_FONT_SIZE = 54
BACKGROUND = "#000000"
DEFAULT_COLOUR = "#d4d4d4"
TEXT_PATTERN = re.compile(
    r'<text class="([^"]*)" x="([\d.]+)" y="([\d.]+)"[^>]*>(.*?)</text>', re.DOTALL
)
STYLE_PATTERN = re.compile(r"\.(terminal-[\w-]+)\s*\{([^}]*)\}")
FILL_PATTERN = re.compile(r"fill:\s*(#[0-9a-fA-F]{3,8})")


def _font(size: int = FONT_SIZE) -> ImageFont.FreeTypeFont:
    """Returns the monospace font the recordings are drawn with.

    Args:
        size: Point size to load it at.

    Returns:
        font: The first font on the list that this machine has.
    """
    for path in FONT_PATHS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise RuntimeError(f"no monospace font found; looked for {', '.join(FONT_PATHS)}")


@dataclass(frozen=True)
class Cell:
    """One run of text drawn at a column, in one colour.

    Attributes:
        column: Character column the run starts at.
        text: The characters themselves.
        colour: Colour the run is drawn in.
    """

    column: int
    text: str
    colour: str


def class_colours(svg: str) -> dict[str, str]:
    """Reads the exported stylesheet into a class-to-colour mapping.

    Args:
        svg: The exported SVG.

    Returns:
        colours: Colour for each terminal class that names one.
    """
    colours: dict[str, str] = {}
    for name, body in STYLE_PATTERN.findall(svg):
        fill = FILL_PATTERN.search(body)
        if fill:
            colours[name] = fill.group(1)
    return colours


def parse_screen(svg: str) -> list[list[Cell]]:
    """Turns one exported screen into rows of coloured cells.

    Args:
        svg: The exported SVG.

    Returns:
        rows: One list of runs per line, top to bottom.
    """
    colours = class_colours(svg)
    by_line: dict[float, list[Cell]] = {}
    for classes, x, y, body in TEXT_PATTERN.findall(svg):
        text = html.unescape(re.sub(r"<[^>]+>", "", body)).replace("\xa0", " ")
        if not text:
            continue
        colour = DEFAULT_COLOUR
        for name in classes.split():
            colour = colours.get(name, colour)
        by_line.setdefault(float(y), []).append(
            Cell(column=round(float(x) / CELL_WIDTH), text=text, colour=colour)
        )
    return [sorted(by_line[y], key=lambda cell: cell.column) for y in sorted(by_line)]


def render(rows: list[list[Cell]], size: tuple[int, int]) -> Image.Image:
    """Draws rows of cells onto an image.

    Args:
        rows: Rows of coloured runs, top to bottom.
        size: Terminal size in columns and lines.

    Returns:
        image: The drawn screen.
    """
    font = _font()
    advance = font.getlength("M")
    # The cell is exactly as tall as a full block, so block letters and box
    # borders join up instead of showing a seam between rows.
    block = font.getbbox("█")
    # One pixel of overlap, since the ink stops just short of the box and the
    # seam would otherwise show through every block letter and border.
    line_height = block[3] - block[1] - 1
    columns, lines = size
    image = Image.new(
        "RGB",
        (int(columns * advance) + PADDING * 2, lines * line_height + PADDING * 2),
        BACKGROUND,
    )
    canvas = ImageDraw.Draw(image)
    for row, cells in enumerate(rows):
        for cell in cells:
            canvas.text(
                (PADDING + cell.column * advance, PADDING + row * line_height - block[1]),
                cell.text,
                font=font,
                fill=cell.colour,
            )
    return image


async def _screen(app: ShipwrightApp, size: tuple[int, int]) -> Image.Image:
    """Renders whatever the app is showing right now.

    Args:
        app: The running application.
        size: Terminal size it is running at.

    Returns:
        image: The drawn screen.
    """
    return render(parse_screen(app.export_screenshot()), size)


def _workspace(path: Path) -> Path:
    """Builds the small checkout the recorded run works in.

    Args:
        path: Directory to build it in.

    Returns:
        workspace: The prepared directory.
    """
    path.mkdir(parents=True, exist_ok=True)
    (path / "pricing.py").write_text(
        "def apply_discount(price, pct):\n    return price * (1 - pct)\n"
    )
    return path


def capture_wordmark(out: Path) -> None:
    """Saves the block-capital mark alone, on a transparent background.

    No terminal around it and no canvas behind it, so it sits on whatever the
    page it is shown on happens to be.

    Args:
        out: File to write.
    """
    font = _font(MARK_FONT_SIZE)
    block = font.getbbox("█")
    advance = font.getlength("M")
    line_height = block[3] - block[1] - 1
    lines = render_word(PROJECT_NAME)
    image = Image.new(
        "RGBA",
        (
            round(len(lines[0]) * advance) + MARK_PADDING * 2,
            len(lines) * line_height + MARK_PADDING * 2,
        ),
        (0, 0, 0, 0),
    )
    canvas = ImageDraw.Draw(image)
    for row, line in enumerate(lines):
        canvas.text(
            (MARK_PADDING, MARK_PADDING + row * line_height - block[1]),
            line,
            font=font,
            fill=BRAND_BLUE,
        )
    bounds = image.getbbox()
    if bounds is not None:
        image = image.crop(
            (
                max(bounds[0] - MARK_PADDING, 0),
                max(bounds[1] - MARK_PADDING, 0),
                min(bounds[2] + MARK_PADDING, image.width),
                min(bounds[3] + MARK_PADDING, image.height),
            )
        )
    image.save(out)


async def capture_approval(out: Path, size: tuple[int, int]) -> None:
    """Saves the prompt that asks before a command runs.

    Args:
        out: File to write.
        size: Terminal size to record at.
    """
    app = ShipwrightApp(_workspace(out.parent / "_sample"), palette=DARK)
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        app.start_turn_for("run the tests for the pricing module")
        panel = ApprovalPanel("run_shell", {"command": "pytest -q tests/"}, palette=app.palette)
        app.show_approval_panel(panel)
        await pilot.pause()
        image = await _screen(app, size)
    image.save(out)


async def capture_session(out: Path, size: tuple[int, int], task: str, frames: int) -> None:
    """Records a real run as an animation.

    Args:
        out: File to write.
        size: Terminal size to record at.
        task: What to ask the agent to do.
        frames: How many frames to take.
    """
    workspace = _workspace(out.parent / "_sample")
    app = ShipwrightApp(workspace, permission_mode=PermissionMode.BYPASS, palette=DARK)
    shots: list[Image.Image] = []
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        shots.append(await _screen(app, size))
        for character in task:
            await pilot.press("space" if character == " " else character)
        shots.append(await _screen(app, size))
        await pilot.press("enter")
        for _ in range(frames):
            await pilot.pause()
            await asyncio.sleep(0.6)
            # Leaving the directory always asks, bypass or not. The recording
            # runs in a throwaway folder, so it answers for itself.
            for panel in app.query(ApprovalPanel):
                if not panel.is_answered:
                    panel.action_allow()
            shots.append(await _screen(app, size))
            turns = app.query_one("Timeline").turns  # type: ignore[attr-defined]
            if turns and turns[-1].is_finished:
                break
        await pilot.pause()
        shots.append(await _screen(app, size))
    shots[0].save(out, save_all=True, append_images=shots[1:], duration=900, loop=0, optimize=True)


def main(argv: list[str] | None = None) -> int:
    """Records one piece of media.

    Args:
        argv: Argument vector; defaults to sys.argv when None.

    Returns:
        exit_code: Zero once the file is written.
    """
    parser = argparse.ArgumentParser(description="Record the interface for the README")
    parser.add_argument("what", choices=("wordmark", "session", "approval"))
    parser.add_argument("out", type=Path)
    parser.add_argument("--task", default="add input validation to apply_discount in pricing.py")
    parser.add_argument("--columns", type=int, default=100)
    parser.add_argument("--lines", type=int, default=30)
    parser.add_argument("--frames", type=int, default=24)
    args = parser.parse_args(argv)

    load_env_file(Path.cwd())
    # The recording is always in colour, whatever the terminal running it says.
    os.environ["TERM"] = "xterm-256color"
    os.environ.setdefault("SHIPWRIGHT_SESSIONS_DIR", "/tmp/shipwright-capture-sessions")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    size = (args.columns, args.lines)
    if args.what == "wordmark":
        capture_wordmark(args.out)
    elif args.what == "approval":
        asyncio.run(capture_approval(args.out, size))
    else:
        asyncio.run(capture_session(args.out, size, args.task, args.frames))
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
