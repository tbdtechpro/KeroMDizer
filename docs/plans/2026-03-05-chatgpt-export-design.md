# KeroMDizer — ChatGPT Export to GFM Markdown Converter

**Date:** 2026-03-05
**Status:** Approved

## Overview

A Python CLI tool that reads a ChatGPT data export folder and converts all conversations into GitHub-Flavored Markdown (GFM) files, one per conversation branch. Designed with a clean internal class structure to support a future TUI layer without architectural changes.

## Decisions Summary

| Decision | Choice |
|---|---|
| Input | CLI argument (export folder path) |
| Output naming | `YYYY-MM-DD_Title_Sanitized[_branch-N].md` |
| Code styling | Pure GFM fenced blocks with language tags |
| Content included | User + assistant text messages only |
| Metadata | Markdown table at top of each file |
| Branches | Each branch = separate file |
| Images | Copied to `assets/`, relative links in markdown |
| Deduplication | By `conversation_id` + `update_time` via `manifest.json` |

## Architecture

```
keromdizer.py          ← CLI entrypoint (argparse)
├── ConversationParser ← reads conversations.json, reconstructs threads
├── MarkdownRenderer   ← converts parsed conversations to GFM markdown strings
└── FileManager        ← handles output paths, deduplication, image copying
```

### `ConversationParser`

- Loads `conversations.json` from the export folder
- For each conversation, walks the `mapping` tree to find all leaf nodes
- Traces each leaf → root via `parent` links to reconstruct all branches
- Filters nodes to `user` and `assistant` roles with `text` content type only
- Yields normalized `Conversation` dataclass objects:
  - `id`, `title`, `create_time`, `update_time`, `model_slug`
  - `branches[]` — each branch is an ordered list of `Message` objects

### `MarkdownRenderer`

- Takes a `Conversation` and branch index, returns a GFM markdown string
- Renders a metadata table, then messages as `### 👤 User` / `### 🤖 Assistant` sections
- Passes assistant/user text through as-is (preserving existing markdown and code fences)
- Converts `sediment://file_xxx` image references to relative `assets/` paths

### `FileManager`

- Sanitizes titles to safe filenames (replaces `/`, `:`, `?`, etc. with `_`)
- Truncates filenames at 80 characters; full title preserved in metadata table
- Detects filename collisions across different conversations and appends `conversation_id` suffix
- Checks `manifest.json` for existing `conversation_id` + `update_time` to skip or overwrite
- Copies referenced image files to `output/assets/`
- Writes `manifest.json` after each run

## Data Flow

```
Export Folder
│
├── conversations.json
│   └── ConversationParser
│       ├── Load all conversations
│       ├── For each conversation:
│       │   ├── Find all leaf nodes in mapping tree
│       │   ├── Trace each leaf → root to get branch paths
│       │   ├── Filter: keep user + assistant text nodes only
│       │   └── Yield Conversation(id, title, times, model, branches[])
│
├── image files (file-*.jpg, file-*.png, etc.)
│   └── FileManager.copy_assets() → output/assets/
│
└── MarkdownRenderer
    ├── For each Conversation × branch:
    │   ├── Build metadata table
    │   ├── Render messages top-to-bottom
    │   └── Return markdown string
    └── FileManager.write()
        ├── Check manifest → skip if up-to-date, overwrite if newer
        └── output/YYYY-MM-DD_Title[_branch-N].md
```

## CLI Interface

```
python keromdizer.py <export_folder> [--output <dir>] [--dry-run]
```

| Argument | Description | Default |
|---|---|---|
| `export_folder` | Path to the ChatGPT export directory | required |
| `--output` | Destination directory for markdown files | `./output` |
| `--dry-run` | Print what would be written without writing anything | off |

## Output Format

### File naming

- Single branch: `2026-01-14_Branch_Casper_Environment_Setup_Plan.md`
- Multiple branches: `2026-01-14_Branch_Casper_Environment_Setup_Plan_branch-2.md`

### File structure

```markdown
| Field | Value |
|---|---|
| Date | 2026-01-14 |
| Model | gpt-5-2 |
| Conversation ID | 69671724-c1c0-8331-a946-7ab76cd67b71 |
| Branch | 1 of 3 |

# Conversation Title Here

---

### 👤 User

User message text here...

---

### 🤖 Assistant

Assistant response here, with code blocks preserved:

```python
print("hello world")
```

---
```

### Directory structure

```
output/
├── assets/
│   ├── file-abc123-sanitized.jpeg
│   └── file-def456-sanitized.png
├── manifest.json
├── 2026-01-14_Branch_Casper_Environment_Setup_Plan.md
├── 2026-01-14_Branch_Casper_Environment_Setup_Plan_branch-2.md
└── 2025-11-23_Some_Other_Chat.md
```

## Error Handling & Edge Cases

### Data edge cases

| Situation | Handling |
|---|---|
| Conversation with no user/assistant messages | Skip silently |
| Message with `null` or empty `parts` | Skip that message |
| Title with special characters | Sanitize to `_` in filename; preserve original in metadata table |
| Duplicate titles across conversations | Append short `conversation_id` suffix to disambiguate |
| Title longer than 80 characters | Truncate in filename; full title in metadata table |
| Image referenced but file missing from export | Warn to stdout; render as `![missing image](assets/filename)` |

### Runtime errors

| Situation | Handling |
|---|---|
| `conversations.json` not found | Clear error message, exit with non-zero code |
| Output directory not writable | Clear error message, exit with non-zero code |
| Individual conversation parse failure | Log warning, skip conversation, continue processing |

### Deduplication

State is persisted in `output/manifest.json`:

```json
{
  "conversation_id": {
    "update_time": 1768364101.184939,
    "files": ["2026-01-14_Title.md", "2026-01-14_Title_branch-2.md"]
  }
}
```

On each run: load manifest → compare `update_time` → skip if unchanged, overwrite if newer, write if new.

## Future Extension Points

- **TUI layer:** Add a TUI frontend that instantiates the same `ConversationParser`, `MarkdownRenderer`, and `FileManager` classes — no architectural changes needed
- **Additional export formats:** Swap or extend `MarkdownRenderer` for HTML, Obsidian-flavored markdown, etc.
- **DeepSeek support:** `ConversationParser` can be subclassed or extended for other export schemas (DeepSeek exports share a similar `conversations.json` structure)
- **Content type flags:** CLI flags to optionally include `thoughts`, `execution_output`, `tool` calls
