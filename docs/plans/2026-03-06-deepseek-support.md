# DeepSeek Export Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add DeepSeek export-to-GFM conversion, auto-detecting the source from the export folder, with the same renderer/file_manager/persona pipeline as ChatGPT.

**Architecture:** `DeepSeekParser` subclasses `ConversationParser`, overriding only `_parse_conversation` and `_extract_messages`. A new `parser_factory.py` module exposes `detect_source()` and `build_parser()` as the clean TUI seam. `keromdizer.py` gains a `--source` flag and replaces its hardcoded `ConversationParser` instantiation with `build_parser()`.

**Tech Stack:** Python 3.11+ stdlib only (`datetime.fromisoformat`). pytest with `tmp_path` for isolation.

---

### Task 1: Create DeepSeek test fixture

**Files:**
- Create: `tests/fixtures/sample_deepseek_conversations.json`

This fixture covers all 8 parser test cases. No commit yet — committed in Task 3.

**Step 1: Create the fixture file with this exact content:**

```json
[
  {
    "id": "ds-single-001",
    "title": "Single Branch Chat",
    "inserted_at": "2025-01-30T06:00:00.000000+00:00",
    "updated_at": "2025-01-30T06:10:00.000000+00:00",
    "mapping": {
      "root": {"id": "root", "parent": null, "children": ["n1"], "message": null},
      "n1": {"id": "n1", "parent": "root", "children": ["n2"], "message": {"model": "deepseek-chat", "inserted_at": "2025-01-30T06:00:01.000000+00:00", "files": [], "fragments": [{"type": "REQUEST", "content": "Hello DeepSeek"}]}},
      "n2": {"id": "n2", "parent": "n1", "children": [], "message": {"model": "deepseek-chat", "inserted_at": "2025-01-30T06:00:02.000000+00:00", "files": [], "fragments": [{"type": "RESPONSE", "content": "Hello! How can I help?"}]}}
    }
  },
  {
    "id": "ds-branched-002",
    "title": "Branched Chat",
    "inserted_at": "2025-02-01T10:00:00.000000+00:00",
    "updated_at": "2025-02-01T11:00:00.000000+00:00",
    "mapping": {
      "root": {"id": "root", "parent": null, "children": ["n1"], "message": null},
      "n1": {"id": "n1", "parent": "root", "children": ["n2"], "message": {"model": "deepseek-chat", "inserted_at": "2025-02-01T10:00:01.000000+00:00", "files": [], "fragments": [{"type": "REQUEST", "content": "Tell me about AI"}]}},
      "n2": {"id": "n2", "parent": "n1", "children": ["n3", "n5"], "message": {"model": "deepseek-chat", "inserted_at": "2025-02-01T10:00:02.000000+00:00", "files": [], "fragments": [{"type": "RESPONSE", "content": "AI is fascinating"}]}},
      "n3": {"id": "n3", "parent": "n2", "children": ["n4"], "message": {"model": "deepseek-chat", "inserted_at": "2025-02-01T10:30:00.000000+00:00", "files": [], "fragments": [{"type": "REQUEST", "content": "More about AI (branch A)"}]}},
      "n4": {"id": "n4", "parent": "n3", "children": [], "message": {"model": "deepseek-chat", "inserted_at": "2025-02-01T10:30:01.000000+00:00", "files": [], "fragments": [{"type": "RESPONSE", "content": "Branch A answer"}]}},
      "n5": {"id": "n5", "parent": "n2", "children": ["n6"], "message": {"model": "deepseek-chat", "inserted_at": "2025-02-01T11:00:00.000000+00:00", "files": [], "fragments": [{"type": "REQUEST", "content": "More about AI (branch B)"}]}},
      "n6": {"id": "n6", "parent": "n5", "children": [], "message": {"model": "deepseek-chat", "inserted_at": "2025-02-01T11:00:01.000000+00:00", "files": [], "fragments": [{"type": "RESPONSE", "content": "Branch B answer (latest)"}]}}
    }
  },
  {
    "id": "ds-reasoner-003",
    "title": "Reasoner Chat",
    "inserted_at": "2025-03-01T09:00:00.000000+00:00",
    "updated_at": "2025-03-01T09:05:00.000000+00:00",
    "mapping": {
      "root": {"id": "root", "parent": null, "children": ["n1"], "message": null},
      "n1": {"id": "n1", "parent": "root", "children": ["n2"], "message": {"model": "deepseek-reasoner", "inserted_at": "2025-03-01T09:00:01.000000+00:00", "files": [], "fragments": [{"type": "REQUEST", "content": "Solve this logic puzzle"}]}},
      "n2": {"id": "n2", "parent": "n1", "children": [], "message": {"model": "deepseek-reasoner", "inserted_at": "2025-03-01T09:00:02.000000+00:00", "files": [], "fragments": [{"type": "THINK", "content": "Let me reason step by step..."}, {"type": "RESPONSE", "content": "The answer is 42."}]}}
    }
  },
  {
    "id": "ds-search-004",
    "title": "Search Chat",
    "inserted_at": "2025-03-02T09:00:00.000000+00:00",
    "updated_at": "2025-03-02T09:05:00.000000+00:00",
    "mapping": {
      "root": {"id": "root", "parent": null, "children": ["n1"], "message": null},
      "n1": {"id": "n1", "parent": "root", "children": ["n2"], "message": {"model": "deepseek-chat", "inserted_at": "2025-03-02T09:00:01.000000+00:00", "files": [], "fragments": [{"type": "REQUEST", "content": "Search the web for AI news"}]}},
      "n2": {"id": "n2", "parent": "n1", "children": ["n3"], "message": {"model": "deepseek-chat", "inserted_at": "2025-03-02T09:00:02.000000+00:00", "files": [], "fragments": [{"type": "SEARCH", "content": "AI news 2025"}]}},
      "n3": {"id": "n3", "parent": "n2", "children": [], "message": {"model": "deepseek-chat", "inserted_at": "2025-03-02T09:00:03.000000+00:00", "files": [], "fragments": [{"type": "RESPONSE", "content": "Here are the latest AI developments."}]}}
    }
  },
  {
    "id": "ds-null-msg-005",
    "title": "Null Message Chat",
    "inserted_at": "2025-03-03T09:00:00.000000+00:00",
    "updated_at": "2025-03-03T09:05:00.000000+00:00",
    "mapping": {
      "root": {"id": "root", "parent": null, "children": ["n1"], "message": null},
      "n1": {"id": "n1", "parent": "root", "children": ["n2"], "message": null},
      "n2": {"id": "n2", "parent": "n1", "children": ["n3"], "message": {"model": "deepseek-chat", "inserted_at": "2025-03-03T09:00:02.000000+00:00", "files": [], "fragments": [{"type": "REQUEST", "content": "Hello"}]}},
      "n3": {"id": "n3", "parent": "n2", "children": [], "message": {"model": "deepseek-chat", "inserted_at": "2025-03-03T09:00:03.000000+00:00", "files": [], "fragments": [{"type": "RESPONSE", "content": "Hi there!"}]}}
    }
  }
]
```

