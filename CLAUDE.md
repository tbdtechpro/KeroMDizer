# KeroMDizer

Converts ChatGPT data export folders into GitHub-Flavored Markdown (GFM) files — one `.md` file per conversation branch. Pure Python stdlib, no external runtime dependencies.

## Quick Start

```bash
bash bootstrap.sh          # First time: installs deps, creates venv, runs tests
source .venv/bin/activate  # Activate venv every session
python keromdizer.py /path/to/chatgpt-export/ --output ./output
```

## Commands

```bash
# Run (basic)
python keromdizer.py /path/to/export/

# Run with explicit output dir
python keromdizer.py /path/to/export/ --output ~/notes/chatgpt

# Preview without writing files
python keromdizer.py /path/to/export/ --dry-run

# Custom speaker labels (CLI override)
python keromdizer.py /path/to/export/ --user-name Matt --assistant-name ChatGPT

# Or set defaults in ~/.keromdizer.toml:
# [user]
# name = "Matt"
# [providers.chatgpt]
# assistant_name = "ChatGPT"

# Tests
pytest tests/ -v

# Single test file
pytest tests/test_parser.py -v

# Single test
pytest tests/test_parser.py::test_trace_to_root_simple -v
```

## Architecture

```
keromdizer.py          ← CLI entrypoint (argparse, thin wiring layer only)
├── conversation_parser.py  ← Reads conversations.json, reconstructs branches
├── renderer.py             ← Converts parsed data to GFM markdown strings
├── file_manager.py         ← Filenames, deduplication, image copying
└── models.py               ← Message, Branch, Conversation dataclasses
```

**Data flow:** `ConversationParser.parse()` → `list[Conversation]` → per branch: `MarkdownRenderer.render()` → string → `FileManager.write()`

## Key Files

| File | Purpose |
|---|---|
| `keromdizer.py` | CLI entry point — run this |
| `conversation_parser.py` | All ChatGPT export parsing logic |
| `renderer.py` | GFM markdown generation |
| `file_manager.py` | File I/O, manifest, asset copying |
| `models.py` | Dataclasses: `Message`, `Branch`, `Conversation` |
| `config.py` | Persona config loading — reads `~/.keromdizer.toml`, resolves display names |
| `conftest.py` | Adds project root to `sys.path` for pytest |
| `tests/fixtures/sample_conversations.json` | Minimal test fixture (3 conversations) |
| `output/manifest.json` | Tracks written files for deduplication (auto-generated) |

## ChatGPT Export Format — Critical Gotchas

The export is a **tree**, not a flat list. Key facts:

- `conversations.json` is a JSON array of conversation objects
- Each conversation has a `mapping` dict — a node graph where every node has `id`, `parent`, `children`, `message`
- Conversations support **branching** (when you edit a message and regenerate). The `current_node` field points to the active leaf; alternate branches exist as other leaf nodes
- `ConversationParser._find_leaf_ids()` finds all leaves (nodes with empty `children`), then `_trace_to_root()` walks each back to reconstruct every branch path
- Branch 1 is always the main thread (path containing `current_node`)

**Content type filtering** — only these are included in output:
- `text` — standard messages (may contain markdown code fences inline)
- `multimodal_text` — messages with user-uploaded images

**Skipped content types:** `thoughts`, `code` (tool calls), `reasoning_recap`, `execution_output`, `tether_browsing_display`

**Skipped roles:** `system`, `tool` — only `user` and `assistant` appear in output

**Image references:** User images use `sediment://file_xxx` URIs. The actual files in the export folder have the format `file_xxx-sanitized.jpg` (prefix match via glob). Some images use `file-service://` URIs — these are NOT included in the export archive and will produce "image not found" warnings. This is normal.

## Output Format

Each `.md` file starts with a metadata table, then a `# Title` heading, then alternating `### 👤 User` / `### 🤖 Assistant` sections separated by `---`:

```markdown
| Field | Value |
|---|---|
| Date | 2026-01-14 |
| Model | gpt-4o |
| Conversation ID | abc-123 |
| Branch | 2 of 3 |        ← only present when conversation has branches

# Conversation Title

---

### 👤 User

User message text...

---

### 🤖 Assistant

Assistant response (code fences preserved verbatim)...

---
```

**Output directory structure:**
```
output/
├── manifest.json                          ← deduplication index
├── assets/                                ← copied images
│   └── file_abc123-sanitized.jpeg
├── 2026-01-14_Conversation_Title.md       ← branch 1 (no suffix)
└── 2026-01-14_Conversation_Title_branch-2.md
```

## Deduplication

`FileManager` maintains `output/manifest.json` keyed by `conversation_id`. On each run it compares `update_time` — conversations are re-exported only if newer. This makes it safe to run against multiple export snapshots into the same output directory.

`_used_filenames` is seeded from the manifest at startup to prevent cross-run filename collisions when two conversations share the same title.

## Persona Config

Speaker labels in rendered markdown can be customized via `~/.keromdizer.toml`:

```toml
[user]
name = "Matt"

[providers.chatgpt]
assistant_name = "ChatGPT"

[providers.deepseek]
assistant_name = "DeepSeek"
```

Both sections are optional. CLI flags `--user-name` and `--assistant-name` override the file for a single run. Fallback chain: CLI flag → TOML file → provider default (ChatGPT/DeepSeek) → "User"/"Assistant".

## Filename Sanitization

`FileManager.sanitize_filename()` replaces these characters with `_`: `<>:"/\|?*`, control chars (0x00–0x1f), middle dot `·`, bullet `•`, curly quotes `''`. Multiple consecutive underscores/spaces are collapsed. Titles truncate at 80 characters; full title is preserved in the metadata table.

ChatGPT titles frequently contain `·` (middle dot, U+00B7) — e.g., `"Branch · Casper Setup"` — which is why it's in the sanitize regex.

## Testing

Tests live in `tests/`. The `conftest.py` at the project root adds `.` to `sys.path` so bare `pytest` works (no need for `python -m pytest`).

```bash
pytest tests/ -v          # all tests
pytest tests/test_parser.py -v    # parser only
pytest tests/test_renderer.py -v  # renderer only
pytest tests/test_file_manager.py -v  # file manager only
```

Tests use `tmp_path` (pytest built-in) extensively — each test gets its own isolated temp dir, no cleanup needed.

The test fixture (`tests/fixtures/sample_conversations.json`) covers:
- A branched conversation (2 branches off the same node)
- A multimodal message with an `image_asset_pointer`
- An empty conversation with a null message (should be skipped)

## Python Version

Requires **Python 3.11+** — uses `X | Y` union type syntax, `list[str]` generics, and `tomllib` (stdlib). Ubuntu 24.04 ships Python 3.12 by default. `bootstrap.sh` handles installation if needed.

## Future Extension Points

The three-class architecture is designed to support a TUI layer without changes:

- **TUI:** Instantiate `ConversationParser`, `MarkdownRenderer`, `FileManager` directly — they're pure classes, not coupled to argparse
- **DeepSeek support:** Subclass `ConversationParser`, override `_parse_conversation` — the schema is similar
- **Additional content types:** Expand `_extract_messages` content_type filter; add `--include-thoughts` flag to CLI
- **HTML output:** Add an `HtmlRenderer` alongside `MarkdownRenderer` — same interface, different output

**Note:** `msg.text` is mutated in-place during image path resolution in `keromdizer.py`. If the same parsed objects are reused (e.g., in a TUI re-render), re-parsing will be necessary. This is a known trade-off in the current CLI design.
