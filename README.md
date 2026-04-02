# KeroMDizer

Converts ChatGPT and DeepSeek data export folders into GitHub-Flavored Markdown (GFM) files — one `.md` file per conversation branch. Includes a terminal UI for browsing, tagging, and syncing conversations to projects.

- Pure Python, no external runtime dependencies for core conversion
- SQLite-backed deduplication — re-running only processes new or updated conversations
- Structured JSONL export for ML/AI consumption
- DeepSeek export support (auto-detected)
- TUI with folder browser, settings, tagging, and ChatGPT Projects sync

---

## Requirements

- Python 3.11+
- Ubuntu 24.04 ships Python 3.12 by default; `bootstrap.sh` handles installation otherwise

---

## Quick Start

```bash
bash bootstrap.sh          # First time: creates venv, installs deps, runs tests
source .venv/bin/activate  # Activate venv each session

# Convert an export folder
python keromdizer.py /path/to/chatgpt-export/ --output ./output

# Or launch the TUI
python tui.py
```

---

## CLI Usage

```bash
# Basic conversion (output defaults to ./output)
python keromdizer.py /path/to/export/

# Explicit output directory
python keromdizer.py /path/to/export/ --output ~/notes/chatgpt

# Preview without writing files
python keromdizer.py /path/to/export/ --dry-run

# Force a specific source (default: auto-detected)
python keromdizer.py /path/to/export/ --source deepseek

# Custom speaker labels for this run
python keromdizer.py /path/to/export/ --user-name Matt --assistant-name ChatGPT

# Export structured JSONL alongside markdown
python keromdizer.py /path/to/export/ --export-jsonl ./output/export.jsonl
```

---

## TUI

```bash
python tui.py
```

Seven screens navigated with keyboard shortcuts:

| Screen | Purpose |
|---|---|
| **MAIN** | Entry point |
| **FOLDER BROWSER** | Navigate to a ChatGPT or DeepSeek export folder |
| **PROVIDER SELECT** | Confirm auto-detected source or override |
| **CONFIRM** | Review settings before running |
| **RUN** | Live progress during conversion |
| **SETTINGS** | Configure output dir, speaker names, branch behaviour |
| **REVIEW** | Browse all imported conversations; tag, categorise, assign to projects |

The REVIEW screen provides an inline editor for `tags`, `project`, `category`, and `syntax` fields with autocomplete. Changes persist to the SQLite database and are included in subsequent JSONL exports.

---

## ChatGPT Projects Sync

The TUI Projects screen (`[P]` from MAIN) syncs your ChatGPT Projects to the local database, tagging each conversation with its project name. This requires a Bearer token from an active ChatGPT web session.

### Getting a Token

**Browser auto-extract (`[B]`) — recommended:** Reads your session cookie directly from Firefox or Chrome and exchanges it for a token automatically. This is the preferred method because it operates within the same browser session context that Cloudflare has already verified. It requires Firefox or Chrome to have an active chatgpt.com session. On Linux, Firefox may need to be closed when `[B]` is pressed, as it locks its profile database while open — though this is not required on all systems; Chrome/Chromium can usually be read while running.

**Manual paste (`[V]`):** If `[B]` fails, you can paste a token manually:

1. Open [chatgpt.com](https://chatgpt.com) and log in
2. Open DevTools (F12) and go to the **Console** tab
3. Paste and run:
   ```js
   (async () => {
     const s = await fetch('/api/auth/session').then(r => r.json());
     console.log(s.accessToken);
   })();
   ```
4. Copy the printed token (a long `eyJ...` string)
5. Press `[V]` in the TUI and paste it

> **Note:** ChatGPT session tokens expire after roughly 10 days. If a sync fails with an auth error, use `[B]` or grab a fresh token via the console snippet above.

### Configuring Projects

Add your project gizmo IDs to `~/.keromdizer.toml`. You can find a project's gizmo ID in its URL: `chatgpt.com/g/{gizmo_id}-{slug}/project`.

```toml
[chatgpt.projects]
"g-p-abc123" = "My Project Name"
"g-p-def456" = "Another Project"
```

---

## Configuration

All settings live in `~/.keromdizer.toml`. Every section is optional.

```toml
[user]
name = "Matt"

[providers.chatgpt]
assistant_name = "ChatGPT"

[providers.deepseek]
assistant_name = "DeepSeek"

[branches]
import          = "all"   # main | all — which branches enter the DB
export_markdown = "all"   # main | all — which branches become .md files
export_jsonl    = "all"   # main | all — which branches appear in JSONL

[database]
path = "~/.keromdizer.db"

[chatgpt.projects]
"g-p-abc123" = "My Project Name"
```

CLI flags `--user-name` and `--assistant-name` override TOML values for a single run.

---

## Output Format

Each `.md` file opens with a metadata table, then a title heading, then alternating user/assistant sections:

```markdown
| Field | Value |
|---|---|
| Date | 2026-01-14 |
| Model | gpt-4o |
| Conversation ID | abc-123 |
| Branch | 2 of 3 |

# Conversation Title

---

### 👤 User

User message text...

---

### 🤖 Assistant

Assistant response (code fences preserved verbatim)...

---
```

Output directory layout:

```
output/
├── assets/
│   └── file_abc123-sanitized.jpeg
├── 2026-01-14_Conversation_Title.md
└── 2026-01-14_Conversation_Title_branch-2.md
```

---

## JSONL Export

`--export-jsonl PATH` writes one JSON record per branch. Messages are structured into typed prose/code segments; tags use YAKE keyword extraction and Pygments syntax detection.

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
  "project": "My Project Name",
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

---

## Obsidian Export

KeroMDizer can write a parallel set of Obsidian-optimised `.md` files alongside the standard GFM output. Enable it in `~/.keromdizer.toml`:

```toml
[exports]
obsidian     = "yes"
obsidian_dir = "~/notes/chatgpt"   # optional — defaults to {output}/obsidian/
```

Obsidian files differ from GFM output in three ways:

- **YAML frontmatter** — title, aliases, created date, provider, model, conversation ID, branch info, tags, project, category, and syntax list
- **Callout-wrapped messages** — user messages use `> [!question]`, assistant messages use `> [!abstract]`
- **Wikilink images** — `![](assets/file.jpg)` becomes `![[file.jpg]]` for Obsidian's embed syntax

Tags are sanitised to Obsidian's valid character set (lowercase, alphanumeric, hyphens, underscores, forward slashes). Inferred tags from YAKE and user-applied tags are merged and deduplicated.

The TUI SETTINGS screen includes a toggle and directory field for Obsidian export.

---

## DeepSeek Support

DeepSeek exports are auto-detected from the presence of `user.json` containing a `mobile` field. Override with `--source deepseek`.

Key differences from ChatGPT exports:
- Timestamps are ISO 8601 strings, not Unix floats
- Messages use a `fragments` list (`REQUEST` = user, `RESPONSE` = assistant; `THINK`/`SEARCH` skipped)
- Main branch is determined by latest timestamp, not a `current_node` pointer
- Model slugs: `deepseek-chat`, `deepseek-reasoner`

---

## Deduplication

`~/.keromdizer.db` (SQLite) tracks every imported conversation by `update_time`. Re-running against the same export skips unchanged conversations. User-applied tags, project, category, and syntax fields are preserved across re-imports.

---

## Testing

```bash
pytest tests/ -v        # 298 tests
pytest tests/test_parser.py -v
pytest tests/test_tui.py -v
```

---

## Architecture

```
keromdizer.py           CLI entrypoint — argparse, thin wiring only
tui.py                  Terminal UI (BubbleTea Elm pattern, Catppuccin Mocha theme)
conversation_parser.py  ChatGPT export parsing — tree traversal, branch reconstruction
deepseek_parser.py      DeepSeek parser (subclasses ConversationParser)
parser_factory.py       Auto-detect source, return correct parser
renderer.py             GFM markdown generation
obsidian_renderer.py    Obsidian-optimised markdown (YAML frontmatter, callouts, wikilinks)
file_manager.py         Filenames, deduplication, image copying
models.py               Message, Branch, Conversation, PersonaConfig dataclasses
config.py               ~/.keromdizer.toml loading
content_parser.py       Splits message text into prose/code ContentSegments
inference.py            YAKE keyword extraction + Pygments syntax detection
db.py                   DatabaseManager — SQLite source of truth
jsonl_exporter.py       JSONL export from DB
project_fetcher.py      ChatGPT Projects API sync
retrieve_token.py       Bearer token retrieval (browser extract or manual paste)
```
