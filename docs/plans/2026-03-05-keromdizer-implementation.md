# KeroMDizer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python CLI tool that converts a ChatGPT data export folder into GFM markdown files, one per conversation branch.

**Architecture:** Three internal classes (`ConversationParser`, `MarkdownRenderer`, `FileManager`) wired together by a thin CLI entrypoint (`keromdizer.py`). No external dependencies beyond pytest for testing. Designed so a TUI layer can be added later by calling the same classes directly.

**Tech Stack:** Python 3.10+, stdlib only (`json`, `pathlib`, `dataclasses`, `argparse`, `shutil`, `re`, `datetime`), pytest for tests.

---

## Project Structure (target state)

```
KeroMDizer/
├── keromdizer.py              ← CLI entrypoint
├── conversation_parser.py     ← ConversationParser class
├── renderer.py                ← MarkdownRenderer class
├── file_manager.py            ← FileManager class
├── models.py                  ← Message, Branch, Conversation dataclasses
├── requirements-dev.txt       ← pytest only
└── tests/
    ├── fixtures/
    │   └── sample_conversations.json
    ├── test_parser.py
    ├── test_renderer.py
    └── test_file_manager.py
```

---

## Task 1: Project Bootstrap

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/fixtures/sample_conversations.json`

**Step 1: Create dev requirements**

```
pytest
```

Save as `requirements-dev.txt`.

**Step 2: Install**

```bash
pip install -r requirements-dev.txt
```

**Step 3: Create test fixture — minimal conversations.json**

This fixture covers the key scenarios: a conversation with two branches, an image reference, and a code block in assistant text.

```json
[
  {
    "id": "conv-001",
    "conversation_id": "conv-001",
    "title": "Test: Python Basics",
    "create_time": 1700000000.0,
    "update_time": 1700000100.0,
    "default_model_slug": "gpt-4o",
    "current_node": "node-d",
    "mapping": {
      "node-a": {
        "id": "node-a",
        "parent": null,
        "children": ["node-b"],
        "message": {
          "id": "node-a",
          "author": {"role": "system"},
          "content": {"content_type": "text", "parts": ["You are a helpful assistant."]},
          "create_time": 1700000000.0,
          "metadata": {}
        }
      },
      "node-b": {
        "id": "node-b",
        "parent": "node-a",
        "children": ["node-c", "node-e"],
        "message": {
          "id": "node-b",
          "author": {"role": "user"},
          "content": {"content_type": "text", "parts": ["How do I print hello world in Python?"]},
          "create_time": 1700000010.0,
          "metadata": {}
        }
      },
      "node-c": {
        "id": "node-c",
        "parent": "node-b",
        "children": ["node-d"],
        "message": {
          "id": "node-c",
          "author": {"role": "assistant"},
          "content": {"content_type": "text", "parts": ["Use the print function:\n\n```python\nprint('Hello, World!')\n```"]},
          "create_time": 1700000020.0,
          "metadata": {}
        }
      },
      "node-d": {
        "id": "node-d",
        "parent": "node-c",
        "children": [],
        "message": {
          "id": "node-d",
          "author": {"role": "user"},
          "content": {"content_type": "text", "parts": ["Thanks! What about printing a variable?"]},
          "create_time": 1700000030.0,
          "metadata": {}
        }
      },
      "node-e": {
        "id": "node-e",
        "parent": "node-b",
        "children": [],
        "message": {
          "id": "node-e",
          "author": {"role": "assistant"},
          "content": {"content_type": "text", "parts": ["Simply use: `print('Hello, World!')`"]},
          "create_time": 1700000020.0,
          "metadata": {}
        }
      }
    }
  },
  {
    "id": "conv-002",
    "conversation_id": "conv-002",
    "title": "Test: With Image",
    "create_time": 1700001000.0,
    "update_time": 1700001100.0,
    "default_model_slug": "gpt-4o",
    "current_node": "img-c",
    "mapping": {
      "img-a": {
        "id": "img-a",
        "parent": null,
        "children": ["img-b"],
        "message": {
          "id": "img-a",
          "author": {"role": "system"},
          "content": {"content_type": "text", "parts": [""]},
          "create_time": 1700001000.0,
          "metadata": {}
        }
      },
      "img-b": {
        "id": "img-b",
        "parent": "img-a",
        "children": ["img-c"],
        "message": {
          "id": "img-b",
          "author": {"role": "user"},
          "content": {
            "content_type": "multimodal_text",
            "parts": [
              "What is in this image?",
              {
                "content_type": "image_asset_pointer",
                "asset_pointer": "sediment://file_abc123",
                "size_bytes": 12345,
                "width": 800,
                "height": 600
              }
            ]
          },
          "create_time": 1700001010.0,
          "metadata": {}
        }
      },
      "img-c": {
        "id": "img-c",
        "parent": "img-b",
        "children": [],
        "message": {
          "id": "img-c",
          "author": {"role": "assistant"},
          "content": {"content_type": "text", "parts": ["The image shows a cat sitting on a windowsill."]},
          "create_time": 1700001020.0,
          "metadata": {}
        }
      }
    }
  },
  {
    "id": "conv-003",
    "conversation_id": "conv-003",
    "title": "Test: Empty (no user messages)",
    "create_time": 1700002000.0,
    "update_time": 1700002000.0,
    "default_model_slug": "gpt-4o",
    "current_node": "empty-b",
    "mapping": {
      "empty-a": {
        "id": "empty-a",
        "parent": null,
        "children": ["empty-b"],
        "message": {
          "id": "empty-a",
          "author": {"role": "system"},
          "content": {"content_type": "text", "parts": [""]},
          "create_time": 1700002000.0,
          "metadata": {}
        }
      },
      "empty-b": {
        "id": "empty-b",
        "parent": "empty-a",
        "children": [],
        "message": null
      }
    }
  }
]
```

Save as `tests/fixtures/sample_conversations.json`.

**Step 4: Verify pytest runs (no tests yet)**

```bash
pytest tests/ -v
```

Expected: `no tests ran` or `collected 0 items`

**Step 5: Commit**

```bash
git init
git add requirements-dev.txt tests/fixtures/sample_conversations.json docs/
git commit -m "chore: project bootstrap with fixtures and design docs"
```

---

## Task 2: Data Models

**Files:**
- Create: `models.py`
- Create: `tests/test_parser.py` (import only, to verify models work)

**Step 1: Write the failing import test**

In `tests/test_parser.py`:

```python
from models import Message, Branch, Conversation


