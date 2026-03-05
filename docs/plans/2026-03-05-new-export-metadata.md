# New Export Metadata Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Surface three new data points from the March 2026 ChatGPT export format: DALL-E image resolution (fixes 156 broken image refs), shared conversation flag, and voice audio count in metadata.

**Architecture:** Two new fields on `Conversation` (`is_shared`, `audio_count`); parser detects them during `parse()`; renderer conditionally adds metadata table rows; `copy_asset` gains a fallback search in `dalle-generations/`.

**Tech Stack:** Python 3.10+, pytest, stdlib only.

---

### Task 1: DALL-E image resolution — strip `file-service://` prefix in parser

**Files:**
- Modify: `conversation_parser.py:131-150` (`_parts_to_text`, `_extract_image_refs`)
- Test: `tests/test_parser.py`

**Step 1: Write the failing test**

Add to `tests/test_parser.py`:

```python
def test_extract_messages_handles_dalle_image(tmp_path):
    """file-service:// asset pointers (DALL-E) should be stripped and treated like sediment://."""
    mapping = {
        'a': {
            'id': 'a', 'parent': None, 'children': [],
            'message': {
                'author': {'role': 'assistant'},
                'content': {
                    'content_type': 'multimodal_text',
                    'parts': [
                        'Here is your image:',
                        {
                            'content_type': 'image_asset_pointer',
                            'asset_pointer': 'file-service://file-AbCdEfGhIj',
                            'size_bytes': 100,
                            'width': 512,
                            'height': 512,
                        }
                    ]
                },
                'create_time': 1700000010.0, 'metadata': {}
            }
        },
    }
    parser = ConversationParser(tmp_path)
    messages = parser._extract_messages(mapping, ['a'])
    assert len(messages) == 1
    assert 'file-AbCdEfGhIj' in messages[0].text
    assert '![image](assets/file-AbCdEfGhIj)' in messages[0].text
    assert messages[0].image_refs == ['file-AbCdEfGhIj']
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_parser.py::test_extract_messages_handles_dalle_image -v
```

Expected: FAIL — the image_ref will contain `file-service://file-AbCdEfGhIj` instead of `file-AbCdEfGhIj`.

**Step 3: Write minimal implementation**

In `conversation_parser.py`, update both `_parts_to_text` and `_extract_image_refs` to strip either URI prefix:

```python
def _parts_to_text(self, parts: list) -> str:
    segments = []
    for part in parts:
        if isinstance(part, str):
            segments.append(part)
        elif isinstance(part, dict):
            if part.get('content_type') == 'image_asset_pointer':
                file_id = self._strip_asset_uri(part.get('asset_pointer', ''))
                if file_id:
                    segments.append(f'![image](assets/{file_id})')
    return '\n\n'.join(segments)

def _extract_image_refs(self, parts: list) -> list[str]:
    refs = []
    for part in parts:
        if isinstance(part, dict) and part.get('content_type') == 'image_asset_pointer':
            file_id = self._strip_asset_uri(part.get('asset_pointer', ''))
            if file_id:
                refs.append(file_id)
    return refs

def _strip_asset_uri(self, uri: str) -> str:
    """Strip sediment:// or file-service:// URI prefix, returning bare file ID."""
    for prefix in ('sediment://', 'file-service://'):
        if uri.startswith(prefix):
            return uri[len(prefix):]
    return uri
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_parser.py::test_extract_messages_handles_dalle_image tests/test_parser.py::test_extract_messages_handles_multimodal -v
```

Expected: both PASS. The multimodal test still passes because `sediment://` is now handled via `_strip_asset_uri`.

**Step 5: Commit**

```bash
git add conversation_parser.py tests/test_parser.py
git commit -m "feat: strip file-service:// URI prefix for DALL-E image asset pointers"
```

---

### Task 2: DALL-E image resolution — search `dalle-generations/` in copy_asset

**Files:**
- Modify: `file_manager.py:72-82` (`copy_asset`)
- Test: `tests/test_file_manager.py`