**Step 2: Verify it is valid JSON:**

```bash
python3 -c "import json; json.load(open('tests/fixtures/sample_deepseek_conversations.json')); print('OK')"
```
Expected: `OK`

---

### Task 2: Write failing tests for DeepSeekParser

**Files:**
- Create: `tests/test_deepseek_parser.py`

**Step 1: Create `tests/test_deepseek_parser.py` with this exact content:**

```python
from datetime import datetime
from pathlib import Path
import pytest
from deepseek_parser import DeepSeekParser

FIXTURE = Path(__file__).parent / 'fixtures' / 'sample_deepseek_conversations.json'


@pytest.fixture
def export_dir(tmp_path):
    data = FIXTURE.read_text(encoding='utf-8')
    (tmp_path / 'conversations.json').write_text(data, encoding='utf-8')
    return tmp_path


@pytest.fixture
def ds_convs(export_dir):
    return DeepSeekParser(export_dir).parse()


def test_parse_basic_conversation(ds_convs):
    conv = next(c for c in ds_convs if c.id == 'ds-single-001')
    assert conv.title == 'Single Branch Chat'
    assert conv.model_slug == 'deepseek-chat'
    assert len(conv.branches) == 1


def test_iso_timestamps_parsed(ds_convs):
    conv = next(c for c in ds_convs if c.id == 'ds-single-001')
    expected_create = datetime.fromisoformat('2025-01-30T06:00:00.000000+00:00').timestamp()
    expected_update = datetime.fromisoformat('2025-01-30T06:10:00.000000+00:00').timestamp()
    assert conv.create_time == pytest.approx(expected_create)
    assert conv.update_time == pytest.approx(expected_update)


def test_request_response_roles(ds_convs):
    conv = next(c for c in ds_convs if c.id == 'ds-single-001')
    msgs = conv.branches[0].messages
    assert len(msgs) == 2
    assert msgs[0].role == 'user'
    assert msgs[0].text == 'Hello DeepSeek'
    assert msgs[1].role == 'assistant'
    assert msgs[1].text == 'Hello! How can I help?'


def test_think_fragments_skipped(ds_convs):
    conv = next(c for c in ds_convs if c.id == 'ds-reasoner-003')
    msgs = conv.branches[0].messages
    assert len(msgs) == 2
    assert msgs[1].role == 'assistant'
    assert msgs[1].text == 'The answer is 42.'
    assert 'Let me reason step by step' not in msgs[1].text


def test_search_fragments_skipped(ds_convs):
    conv = next(c for c in ds_convs if c.id == 'ds-search-004')
    msgs = conv.branches[0].messages
    all_text = ' '.join(m.text for m in msgs)
    assert 'AI news 2025' not in all_text
    assert any(m.role == 'assistant' for m in msgs)


def test_branch_main_is_latest_timestamp(ds_convs):
    conv = next(c for c in ds_convs if c.id == 'ds-branched-002')
    assert len(conv.branches) == 2
    branch1_texts = [m.text for m in conv.branches[0].messages]
    assert 'Branch B answer (latest)' in branch1_texts
    assert conv.branches[0].branch_index == 1
    assert conv.branches[1].branch_index == 2


def test_model_extracted_from_first_response(ds_convs):
    conv = next(c for c in ds_convs if c.id == 'ds-single-001')
    assert conv.model_slug == 'deepseek-chat'
    conv_r = next(c for c in ds_convs if c.id == 'ds-reasoner-003')
    assert conv_r.model_slug == 'deepseek-reasoner'


def test_empty_node_skipped(ds_convs):
    conv = next(c for c in ds_convs if c.id == 'ds-null-msg-005')
    assert conv is not None
    msgs = conv.branches[0].messages
    assert len(msgs) == 2
    assert msgs[0].role == 'user'
    assert msgs[0].text == 'Hello'
    assert msgs[1].role == 'assistant'
```