def test_message_creation():
    msg = Message(role='user', text='hello')
    assert msg.role == 'user'
    assert msg.text == 'hello'
    assert msg.image_refs == []


def test_conversation_creation():
    msg = Message(role='user', text='hi')
    branch = Branch(messages=[msg], branch_index=1)
    conv = Conversation(
        id='abc',
        title='Test',
        create_time=1700000000.0,
        update_time=1700000100.0,
        model_slug='gpt-4o',
        branches=[branch],
    )
    assert conv.id == 'abc'
    assert len(conv.branches) == 1
    assert conv.branches[0].branch_index == 1
```

**Step 2: Run to verify it fails**

```bash
pytest tests/test_parser.py -v
```

Expected: `ModuleNotFoundError: No module named 'models'`

**Step 3: Implement models.py**

```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Message:
    role: str  # 'user' or 'assistant'
    text: str
    create_time: Optional[float] = None
    image_refs: list[str] = field(default_factory=list)


@dataclass
class Branch:
    messages: list[Message]
    branch_index: int  # 1 = main thread (current_node path), 2+ = alternates


@dataclass
class Conversation:
    id: str
    title: str
    create_time: Optional[float]
    update_time: Optional[float]
    model_slug: Optional[str]
    branches: list[Branch]
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_parser.py -v
```

Expected: 2 tests PASS

**Step 5: Commit**

```bash
git add models.py tests/test_parser.py
git commit -m "feat: add Message, Branch, Conversation dataclasses"
```

---

## Task 3: ConversationParser — Tree Traversal

**Files:**
- Create: `conversation_parser.py`
- Modify: `tests/test_parser.py`

The core algorithm: find all leaf nodes (empty `children`), trace each to root via `parent` pointers, identify the main branch (path containing `current_node`).

**Step 1: Write failing tests for tree traversal**

Add to `tests/test_parser.py`:

```python
import json
from pathlib import Path
from conversation_parser import ConversationParser

FIXTURE = Path(__file__).parent / 'fixtures' / 'sample_conversations.json'


def test_parse_returns_list():
    parser = ConversationParser(FIXTURE.parent.parent)
    # We need to point to the folder containing conversations.json
    # For tests we'll use a temp dir approach — see below


def _make_export(tmp_path, conversations):
    """Helper: write conversations.json to a temp folder."""
    (tmp_path / 'conversations.json').write_text(
        json.dumps(conversations), encoding='utf-8'
    )
    return tmp_path


def test_trace_to_root_simple(tmp_path):
    mapping = {
        'a': {'id': 'a', 'parent': None, 'children': ['b'], 'message': None},
        'b': {'id': 'b', 'parent': 'a', 'children': ['c'], 'message': None},
        'c': {'id': 'c', 'parent': 'b', 'children': [], 'message': None},
    }
    parser = ConversationParser(tmp_path)
    path = parser._trace_to_root(mapping, 'c')
    assert path == ['a', 'b', 'c']


def test_find_leaf_nodes(tmp_path):
    mapping = {
        'a': {'id': 'a', 'parent': None, 'children': ['b', 'c'], 'message': None},
        'b': {'id': 'b', 'parent': 'a', 'children': [], 'message': None},
        'c': {'id': 'c', 'parent': 'a', 'children': [], 'message': None},
    }
    parser = ConversationParser(tmp_path)
    leaves = parser._find_leaf_ids(mapping)
    assert set(leaves) == {'b', 'c'}


def test_parse_fixture_conversation_count(tmp_path):
    with open(FIXTURE) as f:
        data = json.load(f)
    export = _make_export(tmp_path, data)
    parser = ConversationParser(export)
    convs = parser.parse()
    # conv-003 has no user/assistant messages so should be skipped
    assert len(convs) == 2


