"""Responsive Rich layout tree."""

from __future__ import annotations

from rich.align import Align
from rich.console import RenderableType
from rich.layout import Layout
from rich.padding import Padding
from rich.text import Text

MIN_WIDTH = 100
MIN_HEIGHT = 30
SIDEBAR_WIDTH = 24
TOAST_WIDTH = 34
COLLAPSE_WIDTH = 110


def too_small(width: int, height: int) -> RenderableType:
    """Centred guard shown below 100x30."""
    message = Text()
    message.append("Terminal too small\n", style="bold #f5a623")
    message.append(
        f"need {MIN_WIDTH}x{MIN_HEIGHT}, current {width}x{height}\n",
        style="#9ca3af",
    )
    message.append("Resize the window or press q to quit.", style="#6b7280")
    return Align.center(message, vertical="middle")


def build_root(
    header: RenderableType,
    workspace: RenderableType,
    footer: RenderableType,
) -> Layout:
    """Compose header / workspace / footer."""
    root = Layout(name="root")
    root.split_column(
        Layout(header, name="header", size=1),
        Layout(workspace, name="body", ratio=1),
        Layout(footer, name="footer", size=1),
    )
    return root


def build_body(
    sidebar: RenderableType,
    divider: RenderableType,
    workspace: RenderableType,
    *,
    show_sidebar: bool,
) -> Layout:
    """Compose sidebar / hairline / workspace."""
    body = Layout(name="body")
    if show_sidebar:
        body.split_row(
            Layout(sidebar, name="sidebar", size=SIDEBAR_WIDTH),
            Layout(divider, name="divider", size=1),
            Layout(workspace, name="workspace", ratio=1),
        )
    else:
        body.update(workspace)
    return body


def pad_workspace(content: RenderableType) -> RenderableType:
    """Two-column breathing room inside the workspace."""
    return Padding(content, (0, 2, 0, 2))


def divider_text(height: int) -> Text:
    """A hairline vertical rule that fills the body height."""
    lines = "\n".join("│" for _ in range(max(1, height)))
    return Text(lines, style="#232732")