**Step 1: Write the failing test**

Add to `tests/test_file_manager.py`:

```python
def test_copy_asset_finds_dalle_image(tmp_path):
    """copy_asset should find files in dalle-generations/ subdirectory."""
    export = tmp_path / 'export'
    export.mkdir()
    dalle_dir = export / 'dalle-generations'
    dalle_dir.mkdir()
    # DALL-E file lives in dalle-generations/, not in export root
    fake_img = dalle_dir / 'file-AbCdEfGhIj-some-uuid.webp'
    fake_img.write_bytes(b'fake webp data')

    output = tmp_path / 'output'
    fm = FileManager(output)
    result = fm.copy_asset(export, 'file-AbCdEfGhIj')
    assert result == 'file-AbCdEfGhIj-some-uuid.webp'
    assert (output / 'assets' / 'file-AbCdEfGhIj-some-uuid.webp').exists()
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_file_manager.py::test_copy_asset_finds_dalle_image -v
```

Expected: FAIL — `copy_asset` only searches export root, returns `None`.

**Step 3: Write minimal implementation**

In `file_manager.py`, update `copy_asset`:

```python
def copy_asset(self, export_folder: Path, file_id: str) -> str | None:
    """Find file by prefix in export_folder or dalle-generations/, copy to assets/, return filename."""
    search_dirs = [
        Path(export_folder),
        Path(export_folder) / 'dalle-generations',
    ]
    for search_dir in search_dirs:
        matches = list(search_dir.glob(f'{file_id}*'))
        if matches:
            src = matches[0]
            self.assets_dir.mkdir(parents=True, exist_ok=True)
            dst = self.assets_dir / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
            return src.name
    return None
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_file_manager.py -v
```

Expected: all file_manager tests PASS.

**Step 5: Commit**

```bash
git add file_manager.py tests/test_file_manager.py
git commit -m "feat: resolve DALL-E images from dalle-generations/ subdirectory"
```

---

### Task 3: Add `is_shared` and `audio_count` fields to Conversation model

**Files:**
- Modify: `models.py`