def test_parse_fixture_branch_count(tmp_path):
    with open(FIXTURE) as f:
        data = json.load(f)
    export = _make_export(tmp_path, data)
    parser = ConversationParser(export)
    convs = parser.parse()
    conv = next(c for c in convs if c.id == 'conv-001')
    # Two leaves: node-d (main) and node-e (alternate)
    assert len(conv.branches) == 2


def test_main_branch_is_index_1(tmp_path):
    with open(FIXTURE) as f:
        data = json.load(f)
    export = _make_export(tmp_path, data)
    parser = ConversationParser(export)
    convs = parser.parse()
    conv = next(c for c in convs if c.id == 'conv-001')
    main = conv.branches[0]
    assert main.branch_index == 1
    # Main branch ends at node-d (the current_node), so has 3 messages: user, assistant, user
    assert len(main.messages) == 3
```

**Step 2: Run to verify they fail**

```bash
pytest tests/test_parser.py -v
```

Expected: `ModuleNotFoundError: No module named 'conversation_parser'`

**Step 3: Implement ConversationParser (tree traversal only)**

```python
import json
from pathlib import Path
from models import Conversation, Branch, Message


class ConversationParser:
    def __init__(self, export_folder: Path):
        self.export_folder = Path(export_folder)
        self._conversations_file = self.export_folder / 'conversations.json'

    def parse(self) -> list[Conversation]:
        if not self._conversations_file.exists():
            raise FileNotFoundError(
                f"conversations.json not found in {self.export_folder}"
            )
        with open(self._conversations_file, encoding='utf-8') as f:
            data = json.load(f)

        conversations = []
        for raw in data:
            try:
                conv = self._parse_conversation(raw)
                if conv is not None:
                    conversations.append(conv)
            except Exception as e:
                title = raw.get('title', 'unknown')
                print(f"Warning: skipping conversation '{title}': {e}")
        return conversations

    def _parse_conversation(self, raw: dict) -> Conversation | None:
        mapping = raw.get('mapping', {})
        current_node = raw.get('current_node')

        leaf_ids = self._find_leaf_ids(mapping)
        if not leaf_ids:
            return None

        # Trace main branch first (contains current_node)
        main_path = self._trace_to_root(mapping, current_node) if current_node else []
        main_path_set = set(main_path)

        branches = []
        seen_paths = set()

        for leaf_id in leaf_ids:
            path = self._trace_to_root(mapping, leaf_id)
            path_key = tuple(path)
            if path_key in seen_paths:
                continue
            seen_paths.add(path_key)

            messages = self._extract_messages(mapping, path)
            if not messages:
                continue

            is_main = bool(main_path_set & set(path)) and (
                current_node in path or leaf_id == current_node
            )
            branches.append((is_main, path_key, messages))

        if not branches:
            return None

        # Sort: main branch first
        branches.sort(key=lambda x: (0 if x[0] else 1))
        final_branches = [
            Branch(messages=msgs, branch_index=i + 1)
            for i, (_, _, msgs) in enumerate(branches)
        ]

        return Conversation(
            id=raw.get('id') or raw.get('conversation_id', ''),
            title=raw.get('title', 'Untitled'),
            create_time=raw.get('create_time'),
            update_time=raw.get('update_time'),
            model_slug=raw.get('default_model_slug'),
            branches=final_branches,
        )

    def _find_leaf_ids(self, mapping: dict) -> list[str]:
        return [nid for nid, node in mapping.items() if not node.get('children')]

    def _trace_to_root(self, mapping: dict, start_id: str) -> list[str]:
        path = []
        node_id = start_id
        seen = set()
        while node_id and node_id not in seen:
            seen.add(node_id)
            path.append(node_id)
            node_id = mapping.get(node_id, {}).get('parent')
        path.reverse()
        return path

    def _extract_messages(self, mapping: dict, path_ids: list[str]) -> list[Message]:
        # Implemented in Task 4
        return []
```

**Step 4: Run tests**

```bash
pytest tests/test_parser.py -v
```

Expected: tree traversal tests PASS; `test_parse_fixture_branch_count` and `test_main_branch_is_index_1` will FAIL (messages not extracted yet — that's fine, Task 4).

**Step 5: Commit**

```bash
git add conversation_parser.py tests/test_parser.py
git commit -m "feat: ConversationParser tree traversal and branch reconstruction"
```

---

## Task 4: ConversationParser — Message Extraction

**Files:**
- Modify: `conversation_parser.py` (implement `_extract_messages`)
- Modify: `tests/test_parser.py`

**Step 1: Write failing tests for message extraction**

Add to `tests/test_parser.py`:

```python
def test_extract_messages_filters_system_and_tool(tmp_path):
    mapping = {
        'a': {
            'id': 'a', 'parent': None, 'children': ['b'],
            'message': {
                'author': {'role': 'system'},
                'content': {'content_type': 'text', 'parts': ['system prompt']},
                'create_time': None, 'metadata': {}
            }
        },
        'b': {
            'id': 'b', 'parent': 'a', 'children': [],
            'message': {
                'author': {'role': 'user'},
                'content': {'content_type': 'text', 'parts': ['Hello']},
                'create_time': 1700000010.0, 'metadata': {}
            }
        },
    }
    parser = ConversationParser(tmp_path)
    messages = parser._extract_messages(mapping, ['a', 'b'])
    assert len(messages) == 1
    assert messages[0].role == 'user'
    assert messages[0].text == 'Hello'


