# KeroMDizer TUI — Design

**Date:** 2026-03-06
**Status:** Approved

## Summary

Add an interactive terminal UI for KeroMDizer using the bubbletea/lipgloss Python ports. The TUI covers the full import workflow (folder selection → provider → confirm → run) plus a Settings screen and a Review placeholder for future tagging support.

## Screen Map

```
MAIN ──→ FOLDER_BROWSER ──→ PROVIDER_SELECT ──→ CONFIRM ──→ RUN
  ├──→ SETTINGS
  └──→ REVIEW  (placeholder)
```

## Screens

### MAIN

Three menu items: `Import`, `Settings`, `Review`. Arrow keys / j/k to move, Enter to select, q to quit.

### FOLDER_BROWSER

Two modes in one screen.

**Browse mode** (default): Current path shown as header. Scrollable list of dirs and files in the current directory. Navigation: up/down arrows to move cursor, Enter to descend into a dir, Backspace to go up one level. When the desired folder is highlighted, Space or a second Enter selects it and advances to PROVIDER_SELECT. Esc returns to MAIN.

**Text mode** (press `/` to activate): An input bar appears at the bottom. Type or paste (Ctrl+V) a full path. Enter validates the path exists and advances. Esc returns to browse mode.

### PROVIDER_SELECT

Single SELECT field cycling through `Auto-detect / ChatGPT / DeepSeek`. When Auto is selected, shows the detected provider as a badge (e.g. `auto → deepseek`). Enter to confirm, Esc back to FOLDER_BROWSER.

### CONFIRM

Summary panel showing all selected options and the conversation count discovered by parsing:

```
Export folder:  ~/Downloads/deepseek_data-2026-03-06
Provider:       DeepSeek (auto-detected)
Output dir:     ./output
User name:      User
Assistant name: DeepSeek
Conversations:  263 found
```

`r` or Enter to run, Esc back to PROVIDER_SELECT.

### RUN

Live progress display. Background worker parses and writes files, sending `ProgressMsg` via `program.send()` per file written. Done summary (`Written: 263, Skipped: 0`) shown on completion. Enter or q to return to MAIN.

### SETTINGS

Form with three text inputs and one action button:

- **Output dir** — text input, default `./output`
- **User name** — text input, blank uses TOML or provider default
- **Assistant name** — text input, blank uses TOML or provider default
- **Save to ~/.keromdizer.toml** — button, persists user/assistant names

Tab/Shift-Tab between fields, Enter on the Save button writes the TOML, Esc back to MAIN.

### REVIEW *(placeholder)*

Static panel: "Coming soon — conversation tagging." Esc back to MAIN.

## Architecture

**New file:** `tui.py` — single file, ~600–800 lines, following the safaribooks `tui.py` pattern.

**Entry point:** `python tui.py` (separate from the CLI).

**Zero changes** to existing modules: `conversation_parser.py`, `deepseek_parser.py`, `parser_factory.py`, `renderer.py`, `file_manager.py`, `models.py`, `config.py`.

**Dependencies added** to `bootstrap.sh`: `charm-bubbletea`, `lipgloss` (pip install from git or PyPI).

## Reference Implementations

- `/home/matt/github/safaribooks/tui.py` — multi-screen TUI, background workers, Ctrl+V paste
- `/home/matt/github/KeroMDizer` (KeroGrid) — form fields, SELECT cycling, mouse hit-testing

## Background Worker

A daemon thread runs the full conversion pipeline:

```python
parser, provider = build_parser(folder, source)
conversations = parser.parse()
for conv in conversations:
    # write files
    program.send(ProgressMsg(written=n, skipped=m, total=total))
program.send(DoneMsg(written=n, skipped=m))
```

## Custom Messages

```python
@dataclass
class ProgressMsg(tea.Msg):
    written: int
    skipped: int
    total: int

@dataclass
class DoneMsg(tea.Msg):
    written: int
    skipped: int

@dataclass
class ConvCountMsg(tea.Msg):
    count: int      # sent after parse(), before file writes begin

@dataclass
class ClipboardMsg(tea.Msg):
    text: str
```

## Color Scheme

Catppuccin Mocha (via `lipgloss.themes.catppuccin`), matching safaribooks convention.

## Future / Out of Scope

- Conversation tagging (REVIEW screen — wired to #20 JSONL when ready)
- Per-conversation preview pane
- Keyboard shortcut help overlay
