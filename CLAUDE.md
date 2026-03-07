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

# Specify export source explicitly (default: auto-detected)
python keromdizer.py /path/to/export/ --source deepseek

# Custom speaker labels (CLI override)
python keromdizer.py /path/to/export/ --user-name Matt --assistant-name ChatGPT

# Export JSONL for ML/AI consumption
python keromdizer.py /path/to/export/ --export-jsonl ./output/export.jsonl

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
├── models.py               ← Message, Branch, Conversation dataclasses
├── deepseek_parser.py      ← DeepSeekParser subclass (DeepSeek export support)
├── parser_factory.py       ← detect_source(), build_parser() — provider auto-detection
├── content_parser.py       ← Parse message text into prose/code segments
├── inference.py            ← YAKE keyword extraction + Pygments syntax detection (at import time)
├── db.py                   ← DatabaseManager — SQLite source of truth (replaces manifest.json)
└── jsonl_exporter.py       ← Export branches from DB to JSONL format
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
| `deepseek_parser.py` | DeepSeek export parsing (subclasses `ConversationParser`) |
| `parser_factory.py` | Auto-detect source, return parser + provider string |
| `config.py` | Persona config loading — reads `~/.keromdizer.toml`, resolves display names |
| `content_parser.py` | Parse message text into `ContentSegment` list (prose/code) |
| `inference.py` | `infer_tags()` (YAKE) + `infer_syntax()` (Pygments) — run at import time |
| `db.py` | `DatabaseManager` — SQLite DB replacing `manifest.json` |
| `jsonl_exporter.py` | `export_jsonl()` — write JSONL from DB, respects branch config |
| `conftest.py` | Adds project root to `sys.path` for pytest |
| `tests/fixtures/sample_conversations.json` | Minimal test fixture (3 conversations) |

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

## DeepSeek Export Support

Auto-detected from `user.json` containing a `mobile` field. Override with `--source deepseek`.

```bash
# Auto-detect (default)
python keromdizer.py /path/to/deepseek-export/

# Explicit source
python keromdizer.py /path/to/deepseek-export/ --source deepseek
```

Key format differences from ChatGPT:
- Timestamps are ISO 8601 strings (`inserted_at`, `updated_at`) not Unix floats
- Messages use `fragments` list with `type` field: `REQUEST` (user), `RESPONSE` (assistant)
- `THINK` and `SEARCH` fragments are silently skipped (like ChatGPT's `thoughts`)
- Main branch is the leaf with the latest `inserted_at` (no `current_node` pointer)
- Model slug is per-message (first `RESPONSE` fragment): `deepseek-chat`, `deepseek-reasoner`
- No shared conversations, no audio recordings in DeepSeek exports

Persona config: `[providers.deepseek]` in `~/.keromdizer.toml`. Default assistant name: `DeepSeek`.

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

`DatabaseManager` maintains `~/.keromdizer.db` (SQLite). On each run it compares `update_time` — conversations are re-exported only if newer. This replaces the old `manifest.json` approach. User-applied tags, project, category, and syntax are preserved across re-imports.

`_used_filenames` is seeded from the database at startup to prevent cross-run filename collisions when two conversations share the same title.

## JSONL Export

`--export-jsonl PATH` writes one JSON record per line to PATH. Each record covers one branch:

```json
{
  "schema_version": "1",
  "id": "abc123__branch_1",
  "conversation_id": "abc123",
  "branch_index": 1,
  "is_main_branch": true,
  "provider": "chatgpt",
  "title": "My Conversation",
  "create_time": "2026-01-14T04:16:34+00:00",
  "model_slug": "gpt-4o",
  "tags": [],
  "project": null,
  "category": null,
  "syntax": [],
  "inferred_tags": ["python", "async"],
  "inferred_syntax": ["python", "bash"],
  "messages": [
    {
      "role": "user",
      "timestamp": "2026-01-14T04:16:34+00:00",
      "content": [
        {"type": "prose", "text": "Here is the code:"},
        {"type": "code", "language": "python", "text": "def foo():\n    pass"}
      ]
    }
  ]
}
```

Messages have structured `content` (prose/code segments extracted at import time). `inferred_tags` uses YAKE keyword extraction; `inferred_syntax` uses Pygments on code blocks.

## Branch Config

Branch handling can be configured in `~/.keromdizer.toml` and in the TUI Settings screen:

```toml
[branches]
import          = "all"   # main | all — which branches enter the DB
export_markdown = "all"   # main | all — which branches become .md files
export_jsonl    = "all"   # main | all — which branches appear in JSONL
```

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

The TUI REVIEW screen is a fully functional tagging interface: a scrollable table of all imported branches, with an inline editor for `tags`, `project`, `category`, and `syntax` fields. Autocomplete suggests existing tags as you type. Changes are persisted to the SQLite database and included in subsequent JSONL exports.

## Filename Sanitization

`FileManager.sanitize_filename()` replaces these characters with `_`: `<>:"/\|?*`, control chars (0x00–0x1f), middle dot `·`, bullet `•`, curly quotes `''`. Multiple consecutive underscores/spaces are collapsed. Titles truncate at 80 characters; full title is preserved in the metadata table.

ChatGPT titles frequently contain `·` (middle dot, U+00B7) — e.g., `"Branch · Casper Setup"` — which is why it's in the sanitize regex.

## Testing

Tests live in `tests/`. The `conftest.py` at the project root adds `.` to `sys.path` so bare `pytest` works (no need for `python -m pytest`).

```bash
pytest tests/ -v                           # all tests (182 total)
pytest tests/test_parser.py -v             # parser only
pytest tests/test_renderer.py -v           # renderer only
pytest tests/test_file_manager.py -v       # file manager only
pytest tests/test_parser_factory.py -v     # parser factory / auto-detection
pytest tests/test_branch_config.py -v      # branch config
pytest tests/test_content_parser.py -v     # content parser
pytest tests/test_db.py -v                 # database manager
pytest tests/test_inference.py -v          # inference engine
pytest tests/test_jsonl_exporter.py -v     # JSONL exporter
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