**Step 2: Run tests to confirm they fail:**

```bash
pytest tests/test_deepseek_parser.py -v
```
Expected: `ModuleNotFoundError: No module named 'deepseek_parser'`

---

### Task 3: Implement deepseek_parser.py

**Files:**
- Create: `deepseek_parser.py`

**Step 1: Create `deepseek_parser.py` with this exact content:**

```python
from datetime import datetime
from models import Conversation, Branch, Message
from conversation_parser import ConversationParser


class DeepSeekParser(ConversationParser):
    """Parser for DeepSeek export folders.

    DeepSeek exports use the same mapping tree structure as ChatGPT but differ in:
    - Fragment-based messages (REQUEST/RESPONSE/THINK/SEARCH) instead of content.parts
    - ISO 8601 timestamps instead of Unix floats
    - No current_node — main branch is the leaf with the latest inserted_at timestamp
    - Model is per-message, not per-conversation
    - No shared conversations, no audio, no image assets
    """

    def _load_shared_ids(self) -> set[str]:
        return set()

    def _parse_conversation(self, raw: dict) -> Conversation | None:
        mapping = raw.get('mapping', {})

        leaf_ids = self._find_leaf_ids(mapping)
        if not leaf_ids:
            return None

        # Main branch = leaf with the latest inserted_at timestamp
        def leaf_timestamp(leaf_id: str) -> float:
            msg = (mapping.get(leaf_id) or {}).get('message') or {}
            return self._parse_iso_timestamp_safe(msg.get('inserted_at')) or 0.0

        sorted_leaves = sorted(leaf_ids, key=leaf_timestamp, reverse=True)
        main_leaf = sorted_leaves[0]

        branches = []
        seen_paths: set[tuple] = set()

        for leaf_id in sorted_leaves:
            path = self._trace_to_root(mapping, leaf_id)
            path_key = tuple(path)
            if path_key in seen_paths:
                continue
            seen_paths.add(path_key)

            messages = self._extract_messages(mapping, path)
            if not messages:
                continue

            is_main = leaf_id == main_leaf
            branches.append((is_main, path_key, messages))

        if not branches:
            return None

        branches.sort(key=lambda x: (0 if x[0] else 1))
        final_branches = [
            Branch(messages=msgs, branch_index=i + 1)
            for i, (_, _, msgs) in enumerate(branches)
        ]

        main_path = self._trace_to_root(mapping, main_leaf)
        model_slug = self._extract_model(mapping, main_path)

        return Conversation(
            id=raw.get('id', ''),
            title=raw.get('title') or 'Untitled',
            create_time=self._parse_iso_timestamp_safe(raw.get('inserted_at')),
            update_time=self._parse_iso_timestamp_safe(raw.get('updated_at')),
            model_slug=model_slug,
            branches=final_branches,
            audio_count=0,
        )

    def _extract_messages(self, mapping: dict, path_ids: list[str]) -> list[Message]:
        messages = []
        for nid in path_ids:
            node = mapping.get(nid, {})
            msg = node.get('message')
            if not msg:
                continue
            create_time = self._parse_iso_timestamp_safe(msg.get('inserted_at'))
            for frag in msg.get('fragments', []):
                frag_type = frag.get('type')
                if frag_type == 'REQUEST':
                    role = 'user'
                elif frag_type == 'RESPONSE':
                    role = 'assistant'
                else:
                    continue  # skip THINK, SEARCH
                content = frag.get('content', '')
                if not content.strip():
                    continue
                messages.append(Message(
                    role=role,
                    text=content,
                    create_time=create_time,
                    image_refs=[],
                ))
        return messages

    def _extract_model(self, mapping: dict, path_ids: list[str]) -> str | None:
        """Return model from the first RESPONSE fragment found in path."""
        for nid in path_ids:
            msg = (mapping.get(nid) or {}).get('message')
            if not msg:
                continue
            for frag in msg.get('fragments', []):
                if frag.get('type') == 'RESPONSE':
                    return msg.get('model')
        return None

    def _parse_iso_timestamp(self, ts: str) -> float:
        return datetime.fromisoformat(ts).timestamp()

    def _parse_iso_timestamp_safe(self, ts: str | None) -> float | None:
        if not ts:
            return None
        try:
            return self._parse_iso_timestamp(ts)
        except (ValueError, AttributeError):
            return None
```

