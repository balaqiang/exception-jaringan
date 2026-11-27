# Skill — Rich View / Component

Use when building a `netcore.tui` view or component (DEC-016).

## Checklist

1. Read `docs/UI_SPEC.md` and the root handoff spec for palette and rhythm.
2. The view exposes `render(state) -> RenderableType`, `actions()`,
   `handle_key(key, state) -> bool`.
3. Only application DTOs enter the view. Never import `sqlite3`,
   `pandas`, `numpy` or `netcore.infrastructure`.
4. No outer box borders. Use `Table(box=None, expand=True)` and
   `Table.grid`; the only separator is the sidebar hairline.
5. Focus states must be visible without color alone (cursor glyph `▸`).
6. Empty data renders `—` / `0`, never `nan` or an exception.
7. Long work goes through the service layer on a worker thread; publish
   a toast via the app queue.
8. Add a headless render test:

```python
console = Console(width=120, height=36, record=True, force_terminal=False)
console.print(app.render())
assert "SQLite Inspector" in console.export_text()
```
