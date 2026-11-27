"""Enforce ARCHITECTURE §1.1 dependency rules."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "netcore"

FORBIDDEN = {
    "domain": {
        "rich",
        "pandas",
        "numpy",
        "sqlite3",
        "textual",
        "netcore.application",
        "netcore.infrastructure",
        "netcore.tui",
    },
    "application": {
        "rich",
        "pandas",
        "numpy",
        "sqlite3",
        "textual",
        "netcore.infrastructure",
        "netcore.tui",
    },
    "tui": {
        "sqlite3",
        "pandas",
        "numpy",
        "textual",
        "netcore.infrastructure",
        "netcore.domain",
    },
}

GLOBAL_FORBIDDEN = {"socket", "subprocess", "textual", "pyside6"}


def modules() -> list[tuple[str, ast.Module, Path]]:
    """Parse every package module."""
    result = []
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC)
        name = "netcore." + ".".join(relative.with_suffix("").parts)
        if relative.name == "__init__.py":
            name = "netcore." + ".".join(relative.parent.parts)
        result.append((name, ast.parse(path.read_text(encoding="utf-8")), path))
    return result


def imports(tree: ast.Module) -> set[str]:
    """Collect absolute imported module names."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module)
    return found


def test_layer_import_rules() -> None:
    """Forbidden imports per layer."""
    violations: list[str] = []
    for name, tree, _path in modules():
        layer = name.split(".")[1] if name.count(".") >= 1 else ""
        forbidden = FORBIDDEN.get(layer, set())
        for imported in imports(tree):
            root = imported.split(".")[0]
            if root in GLOBAL_FORBIDDEN:
                violations.append(f"{name} imports {imported}")
            if any(
                imported == prefix or imported.startswith(prefix + ".")
                for prefix in forbidden
            ):
                violations.append(f"{name} imports {imported}")
    assert not violations, "\n".join(violations)


def test_no_shell_or_socket_usage() -> None:
    """No subprocess/os.system/raw sockets anywhere in src/netcore."""
    violations: list[str] = []
    for name, tree, _path in modules():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "os"
                and node.func.attr == "system"
            ):
                violations.append(f"{name} calls os.system")
    assert not violations, "\n".join(violations)


def test_every_layer_is_a_package() -> None:
    """All four layers exist with __init__.py."""
    for layer in ("domain", "application", "infrastructure", "tui"):
        assert (SRC / layer / "__init__.py").exists()