def test_extract_messages_filters_non_text_content(tmp_path):
    mapping = {
        'a': {
            'id': 'a', 'parent': None, 'children': ['b'],
            'message': {
                'author': {'role': 'assistant'},
                'content': {'content_type': 'thoughts', 'thoughts': [{'summary': 'thinking', 'content': 'I think'}]},
                'create_time': None, 'metadata': {}
            }
        },
        'b': {
            'id': 'b', 'parent': 'a', 'children': [],
            'message': {
                'author': {'role': 'assistant'},
                'content': {'content_type': 'text', 'parts': ['Here is the answer.']},
                'create_time': 1700000020.0, 'metadata': {}
            }
        },
    }
    parser = ConversationParser(tmp_path)
    messages = parser._extract_messages(mapping, ['a', 'b'])
    assert len(messages) == 1
    assert messages[0].text == 'Here is the answer.'


def test_extract_messages_handles_multimodal(tmp_path):
    mapping = {
        'a': {
            'id': 'a', 'parent': None, 'children': [],
            'message': {
                'author': {'role': 'user'},
                'content': {
                    'content_type': 'multimodal_text',
                    'parts': [
                        'What is this?',
                        {
                            'content_type': 'image_asset_pointer',
                            'asset_pointer': 'sediment://file_abc123',
                            'size_bytes': 100,
                            'width': 100,
                            'height': 100,
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
    assert 'What is this?' in messages[0].text
    assert 'file_abc123' in messages[0].text
    assert messages[0].image_refs == ['file_abc123']


def test_parse_fixture_message_content(tmp_path):
    with open(FIXTURE) as f:
        data = json.load(f)
    export = _make_export(tmp_path, data)
    parser = ConversationParser(export)
    convs = parser.parse()
    conv = next(c for c in convs if c.id == 'conv-001')
    main = conv.branches[0]
    # Main branch: user -> assistant -> user
    assert main.messages[0].role == 'user'
    assert 'hello world' in main.messages[0].text.lower()
    assert main.messages[1].role == 'assistant'
    assert '```python' in main.messages[1].text
    assert main.messages[2].role == 'user'


def test_parse_fixture_image_refs(tmp_path):
    with open(FIXTURE) as f:
        data = json.load(f)
    export = _make_export(tmp_path, data)
    parser = ConversationParser(export)
    convs = parser.parse()
    conv = next(c for c in convs if c.id == 'conv-002')
    user_msg = conv.branches[0].messages[0]
    assert 'file_abc123' in user_msg.image_refs
    assert 'assets/file_abc123' in user_msg.text
```

**Step 2: Run to verify failures**

```bash
pytest tests/test_parser.py::test_extract_messages_filters_system_and_tool \
       tests/test_parser.py::test_parse_fixture_message_content -v
```

Expected: FAIL (messages list is always empty)

**Step 3: Implement `_extract_messages` and helpers**

Replace the stub in `conversation_parser.py`:

```python
    def _extract_messages(self, mapping: dict, path_ids: list[str]) -> list[Message]:
        messages = []
        for nid in path_ids:
            node = mapping.get(nid, {})
            msg = node.get('message')
            if not msg:
                continue
            role = msg.get('author', {}).get('role')
            if role not in ('user', 'assistant'):
                continue
            content = msg.get('content', {})
            if not isinstance(content, dict):
                continue
            content_type = content.get('content_type')
            if content_type not in ('text', 'multimodal_text'):
                continue
            parts = content.get('parts') or []
            text = self._parts_to_text(parts)
            image_refs = self._extract_image_refs(parts)
            if not text.strip() and not image_refs:
                continue
            messages.append(Message(
                role=role,
                text=text,
                create_time=msg.get('create_time'),
                image_refs=image_refs,
            ))
        return messages

    def _parts_to_text(self, parts: list) -> str:
        segments = []
        for part in parts:
            if isinstance(part, str):
                segments.append(part)
            elif isinstance(part, dict):
                if part.get('content_type') == 'image_asset_pointer':
                    file_id = part.get('asset_pointer', '').replace('sediment://', '')
                    segments.append(f'![image](assets/{file_id})')
        return '\n'.join(segments)

    def _extract_image_refs(self, parts: list) -> list[str]:
        refs = []
        for part in parts:
            if isinstance(part, dict) and part.get('content_type') == 'image_asset_pointer':
                file_id = part.get('asset_pointer', '').replace('sediment://', '')
                if file_id:
                    refs.append(file_id)
        return refs
```

**Step 4: Run all parser tests**

```bash
pytest tests/test_parser.py -v
```

Expected: all tests PASS

**Step 5: Commit**

```bash
git add conversation_parser.py tests/test_parser.py
git commit -m "feat: ConversationParser message extraction with multimodal support"
```

---

## Task 5: MarkdownRenderer

**Files:**
- Create: `renderer.py`
- Create: `tests/test_renderer.py`

**Step 1: Write failing tests**

```python
from datetime import timezone
from models import Message, Branch, Conversation
from renderer import MarkdownRenderer


def _make_conv(branches, model='gpt-4o', create_time=1700000000.0, update_time=1700000100.0):
    return Conversation(
        id='test-id-001',
        title='My Test Chat',
        create_time=create_time,
        update_time=update_time,
        model_slug=model,
        branches=branches,
    )


def _make_branch(messages, index=1):
    return Branch(messages=messages, branch_index=index)


def test_render_contains_title():
    conv = _make_conv([_make_branch([Message(role='user', text='hi')])])
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '# My Test Chat' in md


def test_render_metadata_table_single_branch():
    conv = _make_conv([_make_branch([Message(role='user', text='hi')])])
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '| Date | 2023-11-14 |' in md
    assert '| Model | gpt-4o |' in md
    assert '| Conversation ID | test-id-001 |' in md
    # No Branch row for single-branch conversations
    assert '| Branch |' not in md


def test_render_metadata_table_multi_branch():
    branch1 = _make_branch([Message(role='user', text='hi')], index=1)
    branch2 = _make_branch([Message(role='assistant', text='hello')], index=2)
    conv = _make_conv([branch1, branch2])
    r = MarkdownRenderer()
    md = r.render(conv, branch1)
    assert '| Branch | 1 of 2 |' in md


def test_render_user_message():
    msg = Message(role='user', text='How do I sort a list?')
    conv = _make_conv([_make_branch([msg])])
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '### 👤 User' in md
    assert 'How do I sort a list?' in md


def test_render_assistant_message():
    msg = Message(role='assistant', text='Use `list.sort()`')
    conv = _make_conv([_make_branch([msg])])
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '### 🤖 Assistant' in md
    assert 'Use `list.sort()`' in md


def test_render_preserves_code_fence():
    text = "Here's a function:\n\n```python\ndef hello():\n    print('hi')\n```"
    msg = Message(role='assistant', text=text)
    conv = _make_conv([_make_branch([msg])])
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '```python' in md
    assert "def hello():" in md


def test_render_messages_separated_by_hr():
    msgs = [
        Message(role='user', text='Question'),
        Message(role='assistant', text='Answer'),
    ]
    conv = _make_conv([_make_branch(msgs)])
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    # At least two horizontal rules between/around messages
    assert md.count('\n---\n') >= 2


def test_render_unknown_model():
    conv = _make_conv([_make_branch([Message(role='user', text='hi')])], model=None)
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '| Model | unknown |' in md
```

**Step 2: Run to verify failures**

```bash
pytest tests/test_renderer.py -v
```

Expected: `ModuleNotFoundError: No module named 'renderer'`

**Step 3: Implement renderer.py**

```python
from datetime import datetime, timezone
from models import Conversation, Branch


class MarkdownRenderer:
    def render(self, conversation: Conversation, branch: Branch) -> str:
        lines = []

        # Metadata table
        date_str = self._format_date(conversation.create_time)
        total_branches = len(conversation.branches)
        lines += [
            '| Field | Value |',
            '|---|---|',
            f'| Date | {date_str} |',
            f'| Model | {conversation.model_slug or "unknown"} |',
            f'| Conversation ID | {conversation.id} |',
        ]
        if total_branches > 1:
            lines.append(f'| Branch | {branch.branch_index} of {total_branches} |')
        lines.append('')

        # Title
        lines += [f'# {conversation.title}', '']

        # Messages
        for msg in branch.messages:
            lines.append('---')
            lines.append('')
            header = '### 👤 User' if msg.role == 'user' else '### 🤖 Assistant'
            lines += [header, '', msg.text, '']

        lines += ['---', '']

        return '\n'.join(lines)

    def _format_date(self, timestamp: float | None) -> str:
        if not timestamp:
            return 'unknown'
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return dt.strftime('%Y-%m-%d')
```

**Step 4: Run all renderer tests**

```bash
pytest tests/test_renderer.py -v
```

Expected: all PASS

**Step 5: Commit**

```bash
git add renderer.py tests/test_renderer.py
git commit -m "feat: MarkdownRenderer converts conversations to GFM markdown"
```

---

## Task 6: FileManager — Filename Sanitization

**Files:**
- Create: `file_manager.py`
- Create: `tests/test_file_manager.py`

**Step 1: Write failing tests**

```python
import json
from pathlib import Path
from models import Message, Branch, Conversation
from file_manager import FileManager


def _make_conv(id_, title, create_time=1700000000.0, update_time=1700000100.0, branch_count=1):
    branches = [Branch(messages=[Message(role='user', text='hi')], branch_index=i+1)
                for i in range(branch_count)]
    return Conversation(
        id=id_, title=title,
        create_time=create_time, update_time=update_time,
        model_slug='gpt-4o', branches=branches,
    )


def test_sanitize_filename_basic(tmp_path):
    fm = FileManager(tmp_path)
    assert fm.sanitize_filename('Hello World') == 'Hello_World'


def test_sanitize_filename_special_chars(tmp_path):
    fm = FileManager(tmp_path)
    result = fm.sanitize_filename('Branch · Casper: Setup/Plan?')
    assert '/' not in result
    assert ':' not in result
    assert '?' not in result
    assert '·' not in result


def test_sanitize_filename_truncates_at_80(tmp_path):
    fm = FileManager(tmp_path)
    long_title = 'A' * 100
    assert len(fm.sanitize_filename(long_title)) <= 80


def test_make_filename_single_branch(tmp_path):
    fm = FileManager(tmp_path)
    conv = _make_conv('abc', 'My Chat', branch_count=1)
    name = fm.make_filename(conv, conv.branches[0])
    assert name == '2023-11-14_My_Chat.md'


def test_make_filename_multi_branch_main(tmp_path):
    fm = FileManager(tmp_path)
    conv = _make_conv('abc', 'My Chat', branch_count=3)
    # Branch 1 (main) gets no suffix
    name = fm.make_filename(conv, conv.branches[0])
    assert name == '2023-11-14_My_Chat.md'


def test_make_filename_multi_branch_alternate(tmp_path):
    fm = FileManager(tmp_path)
    conv = _make_conv('abc', 'My Chat', branch_count=3)
    name = fm.make_filename(conv, conv.branches[1])
    assert name == '2023-11-14_My_Chat_branch-2.md'


def test_make_filename_collision_disambiguation(tmp_path):
    fm = FileManager(tmp_path)
    conv1 = _make_conv('id-aabbcc01', 'Same Title', branch_count=1)
    conv2 = _make_conv('id-xxyyzz02', 'Same Title', branch_count=1)
    name1 = fm.make_filename(conv1, conv1.branches[0])
    name2 = fm.make_filename(conv2, conv2.branches[0])
    assert name1 != name2
    assert 'id-aabb' in name2 or 'id-xxyy' in name2
```

**Step 2: Run to verify failures**

```bash
pytest tests/test_file_manager.py -v
```

Expected: `ModuleNotFoundError: No module named 'file_manager'`

**Step 3: Implement FileManager (filename methods only)**

```python
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from models import Conversation, Branch


class FileManager:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.assets_dir = self.output_dir / 'assets'
        self.manifest_path = self.output_dir / 'manifest.json'
        self._manifest: dict = self._load_manifest()
        self._used_filenames: set[str] = set()

    def _load_manifest(self) -> dict:
        if self.manifest_path.exists():
            with open(self.manifest_path, encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_manifest(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, 'w', encoding='utf-8') as f:
            json.dump(self._manifest, f, indent=2)

    def needs_update(self, conversation: Conversation) -> bool:
        entry = self._manifest.get(conversation.id)
        if not entry:
            return True
        return (conversation.update_time or 0) > entry.get('update_time', 0)

    def sanitize_filename(self, title: str) -> str:
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f·•\u2019\u2018]', '_', title)
        safe = re.sub(r'[\s_]+', '_', safe)
        safe = safe.strip('_')
        return safe[:80]

    def make_filename(self, conversation: Conversation, branch: Branch) -> str:
        date_str = self._format_date(conversation.create_time)
        safe_title = self.sanitize_filename(conversation.title)
        total = len(conversation.branches)

        if total > 1 and branch.branch_index > 1:
            base = f'{date_str}_{safe_title}_branch-{branch.branch_index}'
        else:
            base = f'{date_str}_{safe_title}'

        filename = f'{base}.md'

        if filename in self._used_filenames:
            short_id = conversation.id[:8]
            filename = f'{base}_{short_id}.md'

        self._used_filenames.add(filename)
        return filename

    def write(self, filename: str, content: str, conversation: Conversation):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.output_dir / filename
        filepath.write_text(content, encoding='utf-8')

        entry = self._manifest.setdefault(conversation.id, {'update_time': 0, 'files': []})
        entry['update_time'] = conversation.update_time or 0
        if filename not in entry['files']:
            entry['files'].append(filename)

    def copy_asset(self, export_folder: Path, file_id: str) -> str | None:
        """Find file by prefix in export_folder, copy to assets/, return actual filename."""
        matches = list(Path(export_folder).glob(f'{file_id}*'))
        if not matches:
            return None
        src = matches[0]
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        dst = self.assets_dir / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
        return src.name

    def _format_date(self, timestamp: float | None) -> str:
        if not timestamp:
            return 'unknown'
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return dt.strftime('%Y-%m-%d')
```

**Step 4: Run tests**

```bash
pytest tests/test_file_manager.py -v
```

Expected: all PASS

**Step 5: Commit**

```bash
git add file_manager.py tests/test_file_manager.py
git commit -m "feat: FileManager filename sanitization and collision handling"
```

---

## Task 7: FileManager — Manifest & File Writing

**Files:**
- Modify: `tests/test_file_manager.py`

**Step 1: Write failing tests**

Add to `tests/test_file_manager.py`:

```python
def test_needs_update_new_conversation(tmp_path):
    fm = FileManager(tmp_path)
    conv = _make_conv('new-id', 'New Chat')
    assert fm.needs_update(conv) is True


def test_needs_update_same_timestamp(tmp_path):
    fm = FileManager(tmp_path)
    conv = _make_conv('existing-id', 'Chat', update_time=1700000100.0)
    # Simulate existing manifest entry
    fm._manifest['existing-id'] = {'update_time': 1700000100.0, 'files': ['file.md']}
    assert fm.needs_update(conv) is False


def test_needs_update_newer_timestamp(tmp_path):
    fm = FileManager(tmp_path)
    conv = _make_conv('existing-id', 'Chat', update_time=1700000200.0)
    fm._manifest['existing-id'] = {'update_time': 1700000100.0, 'files': ['file.md']}
    assert fm.needs_update(conv) is True


def test_write_creates_file(tmp_path):
    fm = FileManager(tmp_path)
    conv = _make_conv('abc', 'My Chat')
    fm.write('2023-11-14_My_Chat.md', '# My Chat\n\nhello', conv)
    assert (tmp_path / '2023-11-14_My_Chat.md').exists()
    assert (tmp_path / '2023-11-14_My_Chat.md').read_text() == '# My Chat\n\nhello'


def test_write_updates_manifest(tmp_path):
    fm = FileManager(tmp_path)
    conv = _make_conv('abc', 'My Chat', update_time=1700000100.0)
    fm.write('2023-11-14_My_Chat.md', '# content', conv)
    assert fm._manifest['abc']['update_time'] == 1700000100.0
    assert '2023-11-14_My_Chat.md' in fm._manifest['abc']['files']


def test_save_and_reload_manifest(tmp_path):
    fm = FileManager(tmp_path)
    conv = _make_conv('abc', 'My Chat', update_time=1700000100.0)
    fm.write('2023-11-14_My_Chat.md', '# content', conv)
    fm.save_manifest()

    fm2 = FileManager(tmp_path)
    assert fm2._manifest['abc']['update_time'] == 1700000100.0
    assert fm2.needs_update(conv) is False
```

**Step 2: Run to verify they fail**

```bash
pytest tests/test_file_manager.py::test_write_creates_file \
       tests/test_file_manager.py::test_save_and_reload_manifest -v
```

Expected: FAIL

**Step 3: These tests should already pass** with the implementation from Task 6. Run them:

```bash
pytest tests/test_file_manager.py -v
```

Expected: all PASS (manifest and write methods were already implemented). If any fail, fix the specific method.

**Step 4: Commit**

```bash
git add tests/test_file_manager.py
git commit -m "test: add manifest and file writing tests for FileManager"
```

---

## Task 8: FileManager — Image Copying

**Files:**
- Modify: `tests/test_file_manager.py`

**Step 1: Write failing tests**

Add to `tests/test_file_manager.py`:

```python
def test_copy_asset_finds_file_by_prefix(tmp_path):
    # Create a fake export folder with an image
    export = tmp_path / 'export'
    export.mkdir()
    fake_image = export / 'file_abc123-sanitized.jpg'
    fake_image.write_bytes(b'fakejpeg')

    output = tmp_path / 'output'
    fm = FileManager(output)
    result = fm.copy_asset(export, 'file_abc123')

    assert result == 'file_abc123-sanitized.jpg'
    assert (output / 'assets' / 'file_abc123-sanitized.jpg').exists()


def test_copy_asset_returns_none_if_missing(tmp_path):
    export = tmp_path / 'export'
    export.mkdir()
    output = tmp_path / 'output'
    fm = FileManager(output)
    result = fm.copy_asset(export, 'file_nonexistent')
    assert result is None


def test_copy_asset_does_not_duplicate(tmp_path):
    export = tmp_path / 'export'
    export.mkdir()
    fake_image = export / 'file_abc123-sanitized.jpg'
    fake_image.write_bytes(b'fakejpeg')

    output = tmp_path / 'output'
    fm = FileManager(output)
    fm.copy_asset(export, 'file_abc123')
    fm.copy_asset(export, 'file_abc123')  # second call should not raise

    assets = list((output / 'assets').iterdir())
    assert len(assets) == 1
```

**Step 2: Run to verify**

```bash
pytest tests/test_file_manager.py -v
```

Expected: all PASS (copy_asset already implemented in Task 6). If any fail, fix.

**Step 3: Commit**

```bash
git add tests/test_file_manager.py
git commit -m "test: add image asset copying tests for FileManager"
```

---

## Task 9: CLI Entrypoint

**Files:**
- Create: `keromdizer.py`

No unit tests for the CLI (it's a thin wiring layer). We'll verify with a manual dry-run in Step 3.

**Step 1: Implement keromdizer.py**

```python
import argparse
import sys
from pathlib import Path

from conversation_parser import ConversationParser
from renderer import MarkdownRenderer
from file_manager import FileManager


def main():
    arg_parser = argparse.ArgumentParser(
        description='Convert a ChatGPT data export folder to GFM markdown files.'
    )
    arg_parser.add_argument(
        'export_folder',
        type=Path,
        help='Path to the ChatGPT export directory (must contain conversations.json)',
    )
    arg_parser.add_argument(
        '--output',
        type=Path,
        default=Path('./output'),
        help='Output directory for markdown files (default: ./output)',
    )
    arg_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print what would be written without writing any files',
    )
    args = arg_parser.parse_args()

    if not args.export_folder.is_dir():
        print(f'Error: {args.export_folder} is not a directory', file=sys.stderr)
        sys.exit(1)

    conv_parser = ConversationParser(args.export_folder)
    try:
        conversations = conv_parser.parse()
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    renderer = MarkdownRenderer()
    file_mgr = FileManager(args.output)

    written = 0
    skipped = 0

    for conv in conversations:
        if not file_mgr.needs_update(conv):
            skipped += 1
            continue

        for branch in conv.branches:
            # Resolve image references to actual filenames
            for msg in branch.messages:
                resolved = {}
                for file_id in msg.image_refs:
                    actual_name = file_mgr.copy_asset(args.export_folder, file_id)
                    if actual_name:
                        resolved[file_id] = actual_name
                    else:
                        print(f'Warning: image not found in export: {file_id}')
                for old_id, new_name in resolved.items():
                    msg.text = msg.text.replace(
                        f'assets/{old_id})', f'assets/{new_name})'
                    )

            content = renderer.render(conv, branch)
            filename = file_mgr.make_filename(conv, branch)

            if args.dry_run:
                branch_label = f' (branch {branch.branch_index})' if len(conv.branches) > 1 else ''
                print(f'  Would write: {args.output / filename}{branch_label}')
            else:
                file_mgr.write(filename, content, conv)
                written += 1

    if not args.dry_run:
        file_mgr.save_manifest()
        print(f'Done. Written: {written} file(s), skipped {skipped} up-to-date conversation(s).')
    else:
        total = sum(len(c.branches) for c in conversations if file_mgr.needs_update(c))
        print(f'Dry run complete. Would write ~{total} file(s), skip {skipped} conversation(s).')


if __name__ == '__main__':
    main()
```

**Step 2: Run full test suite to ensure nothing broke**

```bash
pytest tests/ -v
```

Expected: all tests PASS

**Step 3: Smoke test with fixture**

```bash
python keromdizer.py tests/fixtures/ --output /tmp/kero-test --dry-run
```

Expected output (approximate):
```
  Would write: /tmp/kero-test/2023-11-14_Test__Python_Basics.md
  Would write: /tmp/kero-test/2023-11-14_Test__Python_Basics_branch-2.md
  Would write: /tmp/kero-test/2023-11-14_Test__With_Image.md
Dry run complete. Would write ~3 file(s), skip 0 conversation(s).
```

**Step 4: Smoke test with real export (dry run)**

```bash
python keromdizer.py ~/Downloads/27acb0dfd0a3c5fc91e10df3ec41412e00ff7879d440e4504e23ce0810ffbfff-2026-01-14-04-16-34-d9369f62a9184a8b86ce547d614186fb/ --output ~/KeroMDizer-output --dry-run
```

Verify: output lists files without errors, count looks reasonable (394 conversations, likely more files due to branches).

**Step 5: Commit**

```bash
git add keromdizer.py
git commit -m "feat: CLI entrypoint wiring parser, renderer, and file manager"
```

---

## Task 10: Integration — Real Export Run

**Files:**
- No new files; verification only.

**Step 1: Run against the real export**

```bash
python keromdizer.py ~/Downloads/27acb0dfd0a3c5fc91e10df3ec41412e00ff7879d440e4504e23ce0810ffbfff-2026-01-14-04-16-34-d9369f62a9184a8b86ce547d614186fb/ --output ~/KeroMDizer-output
```

**Step 2: Spot-check output**

```bash
ls ~/KeroMDizer-output/ | head -20
ls ~/KeroMDizer-output/assets/ | head -10
cat ~/KeroMDizer-output/manifest.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'{len(d)} conversations in manifest')"
```

**Step 3: Verify a known chat renders correctly**

Open one of the output `.md` files and verify:
- Metadata table is present at top
- Title heading is correct
- Code blocks are properly fenced with language tags
- Images (if any) reference `assets/` correctly

**Step 4: Test deduplication (run again, should skip everything)**

```bash
python keromdizer.py ~/Downloads/27acb0dfd0a3c5fc91e10df3ec41412e00ff7879d440e4504e23ce0810ffbfff-2026-01-14-04-16-34-d9369f62a9184a8b86ce547d614186fb/ --output ~/KeroMDizer-output
```

Expected: `Written: 0 file(s), skipped N up-to-date conversation(s).`

**Step 5: Final commit**

```bash
git add -A
git commit -m "chore: verified integration with real ChatGPT export"
```

---

## Notes for Future Extension

- **TUI layer:** Instantiate `ConversationParser`, `MarkdownRenderer`, `FileManager` directly — same API, no script changes needed
- **DeepSeek support:** Subclass `ConversationParser` and override `_parse_conversation` — DeepSeek exports use a similar but slightly different schema
- **Content type flags:** Add `include_thoughts`, `include_tool_calls` booleans to `ConversationParser.__init__` and expand `_extract_messages` filter accordingly
- **Additional exports:** Pass the older export folder with `--output` pointing to the same directory — `manifest.json` deduplication will handle merging automatically
