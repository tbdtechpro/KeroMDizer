# DeepSeek Export Support — Design

**Date:** 2026-03-06
**Status:** Approved

## Summary

Add support for converting DeepSeek chat export folders to GFM markdown, using the same output format, renderer, file manager, and persona config as the existing ChatGPT pipeline. Auto-detect export source from folder contents; `--source` flag overrides.

## DeepSeek Export Format (analysed from 2026-03-06 export)

| Field | ChatGPT | DeepSeek |
|---|---|---|
| Conversation keys | `id`, `title`, `create_time`, `update_time`, `mapping`, `current_node`, `default_model_slug` | `id`, `title`, `inserted_at`, `updated_at`, `mapping` |
| Node message keys | `author.role`, `content.content_type`, `content.parts` | `model`, `inserted_at`, `fragments` |
| Role field | `message.author.role` = `user`/`assistant` | `fragment.type` = `REQUEST`/`RESPONSE` |
| Content field | `content.parts[0]` (list) | `fragment.content` (plain string) |
| Skip types | `thoughts`, `code`, `execution_output`, `tether_browsing_display` | `THINK`, `SEARCH` |
| Model | `conversation.default_model_slug` | `message.model` (per-message) |
| Timestamps | Unix float (`create_time`) | ISO 8601 string (`inserted_at`) |
| Main branch | `current_node` pointer | Latest-timestamp leaf |
| Images | `sediment://` URIs, files in export | `files: []` — not present in exports |
| Shared convs | `shared_conversations.json` | Not present |
| Audio | Per-conversation `audio/` dirs | Not present |
| Model slugs | `gpt-4o`, `o1`, etc. | `deepseek-chat`, `deepseek-reasoner` |

Multi-fragment messages: DeepSeek Reasoner produces `[THINK, RESPONSE]` in a single node. Only `RESPONSE` is extracted; `THINK` is skipped (same as ChatGPT's `thoughts`).

## Architecture

Three new files. Zero changes to `models.py`, `renderer.py`, `file_manager.py`, `config.py`.

```
deepseek_parser.py    ← DeepSeekParser(ConversationParser) subclass
parser_factory.py     ← detect_source(), build_parser() — TUI seam
tests/test_deepseek_parser.py
tests/test_parser_factory.py
tests/fixtures/sample_deepseek_conversations.json
```

`keromdizer.py` gets two small changes: import `build_parser`, add `--source` flag.

## `deepseek_parser.py`

Subclasses `ConversationParser`. Inherits unchanged:
- `_load_raw_conversations` (same `conversations.json` filename and structure)
- `parse` (load → iterate → `_parse_conversation` per conv)
- `_find_leaf_ids` / `_trace_to_root` (tree traversal is identical)

Overrides:

**`_load_shared_ids`** → returns `set()` always (no shared conversations in DeepSeek).

**`_parse_conversation`**:
- Main branch: no `current_node` — use leaf with latest `inserted_at` as branch 1
- Timestamps: parse ISO strings via `datetime.fromisoformat(ts).timestamp()` → float
- Model: extracted from first `RESPONSE` fragment node in main branch path
- `audio_count=0` always (no audio in DeepSeek exports)
- Title/id field names identical to ChatGPT

**`_extract_messages`**:
- Iterate `msg.get('fragments', [])` per node
- Keep `REQUEST` (→ `role='user'`) and `RESPONSE` (→ `role='assistant'`) only
- `THINK` and `SEARCH` silently skipped
- Content: `fragment['content']` is a plain string — no parts unwrapping
- `create_time`: parse `msg.get('inserted_at')` ISO string → float
- `image_refs=[]` always (no images in DeepSeek exports)

## `parser_factory.py`

```python
def detect_source(export_folder: Path) -> str:
    user_json = export_folder / 'user.json'
    if user_json.exists():
        data = json.loads(user_json.read_text(encoding='utf-8'))
        if 'mobile' in data:      # DeepSeek-specific field
            return 'deepseek'
    return 'chatgpt'              # safe default

def build_parser(export_folder: Path, source: str | None = None) -> tuple[ConversationParser, str]:
    provider = source or detect_source(export_folder)
    parser = DeepSeekParser(export_folder) if provider == 'deepseek' else ConversationParser(export_folder)
    return parser, provider
```

Returns `(parser, provider_str)` so the caller passes `provider` straight into `load_persona()`. The TUI calls `build_parser(folder)` directly — no argparse dependency.

## CLI changes (`keromdizer.py`)

New flag:
```python
arg_parser.add_argument(
    '--source',
    choices=['chatgpt', 'deepseek'],
    default=None,
    help='Export source (default: auto-detected from folder contents)',
)
```

Replace hardcoded parser + persona wiring:
```python
# Before:
conv_parser = ConversationParser(args.export_folder)
persona = load_persona(provider='chatgpt', ...)

# After:
conv_parser, provider = build_parser(args.export_folder, source=args.source)
persona = load_persona(provider=provider, ...)
```

## Persona Config Integration

`load_persona(provider='deepseek')` reads `[providers.deepseek]` from `~/.keromdizer.toml`. The default assistant name for `deepseek` is already `'DeepSeek'` in `PROVIDER_DEFAULTS`. No changes to `config.py`.

## Testing

**`tests/fixtures/sample_deepseek_conversations.json`** — synthetic fixture covering:
- Single-branch conversation (REQUEST → RESPONSE)
- Branched conversation (two leaves, different timestamps — later leaf is main branch)
- Reasoner conversation with THINK+RESPONSE (THINK skipped)
- SEARCH fragment (skipped, produces no messages)
- Null-message node (skipped without crash)

**`tests/test_deepseek_parser.py`**:
- `test_parse_basic_conversation` — title, id, model extracted
- `test_iso_timestamps_parsed` — `create_time`/`update_time` are floats
- `test_request_response_roles` — roles mapped correctly
- `test_think_fragments_skipped` — THINK content absent from output
- `test_search_fragments_skipped` — SEARCH nodes produce no messages
- `test_branch_main_is_latest_timestamp` — branch 1 is later-timestamped leaf
- `test_model_extracted_from_first_response` — `model_slug` correct
- `test_empty_node_skipped` — null message node handled safely

**`tests/test_parser_factory.py`**:
- `test_detect_source_deepseek` — `user.json` with `mobile` field → `'deepseek'`
- `test_detect_source_chatgpt_no_user_json` — no `user.json` → `'chatgpt'`
- `test_detect_source_chatgpt_no_mobile_field` — `user.json` without `mobile` → `'chatgpt'`
- `test_build_parser_returns_deepseek_parser` — correct type
- `test_build_parser_source_override` — explicit source overrides auto-detect
- `test_build_parser_returns_provider_string` — tuple second element correct

## Future / Out of Scope

- Image attachments from DeepSeek (not present in current export format)
- Shared conversation flag for DeepSeek
- Per-conversation audio for DeepSeek
- JSONL export (#20) — DeepSeek data will flow through the same `Conversation` model, so JSONL generation is provider-agnostic by design