**Step 2: Run the DeepSeek parser tests:**

```bash
pytest tests/test_deepseek_parser.py -v
```
Expected: all 8 tests PASS.

**Step 3: Run the full test suite to confirm no regressions:**

```bash
pytest tests/ -v
```
Expected: all tests pass (57 existing + 8 new = 65 total).

**Step 4: Commit:**

```bash
git add deepseek_parser.py tests/test_deepseek_parser.py tests/fixtures/sample_deepseek_conversations.json
git commit -m "feat: add DeepSeekParser with fragment-based message extraction"
```

---

### Task 4: Write failing tests for parser_factory

**Files:**
- Create: `tests/test_parser_factory.py`

**Step 1: Create `tests/test_parser_factory.py` with this exact content:**

```python
import json
import pytest
from pathlib import Path
from parser_factory import detect_source, build_parser
from deepseek_parser import DeepSeekParser
from conversation_parser import ConversationParser


def _make_export(tmp_path, user_json: dict | None = None) -> Path:
    """Create a minimal export dir. user_json=None means no user.json file."""
    (tmp_path / 'conversations.json').write_text('[]', encoding='utf-8')
    if user_json is not None:
        (tmp_path / 'user.json').write_text(json.dumps(user_json), encoding='utf-8')
    return tmp_path


def test_detect_source_deepseek(tmp_path):
    _make_export(tmp_path, {'user_id': 'abc', 'email': 'x@y.com', 'mobile': None})
    assert detect_source(tmp_path) == 'deepseek'


def test_detect_source_chatgpt_no_user_json(tmp_path):
    _make_export(tmp_path)
    assert detect_source(tmp_path) == 'chatgpt'


def test_detect_source_chatgpt_no_mobile_field(tmp_path):
    _make_export(tmp_path, {'user_id': 'abc', 'email': 'x@y.com'})
    assert detect_source(tmp_path) == 'chatgpt'


def test_build_parser_returns_deepseek_parser(tmp_path):
    _make_export(tmp_path, {'user_id': 'abc', 'mobile': None})
    parser, provider = build_parser(tmp_path)
    assert isinstance(parser, DeepSeekParser)
    assert provider == 'deepseek'


def test_build_parser_returns_chatgpt_parser(tmp_path):
    _make_export(tmp_path)
    parser, provider = build_parser(tmp_path)
    assert isinstance(parser, ConversationParser)
    assert not isinstance(parser, DeepSeekParser)
    assert provider == 'chatgpt'


def test_build_parser_source_override_chatgpt(tmp_path):
    # DeepSeek folder but forced to chatgpt via source param
    _make_export(tmp_path, {'user_id': 'abc', 'mobile': None})
    parser, provider = build_parser(tmp_path, source='chatgpt')
    assert isinstance(parser, ConversationParser)
    assert not isinstance(parser, DeepSeekParser)
    assert provider == 'chatgpt'
```

