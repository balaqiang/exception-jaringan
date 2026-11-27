"""View protocol and shared helpers."""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.text import Text

from netcore.tui.input_handler import KeyEvent
from netcore.tui.state import Action, AppState


@dataclass(frozen=True, slots=True)
class ViewContent:
    """What a view contributes below the status strip."""

    metrics: tuple[tuple[str, str, str], ...]
    section: str
    body: RenderableType
    hint: str = ""


class BaseView:
    """Base class for all screens."""

    id = "base"
    title = "NetCore"
    subtitle = ""

    def actions(self, state: AppState) -> tuple[Action, ...]:
        """Action-bar buttons for this view."""
        return ()

    def build(self, state: AppState) -> ViewContent:
        """Render metrics and content."""
        return ViewContent(
            metrics=(),
            section=self.title,
            body=Text("No data", style="#6b7280"),
        )

    def handle_key(self, key: KeyEvent, state: AppState) -> bool:
        """Handle content-zone keys; return True when state changed."""
        return False

    def selected(self, state: AppState) -> int:
        """Cursor index for the primary list."""
        return state.cursor(self.id, len(state.data.get(self.id, ()) or ()))

    def empty(self, hint: str) -> ViewContent:
        """Standard empty state."""
        return ViewContent(
            metrics=(),
            section=self.title,
            body=Text(f"  {hint}", style="#6b7280"),
            hint=hint,
        )
