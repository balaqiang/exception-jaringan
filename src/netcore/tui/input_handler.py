"""Cross-platform raw keyboard reader."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Literal

KeyKind = Literal[
    "UP",
    "DOWN",
    "LEFT",
    "RIGHT",
    "ENTER",
    "ESC",
    "TAB",
    "SHIFT_TAB",
    "BACKSPACE",
    "DELETE",
    "PAGE_UP",
    "PAGE_DOWN",
    "HOME",
    "END",
    "CTRL_B",
    "CTRL_C",
    "CTRL_P",
    "CTRL_S",
    "CHAR",
]

CONTROLS: dict[str, KeyKind] = {
    "\x02": "CTRL_B",
    "\x03": "CTRL_C",
    "\x10": "CTRL_P",
    "\x13": "CTRL_S",
    "\t": "TAB",
    "\r": "ENTER",
    "\n": "ENTER",
    "\x7f": "BACKSPACE",
    "\x08": "BACKSPACE",
}

CSI: dict[str, KeyKind] = {
    "A": "UP",
    "B": "DOWN",
    "C": "RIGHT",
    "D": "LEFT",
    "Z": "SHIFT_TAB",
    "H": "HOME",
    "F": "END",
}

CSI_TILDE: dict[str, KeyKind] = {
    "1~": "HOME",
    "2~": "DELETE",
    "3~": "DELETE",
    "4~": "END",
    "5~": "PAGE_UP",
    "6~": "PAGE_DOWN",
}

WINDOWS_KEYS: dict[str, KeyKind] = {
    "H": "UP",
    "P": "DOWN",
    "M": "RIGHT",
    "K": "LEFT",
    "G": "HOME",
    "O": "END",
    "I": "PAGE_UP",
    "Q": "PAGE_DOWN",
    "S": "DELETE",
}


@dataclass(frozen=True, slots=True)
class KeyEvent:
    """A parsed key press."""

    kind: KeyKind
    char: str = ""


def parse_bytes(data: bytes | str) -> KeyEvent | None:
    """Parse a raw input chunk into a KeyEvent."""
    text = data.decode("utf-8", "ignore") if isinstance(data, bytes) else data
    if not text:
        return None
    if text in CONTROLS:
        return KeyEvent(CONTROLS[text])
    if text.startswith("\x1b["):
        sequence = text[2:]
        if sequence in CSI:
            return KeyEvent(CSI[sequence])
        if sequence in CSI_TILDE:
            return KeyEvent(CSI_TILDE[sequence])
        if sequence.endswith("~") and sequence[:-1] in CSI_TILDE:
            return KeyEvent(CSI_TILDE[sequence[:-1]])
        return None
    if text in {"\x1b", "\x1bO"}:
        return KeyEvent("ESC")
    if text.startswith("\x1bO") and len(text) >= 3:
        return KeyEvent(CSI.get(text[2], "ESC"))
    if text.startswith("\x1b"):
        return KeyEvent("ESC")
    if text.isprintable():
        return KeyEvent("CHAR", text[0])
    return None


class RawKeyboardReader:
    """Context manager putting stdin in cbreak mode."""

    def __enter__(self) -> RawKeyboardReader:
        self._fd = -1
        self._old_settings: Any = None
        self._buffer = ""
        if os.name != "nt" and sys.stdin.isatty():
            import termios
            import tty

            self._fd = sys.stdin.fileno()
            self._old_settings = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
        return self

    def __exit__(self, *_: object) -> None:
        if os.name != "nt" and self._old_settings is not None:
            import termios

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)
            self._old_settings = None

    def read_key(self, timeout_s: float = 0.05) -> KeyEvent | None:
        """Return the next key or None after ``timeout_s``."""
        if os.name == "nt":
            return self._read_windows(timeout_s)
        return self._read_posix(timeout_s)

    def _read_posix(self, timeout_s: float) -> KeyEvent | None:
        import select

        if self._fd < 0:
            return None
        ready, _, _ = select.select([self._fd], [], [], timeout_s)
        if not ready:
            return None
        try:
            data = os.read(self._fd, 32)
        except OSError:
            return None
        if not data:
            return None
        self._buffer += data.decode("utf-8", "ignore")
        if self._buffer == "\x1b":
            # Distinguish a lone ESC from the start of a CSI sequence.
            ready, _, _ = select.select([self._fd], [], [], 0.01)
            if not ready:
                self._buffer = ""
                return KeyEvent("ESC")
            self._buffer += os.read(self._fd, 32).decode("utf-8", "ignore")
        chunk, self._buffer = self._buffer, ""
        return parse_bytes(chunk)

    def _read_windows(self, timeout_s: float) -> KeyEvent | None:
        import msvcrt
        import time

        kbhit = getattr(msvcrt, "kbhit", None)
        getwch = getattr(msvcrt, "getwch", None)
        if kbhit is None or getwch is None:
            return None
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if kbhit():
                char = getwch()
                if char in {"\x00", "\xe0"}:
                    code = getwch()
                    return KeyEvent(WINDOWS_KEYS.get(code, "ESC"))
                return parse_bytes(char)
            time.sleep(0.005)
        return None