**Step 2: Run tests to confirm they fail:**

```bash
pytest tests/test_parser_factory.py -v
```
Expected: `ModuleNotFoundError: No module named 'parser_factory'`

---

### Task 5: Implement parser_factory.py

**Files:**
- Create: `parser_factory.py`

**Step 1: Create `parser_factory.py` with this exact content:**

```python
import json
from pathlib import Path

from conversation_parser import ConversationParser
from deepseek_parser import DeepSeekParser

SOURCES = ('chatgpt', 'deepseek')


def detect_source(export_folder: Path) -> str:
    """Infer export provider from folder contents.

    DeepSeek exports include user.json with a 'mobile' field.
    Falls back to 'chatgpt' if the field is absent or the file is missing.
    """
    user_json = Path(export_folder) / 'user.json'
    if user_json.exists():
        try:
            data = json.loads(user_json.read_text(encoding='utf-8'))
            if 'mobile' in data:
                return 'deepseek'
        except (json.JSONDecodeError, OSError):
            pass
    return 'chatgpt'


def build_parser(
    export_folder: Path,
    source: str | None = None,
) -> tuple[ConversationParser, str]:
    """Return (parser, provider_str) for the given export folder.

    source=None triggers auto-detection. Pass source='chatgpt' or
    source='deepseek' to override. The returned provider string can be
    passed directly to load_persona(provider=...).
    """
    provider = source or detect_source(export_folder)
    if provider == 'deepseek':
        return DeepSeekParser(export_folder), provider
    return ConversationParser(export_folder), provider
```

**Step 2: Run parser_factory tests:**

```bash
pytest tests/test_parser_factory.py -v
```
Expected: all 6 tests PASS.

**Step 3: Run full test suite:**

```bash
pytest tests/ -v
```
Expected: all tests pass (65 existing + 6 new = 71 total).

**Step 4: Commit:**

```bash
git add parser_factory.py tests/test_parser_factory.py
git commit -m "feat: add parser_factory with auto-detection and build_parser()"
```

---

### Task 6: Update keromdizer.py

**Files:**
- Modify: `keromdizer.py`

**Step 1: Update imports** — replace `from conversation_parser import ConversationParser` with `from parser_factory import build_parser`:

```python
import argparse
import sys
from pathlib import Path

from config import load_persona
from parser_factory import build_parser
from renderer import MarkdownRenderer
from file_manager import FileManager
```

