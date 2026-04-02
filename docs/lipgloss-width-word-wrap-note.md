# lipgloss `width()` — Word-Wrap Behaviour with Long Unbreakable Strings

**Date:** 2026-03-06
**Observed in:** KeroMDizer TUI (`tui.py`) folder browser screen
**Library:** `tbdtechpro/lipgloss` (Python port)

## Behaviour

`Style.width(n)` sets a minimum column width and applies **word-wrap** to content longer than `n - pad_left - pad_right` columns. From `style.py`:

```python
if not inline and width_ > 0:
    wrap_at = width_ - pad_left - pad_right
    if wrap_at > 0:
        str_ = _word_wrap(str_, wrap_at)
```

Word-wrap only breaks on whitespace/word boundaries. Strings with no spaces (e.g. long hash filenames like `27acb0fd...2026-01-14-04-16-34-d9369f62a9184a8b86ce547d614186fb/`) are treated as a single word and are **not wrapped** — they overflow the panel boundary.

## Contrast: `max_width(n)`

`Style.max_width(n)` truncates per-line with full ANSI awareness:

```python
if max_width > 0:
    str_ = "\n".join(_truncate_ansi(line, max_width) for line in lines)
```

This is the correct primitive for hard-capping line length. It is not applied automatically by `width()`.

## Potential Enhancement Request

The Go lipgloss library similarly does not force-break long words — this is consistent with the port. However, an optional `break_long_words=True` parameter on `width()` (similar to Python's `textwrap.wrap(break_long_words=True)`) would make it easier to safely display arbitrary filesystem paths and user-supplied strings in fixed-width panels without requiring the caller to pre-truncate.

## Workaround (applied in KeroMDizer)

Pre-truncate strings in application code before passing to lipgloss:

```python
max_label = w - 10  # panel width minus border/padding/cursor prefix
label = label[:max_label] + '…' if len(label) > max_label else label
```

Or apply `max_width` on the row style itself:

```python
row_style.max_width(w - 8).render(f'  ▶  {label}')
```

Both approaches work. The `max_width` approach is more composable since it lets lipgloss handle ANSI escape accounting.