These are simple dataclass fields with defaults — no tests needed (the existing dataclass tests will break if defaults are missing, which we'll catch).

**Step 1: Add fields to `Conversation`**

In `models.py`, update `Conversation`:

```python
@dataclass
class Conversation:
    id: str
    title: str
    create_time: Optional[float]
    update_time: Optional[float]
    model_slug: Optional[str]
    branches: list[Branch]
    is_shared: bool = False
    audio_count: int = 0
```

**Step 2: Verify existing tests still pass**

```bash
pytest tests/ -v
```

Expected: all 27 tests PASS. The new fields have defaults so existing `Conversation(...)` call sites are unaffected.

**Step 3: Commit**

```bash
git add models.py
git commit -m "feat: add is_shared and audio_count fields to Conversation model"
```

---

### Task 4: Detect shared conversations and voice audio in parser

**Files:**
- Modify: `conversation_parser.py` (`parse`, `_parse_conversation`)
- Test: `tests/test_parser.py`

**Step 1: Write the failing tests**

Add to `tests/test_parser.py`:

```python
def test_parse_marks_shared_conversation(tmp_path):
    """Conversations listed in shared_conversations.json get is_shared=True."""
    conv_data = [{
        'id': 'conv-shared-1',
        'title': 'Shared Chat',
        'mapping': {
            'a': {'id': 'a', 'parent': None, 'children': ['b'], 'message': None},
            'b': {
                'id': 'b', 'parent': 'a', 'children': [],
                'message': {
                    'author': {'role': 'user'},
                    'content': {'content_type': 'text', 'parts': ['hello']},
                    'create_time': None, 'metadata': {}
                }
            },
        },
        'current_node': 'b',
        'create_time': 1700000000.0,
        'update_time': 1700000100.0,
        'default_model_slug': 'gpt-4o',
    }]
    export = _make_export(tmp_path, conv_data)
    (export / 'shared_conversations.json').write_text(
        json.dumps([{'conversation_id': 'conv-shared-1', 'id': 'share-abc', 'title': 'Shared Chat', 'is_anonymous': True}]),
        encoding='utf-8',
    )
    parser = ConversationParser(export)
    convs = parser.parse()
    assert convs[0].is_shared is True


def test_parse_not_shared_when_absent(tmp_path):
    """Conversations not in shared_conversations.json get is_shared=False."""
    conv_data = [{
        'id': 'conv-private-1',
        'title': 'Private Chat',
        'mapping': {
            'a': {'id': 'a', 'parent': None, 'children': ['b'], 'message': None},
            'b': {
                'id': 'b', 'parent': 'a', 'children': [],
                'message': {
                    'author': {'role': 'user'},
                    'content': {'content_type': 'text', 'parts': ['hello']},
                    'create_time': None, 'metadata': {}
                }
            },
        },
        'current_node': 'b',
        'create_time': 1700000000.0,
        'update_time': 1700000100.0,
        'default_model_slug': 'gpt-4o',
    }]
    export = _make_export(tmp_path, conv_data)
    # No shared_conversations.json — should work fine, is_shared stays False
    parser = ConversationParser(export)
    convs = parser.parse()
    assert convs[0].is_shared is False


def test_parse_counts_audio_recordings(tmp_path):
    """Conversations with an audio/ subfolder get audio_count set."""
    conv_id = 'conv-voice-1'
    conv_data = [{
        'id': conv_id,
        'title': 'Voice Chat',
        'mapping': {
            'a': {'id': 'a', 'parent': None, 'children': ['b'], 'message': None},
            'b': {
                'id': 'b', 'parent': 'a', 'children': [],
                'message': {
                    'author': {'role': 'user'},
                    'content': {'content_type': 'text', 'parts': ['hi']},
                    'create_time': None, 'metadata': {}
                }
            },
        },
        'current_node': 'b',
        'create_time': 1700000000.0,
        'update_time': 1700000100.0,
        'default_model_slug': 'gpt-4o',
    }]
    export = _make_export(tmp_path, conv_data)
    audio_dir = export / conv_id / 'audio'
    audio_dir.mkdir(parents=True)
    (audio_dir / 'recording1.wav').write_bytes(b'')
    (audio_dir / 'recording2.wav').write_bytes(b'')
    parser = ConversationParser(export)
    convs = parser.parse()
    assert convs[0].audio_count == 2
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_parser.py::test_parse_marks_shared_conversation tests/test_parser.py::test_parse_not_shared_when_absent tests/test_parser.py::test_parse_counts_audio_recordings -v
```

Expected: all FAIL — `is_shared` always `False`, `audio_count` always `0`.

**Step 3: Write minimal implementation**

In `conversation_parser.py`, update `parse` to load shared IDs, and `_parse_conversation` to detect audio:

```python
def parse(self) -> list[Conversation]:
    data = self._load_raw_conversations()
    shared_ids = self._load_shared_ids()

    conversations = []
    for raw in data:
        try:
            conv = self._parse_conversation(raw)
            if conv is not None:
                conv.is_shared = conv.id in shared_ids
                conversations.append(conv)
        except Exception as e:
            title = raw.get('title', 'unknown')
            print(f"Warning: skipping conversation '{title}': {e}")
    return conversations

def _load_shared_ids(self) -> set[str]:
    """Return set of conversation IDs listed in shared_conversations.json, or empty set."""
    path = self.export_folder / 'shared_conversations.json'
    if not path.exists():
        return set()
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    return {entry['conversation_id'] for entry in data if 'conversation_id' in entry}
```

In `_parse_conversation`, add audio count detection. Add these two lines just before the `return Conversation(...)` call:

```python
conv_id = raw.get('id') or raw.get('conversation_id', '')
audio_dir = self.export_folder / conv_id / 'audio'
audio_count = len(list(audio_dir.glob('*.wav'))) if audio_dir.is_dir() else 0

return Conversation(
    id=conv_id,
    title=raw.get('title', 'Untitled'),
    create_time=raw.get('create_time'),
    update_time=raw.get('update_time'),
    model_slug=raw.get('default_model_slug'),
    branches=final_branches,
    audio_count=audio_count,
)
```

Note: remove the original `id=raw.get('id') or raw.get('conversation_id', ''),` line since `conv_id` now holds that value.

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_parser.py -v
```

Expected: all parser tests PASS (30 total now).

**Step 5: Commit**

```bash
git add conversation_parser.py tests/test_parser.py
git commit -m "feat: detect shared conversations and voice audio count during parse"
```

---

### Task 5: Render `Shared` and `Audio` rows in metadata table

**Files:**
- Modify: `renderer.py`
- Test: `tests/test_renderer.py`

**Step 1: Write the failing tests**

Add to `tests/test_renderer.py`:

```python
def test_render_shared_flag():
    conv = _make_conv([_make_branch([Message(role='user', text='hi')])])
    conv.is_shared = True
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '| Shared | Yes |' in md


def test_render_no_shared_flag_when_false():
    conv = _make_conv([_make_branch([Message(role='user', text='hi')])])
    # is_shared defaults to False
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '| Shared |' not in md


def test_render_audio_count():
    conv = _make_conv([_make_branch([Message(role='user', text='hi')])])
    conv.audio_count = 5
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '| Audio | 5 recordings |' in md


def test_render_no_audio_row_when_zero():
    conv = _make_conv([_make_branch([Message(role='user', text='hi')])])
    # audio_count defaults to 0
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '| Audio |' not in md
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_renderer.py::test_render_shared_flag tests/test_renderer.py::test_render_no_shared_flag_when_false tests/test_renderer.py::test_render_audio_count tests/test_renderer.py::test_render_no_audio_row_when_zero -v
```

Expected: all FAIL — neither row appears yet.

**Step 3: Write minimal implementation**

In `renderer.py`, update the metadata table block:

```python
lines += [
    '| Field | Value |',
    '|---|---|',
    f'| Date | {date_str} |',
    f'| Model | {conversation.model_slug or "unknown"} |',
    f'| Conversation ID | {conversation.id} |',
]
if total_branches > 1:
    lines.append(f'| Branch | {branch.branch_index} of {total_branches} |')
if conversation.is_shared:
    lines.append('| Shared | Yes |')
if conversation.audio_count > 0:
    lines.append(f'| Audio | {conversation.audio_count} recordings |')
lines.append('')
```

**Step 4: Run all tests**

```bash
pytest tests/ -v
```

Expected: all 35 tests PASS.

**Step 5: Commit**

```bash
git add renderer.py tests/test_renderer.py
git commit -m "feat: add Shared and Audio metadata rows to rendered markdown"
```

---

### Task 6: Smoke test against real export and push

**Step 1: Run against new export (dry-run)**

```bash
source .venv/bin/activate
python keromdizer.py "/home/matt/Downloads/27acb0dfd0a3c5fc91e10df3ec41412e00ff7879d440e4504e23ce0810ffbfff-2026-03-03-17-52-25-947f2c39f860403c8ca60da48482d11c" --dry-run 2>&1 | grep -E "(Warning|would write|Done|Dry)" | tail -20
```

Expected: fewer "Warning: image not found" messages for `file-service://` URIs, same ~664 file count.

**Step 2: Check a DALL-E conversation renders correctly**

```bash
python keromdizer.py "/home/matt/Downloads/27acb0dfd0a3c5fc91e10df3ec41412e00ff7879d440e4504e23ce0810ffbfff-2026-03-03-17-52-25-947f2c39f860403c8ca60da48482d11c" --output /tmp/kero-test 2>&1 | head -5
grep -l "dalle\|webp" /tmp/kero-test/assets/ | head -3
```

**Step 3: Commit design doc and push branch**

```bash
git add docs/
git commit -m "docs: add design doc for new export metadata features"
```

Then use the `/commit-push-pr` skill to push and open a PR.