**Step 2: Update the CLI description and add `--source` flag** — find the `ArgumentParser` description and the `--assistant-name` block, add `--source` immediately after `--assistant-name`:

```python
    arg_parser = argparse.ArgumentParser(
        description='Convert a ChatGPT or DeepSeek data export folder to GFM markdown files.'
    )
```

After the `--assistant-name` argument block (lines 36-40), add:

```python
    arg_parser.add_argument(
        '--source',
        choices=['chatgpt', 'deepseek'],
        default=None,
        help='Export source provider (default: auto-detected from folder contents)',
    )
```

**Step 3: Replace ConversationParser instantiation** — find line 47:
```python
    conv_parser = ConversationParser(args.export_folder)
```
Replace with:
```python
    conv_parser, provider = build_parser(args.export_folder, source=args.source)
```

**Step 4: Fix the hardcoded provider in load_persona** — find `provider='chatgpt'` (line 56):
```python
        persona = load_persona(
            provider='chatgpt',
            user_name=args.user_name,
            assistant_name=args.assistant_name,
        )
```
Replace with:
```python
        persona = load_persona(
            provider=provider,
            user_name=args.user_name,
            assistant_name=args.assistant_name,
        )
```

**Step 5: Verify --help shows the new flag:**

```bash
python keromdizer.py --help
```
Expected output includes:
```
  --source {chatgpt,deepseek}
```

**Step 6: Run full test suite:**

```bash
pytest tests/ -v
```
Expected: all 71 tests still pass.

**Step 7: Commit:**

```bash
git add keromdizer.py
git commit -m "feat: add --source flag and wire build_parser() into CLI"
```

---

### Task 7: Integration test + update CLAUDE.md

**Step 1: Dry-run against the real DeepSeek export (auto-detect):**

```bash
python keromdizer.py /home/matt/Downloads/deepseek_data-2026-03-06/ --dry-run 2>&1 | head -20
```
Expected: lines like `Would write: ./output/2025-01-30_Some_Title.md` with no errors. Should show ~263 conversations.

**Step 2: Dry-run with explicit --source deepseek:**

```bash
python keromdizer.py /home/matt/Downloads/deepseek_data-2026-03-06/ --dry-run --source deepseek 2>&1 | head -5
```
Expected: same output, no errors.

**Step 3: Dry-run with --assistant-name override:**

```bash
python keromdizer.py /home/matt/Downloads/deepseek_data-2026-03-06/ --dry-run --assistant-name DeepSeek 2>&1 | head -5
```
Expected: dry run output, no errors.

**Step 4: Update CLAUDE.md**

In the Architecture section, update the module map to add the two new files:

Find:
```
keromdizer.py          ← CLI entrypoint (argparse, thin wiring layer only)
├── conversation_parser.py  ← Reads conversations.json, reconstructs branches
├── renderer.py             ← Converts parsed data to GFM markdown strings
├── file_manager.py         ← Filenames, deduplication, image copying
└── models.py               ← Message, Branch, Conversation dataclasses
```

Replace with:
```
keromdizer.py          ← CLI entrypoint (argparse, thin wiring layer only)
├── parser_factory.py       ← detect_source(), build_parser() — TUI seam
├── conversation_parser.py  ← ChatGPT export parsing, reconstructs branches
├── deepseek_parser.py      ← DeepSeek export parsing (subclass of above)
├── renderer.py             ← Converts parsed data to GFM markdown strings
├── file_manager.py         ← Filenames, deduplication, image copying
└── models.py               ← Message, Branch, Conversation dataclasses
```

In the Key Files table, add two rows after `conversation_parser.py`:
```
| `deepseek_parser.py` | DeepSeek export parsing — subclasses `ConversationParser` |
| `parser_factory.py` | `detect_source()`, `build_parser()` — provider auto-detection; TUI entry point |
```

In the Commands section, add after the existing run examples:
```bash
# DeepSeek export (auto-detected)
python keromdizer.py /path/to/deepseek_data/ --output ~/notes/deepseek

# Force source explicitly
python keromdizer.py /path/to/export/ --source deepseek
```

**Step 5: Commit:**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for DeepSeek support and parser_factory"
```
