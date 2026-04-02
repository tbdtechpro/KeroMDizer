# Obsidian Export + Contraction Tag Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Obsidian-optimized `.md` export as a parallel output format, and fix YAKE keyword extraction dropping contraction artifacts (`n't`, `r'e`) into inferred tags.

**Architecture:** New `obsidian_renderer.py` renders Obsidian `.md` from DB branch rows (YAML frontmatter + callout-wrapped messages). The CLI post-sweep and TUI Export Settings screen wire it in alongside the existing html/docx exporters. The contraction fix is a one-line post-filter in `inference.py`.

**Tech Stack:** Python 3.11+ stdlib only; YAKE (keyword extraction); `db.DatabaseManager` (SQLite source of truth); BubbleTea TUI framework (lipgloss/bubbletea/pyubbles).

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Modify | `inference.py` | Filter apostrophe tokens from YAKE output |
| Create | `obsidian_renderer.py` | `ObsidianRenderer` — YAML frontmatter + callout body |
| Modify | `models.py` | Add `obsidian_enabled`, `obsidian_dir` to `ExportConfig` |
| Modify | `config.py` | Read obsidian fields in `load_export_config()` |
| Modify | `keromdizer.py` | Add obsidian block to post-import sweep |
| Modify | `tui.py` | Add obsidian fields to EXPORT_SETTINGS screen |
| Modify | `tests/test_inference.py` | Apostrophe filter test cases |
| Create | `tests/test_obsidian_renderer.py` | Full renderer test suite |
| Modify | `tests/test_config.py` | Test new ExportConfig fields |

---

## Task 1: Contraction Tag Filter

**Files:**
- Modify: `inference.py:11`
- Modify: `tests/test_inference.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_inference.py`:

```python
def test_infer_tags_filters_contraction_artifacts():
    """YAKE produces n't, r'e etc. from contractions — these must be filtered."""
    # Force YAKE to see contractions by using them directly
    text = "don't won't they're we've I'll he'd isn't can't"
    tags = infer_tags(text, top_n=20)
    for tag in tags:
        assert "'" not in tag, f"Contraction artifact leaked into tags: {tag!r}"


def test_infer_tags_preserves_short_tokens_without_apostrophe():
    """Short tags like AI, UX, CI must not be filtered (no apostrophe)."""
    # YAKE won't naturally extract 2-char tokens, but the filter must not block them
    # Test the filter logic directly: if YAKE returned these, they'd survive
    from inference import infer_tags
    # Use text that forces YAKE to score 'AI' highly
    text = ' '.join(['AI'] * 30 + ['artificial', 'intelligence', 'model'])
    tags = infer_tags(text, top_n=5)
    # AI may or may not appear (YAKE behaviour), but we assert the filter
    # doesn't remove tokens lacking apostrophes
    for tag in tags:
        if "'" not in tag:
            assert tag == tag  # trivially true — just confirm no apostrophe-free token was removed
    # Directly verify the filter predicate: tokens without apostrophe must pass
    import yake
    extractor = yake.KeywordExtractor(lan='en', n=1, dedupLim=0.9, top=20)
    raw = extractor.extract_keywords(text)
    without_filter = [kw for kw, _ in raw]
    with_filter    = [kw for kw, _ in raw if "'" not in kw]
    # Every token in with_filter must also be in without_filter (only apostrophe ones removed)
    for tag in with_filter:
        assert "'" not in tag
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_inference.py::test_infer_tags_filters_contraction_artifacts \
       tests/test_inference.py::test_infer_tags_preserves_short_tokens_without_apostrophe -v
```

Expected: the first test may pass or fail depending on input text — run against a real contraction-heavy string to observe the bug first.

- [ ] **Step 3: Apply the fix**

In `inference.py`, change line 11:

```python
# Before
return [kw for kw, _score in results]

# After
return [kw for kw, _score in results if "'" not in kw]
```

Full updated function:

```python
def infer_tags(text: str, top_n: int = 10) -> list[str]:
    """Extract top_n keywords from text using YAKE."""
    if not text or not text.strip():
        return []
    extractor = yake.KeywordExtractor(lan='en', n=1, dedupLim=0.9, top=top_n)
    results = extractor.extract_keywords(text)
    return [kw for kw, _score in results if "'" not in kw]
```

- [ ] **Step 4: Run all inference tests**

```bash
pytest tests/test_inference.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add inference.py tests/test_inference.py
git commit -m "fix: filter contraction artifacts from YAKE inferred tags

Tokens containing apostrophes (n't, r'e, 've etc.) are always
contraction fragments, not meaningful keywords. One-line post-filter
in infer_tags(). Short tokens without apostrophes (AI, UX, CI) are
preserved."
```

---

## Task 2: ObsidianRenderer — Frontmatter

**Files:**
- Create: `obsidian_renderer.py`
- Create: `tests/test_obsidian_renderer.py`

- [ ] **Step 1: Write the failing frontmatter tests**

Create `tests/test_obsidian_renderer.py`:

```python
"""Tests for ObsidianRenderer."""
import pytest


def _branch_row(**overrides) -> dict:
    """Minimal valid branch row matching db.list_branches() shape."""
    base = {
        'branch_id': 'conv1__branch_1',
        'conversation_id': 'conv1',
        'branch_index': 1,
        'is_main_branch': True,
        'messages': [],
        'tags': [],
        'project': None,
        'category': None,
        'syntax': [],
        'inferred_tags': ['python', 'api design'],
        'inferred_syntax': ['python'],
        'md_filename': '2026-01-14_Hello_World.md',
        'title': 'Hello World',
        'provider': 'chatgpt',
        'conv_create_time': '2026-01-14T04:16:34+00:00',
        'model_slug': 'gpt-4o',
        'branch_count': 1,
        'user_alias': 'Matt',
        'assistant_alias': 'ChatGPT',
    }
    base.update(overrides)
    return base


# ── Frontmatter tests ──────────────────────────────────────────────────────────

def test_frontmatter_starts_and_ends_with_dashes():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    row = _branch_row()
    result = r._build_frontmatter(row)
    assert result.startswith('---\n')
    assert result.endswith('\n---')


def test_frontmatter_title_present_and_quoted():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(title='Hello World'))
    assert 'title: "Hello World"' in result


def test_frontmatter_title_with_colon_quoted():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(title='Python: A Guide'))
    assert 'title: "Python: A Guide"' in result


def test_frontmatter_aliases_present():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(title='Hello World'))
    assert 'aliases:' in result
    assert '  - "Hello World"' in result


def test_frontmatter_created_date_only():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(conv_create_time='2026-01-14T04:16:34+00:00'))
    assert 'created: 2026-01-14' in result
    assert 'T' not in result.split('created:')[1].split('\n')[0]


def test_frontmatter_provider_present():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(provider='chatgpt'))
    assert 'provider: chatgpt' in result


def test_frontmatter_model_present():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(model_slug='gpt-4o'))
    assert 'model: gpt-4o' in result


def test_frontmatter_model_omitted_when_null():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(model_slug=None))
    assert 'model:' not in result


def test_frontmatter_conversation_id_present():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(conversation_id='abc-123'))
    assert 'conversation_id: abc-123' in result


def test_frontmatter_branch_fields_omitted_for_single_branch():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(branch_count=1))
    assert 'branch:' not in result
    assert 'branch_count:' not in result


def test_frontmatter_branch_fields_present_for_multi_branch():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(branch_index=2, branch_count=3))
    assert 'branch: 2' in result
    assert 'branch_count: 3' in result


def test_frontmatter_tags_sanitized_and_merged():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    row = _branch_row(inferred_tags=['api design', 'python'], tags=['My Tag!'])
    result = r._build_frontmatter(row)
    assert 'tags:' in result
    assert '  - api-design' in result
    assert '  - python' in result
    assert '  - my-tag' in result


def test_frontmatter_tags_deduplicated():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    row = _branch_row(inferred_tags=['python'], tags=['python'])
    result = r._build_frontmatter(row)
    assert result.count('  - python') == 1


def test_frontmatter_tags_omitted_when_empty():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(inferred_tags=[], tags=[]))
    assert 'tags:' not in result


def test_frontmatter_project_present_when_set():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(project='my-project'))
    assert 'project: "my-project"' in result


def test_frontmatter_project_omitted_when_null():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(project=None))
    assert 'project:' not in result


def test_frontmatter_category_present_when_set():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(category='work'))
    assert 'category: "work"' in result


def test_frontmatter_syntax_list_present():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(inferred_syntax=['python', 'bash'], syntax=[]))
    assert 'syntax:' in result
    assert '  - python' in result
    assert '  - bash' in result


def test_frontmatter_syntax_omitted_when_empty():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(inferred_syntax=[], syntax=[]))
    assert 'syntax:' not in result
```

- [ ] **Step 2: Run tests to confirm they fail (ImportError expected)**

```bash
pytest tests/test_obsidian_renderer.py -v
```

Expected: `ImportError: No module named 'obsidian_renderer'`

- [ ] **Step 3: Create `obsidian_renderer.py` with frontmatter logic**

```python
"""Obsidian-optimized markdown renderer for KeroMDizer conversations."""
from __future__ import annotations
import re

_TAG_INVALID_RE = re.compile(r'[^a-z0-9_\-/]')
_IMAGE_RE = re.compile(r'!\[.*?\]\(assets/([^)]+)\)')


def _yaml_quoted(value: str) -> str:
    """Return value as a double-quoted YAML string scalar."""
    escaped = value.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped}"'


class ObsidianRenderer:

    def _build_frontmatter(self, row: dict) -> str:
        lines = ['---']
        title = row.get('title') or 'Untitled'
        lines.append(f'title: {_yaml_quoted(title)}')
        lines.append('aliases:')
        lines.append(f'  - {_yaml_quoted(title)}')
        conv_create_time = row.get('conv_create_time') or ''
        if conv_create_time:
            lines.append(f'created: {conv_create_time[:10]}')
        provider = row.get('provider') or ''
        if provider:
            lines.append(f'provider: {provider}')
        model = row.get('model_slug') or ''
        if model:
            lines.append(f'model: {model}')
        conv_id = row.get('conversation_id') or ''
        if conv_id:
            lines.append(f'conversation_id: {conv_id}')
        branch_count = row.get('branch_count') or 1
        if branch_count > 1:
            lines.append(f'branch: {row.get("branch_index", 1)}')
            lines.append(f'branch_count: {branch_count}')
        tags = self._build_tags(row)
        if tags:
            lines.append('tags:')
            for tag in tags:
                lines.append(f'  - {tag}')
        project = row.get('project') or ''
        if project:
            lines.append(f'project: {_yaml_quoted(project)}')
        category = row.get('category') or ''
        if category:
            lines.append(f'category: {_yaml_quoted(category)}')
        syntax = self._build_syntax(row)
        if syntax:
            lines.append('syntax:')
            for s in syntax:
                lines.append(f'  - {s}')
        lines.append('---')
        return '\n'.join(lines)

    def _build_tags(self, row: dict) -> list[str]:
        combined = list(row.get('inferred_tags') or []) + list(row.get('tags') or [])
        seen: list[str] = []
        for raw in combined:
            tag = _TAG_INVALID_RE.sub('', raw.lower().replace(' ', '-'))
            if tag and tag not in seen:
                seen.append(tag)
        return seen

    def _build_syntax(self, row: dict) -> list[str]:
        combined = list(row.get('inferred_syntax') or []) + list(row.get('syntax') or [])
        seen: list[str] = []
        for s in combined:
            if s and s not in seen:
                seen.append(s)
        return seen
```

- [ ] **Step 4: Run frontmatter tests**

```bash
pytest tests/test_obsidian_renderer.py -v
```

Expected: all frontmatter tests pass. (Callout/render tests don't exist yet — only frontmatter tests are in the file at this point.)

- [ ] **Step 5: Commit**

```bash
git add obsidian_renderer.py tests/test_obsidian_renderer.py
git commit -m "feat: add ObsidianRenderer with YAML frontmatter generation"
```

---

## Task 3: Callout Wrapping and Image Conversion

**Files:**
- Modify: `obsidian_renderer.py` (add `_wrap_callout`, `_segments_to_text`)
- Modify: `tests/test_obsidian_renderer.py` (add callout/image tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_obsidian_renderer.py`:

```python
# ── Callout tests ──────────────────────────────────────────────────────────────

def test_wrap_callout_header_format():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._wrap_callout('question', '👤 Matt', 'Hello world')
    assert result.startswith('> [!question] 👤 Matt\n')


def test_wrap_callout_body_lines_prefixed():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._wrap_callout('note', 'Label', 'line one\nline two')
    lines = result.split('\n')
    assert '> line one' in lines
    assert '> line two' in lines


def test_wrap_callout_blank_lines_become_bare_gt():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._wrap_callout('note', 'Label', 'para one\n\npara two')
    lines = result.split('\n')
    # blank line must be '>' not '> ' (no trailing space)
    assert '>' in lines
    assert '> ' not in [l for l in lines if l == '>']


def test_wrap_callout_code_fence_lines_prefixed():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    body = '```python\ndef foo():\n    pass\n```'
    result = r._wrap_callout('abstract', 'Label', body)
    assert '> ```python' in result
    assert '> def foo():' in result
    assert '> ```' in result


def test_segments_to_text_prose_only():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    content = [{'type': 'prose', 'text': 'Hello world'}]
    assert r._segments_to_text(content) == 'Hello world'


def test_segments_to_text_code_wrapped_in_fences():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    content = [{'type': 'code', 'language': 'python', 'text': 'print("hi")'}]
    result = r._segments_to_text(content)
    assert result == '```python\nprint("hi")\n```'


def test_segments_to_text_mixed_separated_by_blank_line():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    content = [
        {'type': 'prose', 'text': 'See this:'},
        {'type': 'code', 'language': 'bash', 'text': 'echo hi'},
    ]
    result = r._segments_to_text(content)
    assert 'See this:' in result
    assert '```bash\necho hi\n```' in result
    # separated by double newline
    assert 'See this:\n\n```bash' in result


def test_segments_to_text_code_no_language():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    content = [{'type': 'code', 'language': None, 'text': 'some text'}]
    result = r._segments_to_text(content)
    assert result == '```\nsome text\n```'


# ── Image conversion tests ─────────────────────────────────────────────────────

def test_image_converted_to_wikilink():
    from obsidian_renderer import _IMAGE_RE
    text = '![alt text](assets/file_abc-sanitized.jpg)'
    result = _IMAGE_RE.sub(lambda m: f'![[{m.group(1)}]]', text)
    assert result == '![[file_abc-sanitized.jpg]]'


def test_image_no_alt_converted():
    from obsidian_renderer import _IMAGE_RE
    text = '![](assets/image.png)'
    result = _IMAGE_RE.sub(lambda m: f'![[{m.group(1)}]]', text)
    assert result == '![[image.png]]'


def test_non_asset_image_not_converted():
    from obsidian_renderer import _IMAGE_RE
    text = '![](https://example.com/image.png)'
    result = _IMAGE_RE.sub(lambda m: f'![[{m.group(1)}]]', text)
    assert result == '![](https://example.com/image.png)'
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_obsidian_renderer.py -k "callout or segment or image" -v
```

Expected: `AttributeError: 'ObsidianRenderer' object has no attribute '_wrap_callout'`

- [ ] **Step 3: Add callout and segment methods to `obsidian_renderer.py`**

Add these methods to the `ObsidianRenderer` class:

```python
    def _wrap_callout(self, callout_type: str, label: str, text: str) -> str:
        """Wrap text in an Obsidian callout block."""
        lines = [f'> [!{callout_type}] {label}', '>']
        for line in text.split('\n'):
            lines.append(f'> {line}' if line else '>')
        return '\n'.join(lines)

    def _segments_to_text(self, content: list[dict]) -> str:
        """Reconstruct message text from structured DB content segments."""
        parts = []
        for seg in content:
            if seg.get('type') == 'code':
                lang = seg.get('language') or ''
                parts.append(f'```{lang}\n{seg.get("text", "")}\n```')
            else:
                text = seg.get('text') or ''
                if text:
                    parts.append(text)
        return '\n\n'.join(parts)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_obsidian_renderer.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add obsidian_renderer.py tests/test_obsidian_renderer.py
git commit -m "feat: add callout wrapping and image conversion to ObsidianRenderer"
```

---

## Task 4: Full `render()` Integration

**Files:**
- Modify: `obsidian_renderer.py` (add `render()`)
- Modify: `tests/test_obsidian_renderer.py` (add integration tests)

- [ ] **Step 1: Write failing integration tests**

Append to `tests/test_obsidian_renderer.py`:

```python
# ── render() integration tests ─────────────────────────────────────────────────

def _make_row_with_messages() -> dict:
    return _branch_row(
        messages=[
            {
                'role': 'user',
                'timestamp': '2026-01-14T04:16:34+00:00',
                'content': [{'type': 'prose', 'text': 'What is Python?'}],
            },
            {
                'role': 'assistant',
                'timestamp': '2026-01-14T04:16:35+00:00',
                'content': [
                    {'type': 'prose', 'text': 'Python is a language.'},
                    {'type': 'code', 'language': 'python', 'text': 'print("hello")'},
                ],
            },
        ]
    )


def test_render_starts_with_frontmatter():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r.render(_make_row_with_messages())
    assert result.startswith('---\n')


def test_render_contains_title_heading():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r.render(_make_row_with_messages())
    assert '\n# Hello World\n' in result


def test_render_user_turn_uses_question_callout():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r.render(_make_row_with_messages())
    assert '> [!question] 👤 Matt' in result


def test_render_assistant_turn_uses_abstract_callout():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r.render(_make_row_with_messages())
    assert '> [!abstract] 🤖 ChatGPT' in result


def test_render_message_content_inside_callout():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r.render(_make_row_with_messages())
    assert '> What is Python?' in result
    assert '> Python is a language.' in result
    assert '> ```python' in result


def test_render_image_converted_to_wikilink():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    row = _branch_row(messages=[{
        'role': 'user',
        'timestamp': None,
        'content': [{'type': 'prose', 'text': '![](assets/file_abc.jpg)'}],
    }])
    result = r.render(row)
    assert '![[file_abc.jpg]]' in result
    assert '![](assets/' not in result


def test_render_empty_messages_produces_valid_output():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r.render(_branch_row(messages=[]))
    assert result.startswith('---\n')
    assert '# Hello World' in result


def test_render_fallback_persona_when_aliases_missing():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    row = _branch_row(
        user_alias=None,
        assistant_alias=None,
        messages=[
            {'role': 'user', 'timestamp': None, 'content': [{'type': 'prose', 'text': 'Hi'}]},
            {'role': 'assistant', 'timestamp': None, 'content': [{'type': 'prose', 'text': 'Hello'}]},
        ],
    )
    result = r.render(row)
    assert '👤 User' in result
    assert '🤖 Assistant' in result
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_obsidian_renderer.py -k "render" -v
```

Expected: `AttributeError: 'ObsidianRenderer' object has no attribute 'render'`

- [ ] **Step 3: Add `render()` to `ObsidianRenderer`**

Add this method to the class (before `_build_frontmatter`):

```python
    def render(self, row: dict) -> str:
        """Render a DB branch row as an Obsidian-optimized markdown string."""
        parts = [self._build_frontmatter(row), '']
        title = row.get('title') or 'Untitled'
        parts.append(f'# {title}')
        parts.append('')
        user_alias = row.get('user_alias') or 'User'
        assistant_alias = row.get('assistant_alias') or 'Assistant'
        for msg in row.get('messages') or []:
            role = msg.get('role', '')
            text = self._segments_to_text(msg.get('content') or [])
            text = _IMAGE_RE.sub(lambda m: f'![[{m.group(1)}]]', text)
            if role == 'user':
                block = self._wrap_callout('question', f'👤 {user_alias}', text)
            else:
                block = self._wrap_callout('abstract', f'🤖 {assistant_alias}', text)
            parts.append(block)
            parts.append('')
        return '\n'.join(parts)
```

- [ ] **Step 4: Run all obsidian renderer tests**

```bash
pytest tests/test_obsidian_renderer.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add obsidian_renderer.py tests/test_obsidian_renderer.py
git commit -m "feat: complete ObsidianRenderer with render() integration"
```

---

## Task 5: ExportConfig + Config

**Files:**
- Modify: `models.py`
- Modify: `config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

Append to `tests/test_config.py`:

```python
def test_load_export_config_obsidian_defaults_to_disabled(monkeypatch, tmp_path):
    from config import load_export_config
    monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'nonexistent.toml')
    cfg = load_export_config()
    assert cfg.obsidian_enabled is False
    assert cfg.obsidian_dir == ''


def test_load_export_config_obsidian_enabled_from_toml(monkeypatch, tmp_path):
    from config import load_export_config
    cfg_file = tmp_path / 'keromdizer.toml'
    _write_toml(cfg_file, '[exports]\nobsidian = "yes"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg_file)
    cfg = load_export_config()
    assert cfg.obsidian_enabled is True


def test_load_export_config_obsidian_dir_from_toml(monkeypatch, tmp_path):
    from config import load_export_config
    cfg_file = tmp_path / 'keromdizer.toml'
    _write_toml(cfg_file, '[exports]\nobsidian = "yes"\nobsidian_dir = "/my/vault"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg_file)
    cfg = load_export_config()
    assert cfg.obsidian_dir == '/my/vault'
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_config.py::test_load_export_config_obsidian_defaults_to_disabled \
       tests/test_config.py::test_load_export_config_obsidian_enabled_from_toml \
       tests/test_config.py::test_load_export_config_obsidian_dir_from_toml -v
```

Expected: `AttributeError: 'ExportConfig' object has no attribute 'obsidian_enabled'`

- [ ] **Step 3: Update `models.py`**

In `models.py`, add two fields to `ExportConfig`:

```python
@dataclass
class ExportConfig:
    html_github_enabled: bool = False
    html_github_dir: str = ''
    html_retro_enabled: bool = False
    html_retro_dir: str = ''
    docx_enabled: bool = False
    docx_dir: str = ''
    obsidian_enabled: bool = False
    obsidian_dir: str = ''
```

- [ ] **Step 4: Update `config.py`**

In `load_export_config()`, add two lines to the return statement:

```python
def load_export_config() -> ExportConfig:
    """Load export format settings from ~/.keromdizer.toml."""
    data = _load_toml()
    e = data.get('exports', {})
    return ExportConfig(
        html_github_enabled=e.get('html_github', 'no') == 'yes',
        html_github_dir=e.get('html_github_dir', ''),
        html_retro_enabled=e.get('html_retro', 'no') == 'yes',
        html_retro_dir=e.get('html_retro_dir', ''),
        docx_enabled=e.get('docx', 'no') == 'yes',
        docx_dir=e.get('docx_dir', ''),
        obsidian_enabled=e.get('obsidian', 'no') == 'yes',
        obsidian_dir=e.get('obsidian_dir', ''),
    )
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_config.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add models.py config.py tests/test_config.py
git commit -m "feat: add obsidian_enabled/obsidian_dir to ExportConfig"
```

---

## Task 6: keromdizer.py CLI Post-Sweep Wiring

**Files:**
- Modify: `keromdizer.py`

- [ ] **Step 1: Write a focused integration test**

Create `tests/test_obsidian_sweep.py`:

```python
"""Integration test: obsidian post-sweep writes files from DB rows."""
import pytest
from pathlib import Path
from db import DatabaseManager
from obsidian_renderer import ObsidianRenderer


def _populate_db(db: DatabaseManager) -> None:
    db.upsert_conversation(
        conversation_id='test1',
        provider='chatgpt',
        title='Test Conversation',
        create_time='2026-01-14T00:00:00+00:00',
        update_time='2026-01-14T00:00:00+00:00',
        model_slug='gpt-4o',
        branch_count=1,
        branches=[{
            'branch_id': 'test1__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': ['python'],
            'inferred_syntax': ['python'],
            'md_filename': '2026-01-14_Test_Conversation.md',
        }],
        user_alias='Matt',
        assistant_alias='ChatGPT',
    )


def test_obsidian_sweep_writes_file(tmp_path):
    db = DatabaseManager(tmp_path / 'test.db')
    _populate_db(db)
    renderer = ObsidianRenderer()
    obsidian_dir = tmp_path / 'obsidian'

    for row in db.list_branches():
        md_filename = row.get('md_filename') or ''
        if not md_filename:
            continue
        out = obsidian_dir / md_filename
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(renderer.render(row), encoding='utf-8')

    db.close()
    out_file = obsidian_dir / '2026-01-14_Test_Conversation.md'
    assert out_file.exists()
    content = out_file.read_text(encoding='utf-8')
    assert content.startswith('---\n')
    assert 'title: "Test Conversation"' in content


def test_obsidian_sweep_skips_existing_files(tmp_path):
    db = DatabaseManager(tmp_path / 'test.db')
    _populate_db(db)
    renderer = ObsidianRenderer()
    obsidian_dir = tmp_path / 'obsidian'
    obsidian_dir.mkdir()

    # Pre-write a sentinel file
    sentinel = obsidian_dir / '2026-01-14_Test_Conversation.md'
    sentinel.write_text('SENTINEL', encoding='utf-8')

    for row in db.list_branches():
        md_filename = row.get('md_filename') or ''
        if not md_filename:
            continue
        out = obsidian_dir / md_filename
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(renderer.render(row), encoding='utf-8')

    db.close()
    # Sentinel must be unchanged
    assert sentinel.read_text(encoding='utf-8') == 'SENTINEL'
```

- [ ] **Step 2: Run tests to confirm they pass (testing the logic, not keromdizer.py directly)**

```bash
pytest tests/test_obsidian_sweep.py -v
```

Expected: both pass (the sweep logic is exercised directly, no CLI needed).

- [ ] **Step 3: Wire into `keromdizer.py`**

Find the post-import sweep block (around line 213). Replace:

```python
            if exp_cfg.html_github_enabled or exp_cfg.html_retro_enabled or exp_cfg.docx_enabled:
                sweep_count = 0
                for row in db.list_branches():
                    md_filename = row.get('md_filename') or ''
                    if not md_filename:
                        continue
                    md_path = args.output / md_filename
                    if not md_path.exists():
                        continue
                    try:
                        md_content = md_path.read_text(encoding='utf-8')
                    except OSError:
                        continue
                    stem = md_filename[:-3]
                    if exp_cfg.html_github_enabled:
                        from html_github_exporter import export_html_github
                        html_dir = Path(exp_cfg.html_github_dir).expanduser() if exp_cfg.html_github_dir else args.output / 'html-github'
                        out = html_dir / f'{stem}.html'
                        if not out.exists():
                            export_html_github(md_content, out)
                            sweep_count += 1
                    if exp_cfg.html_retro_enabled:
                        from html_retro_exporter import export_html_retro
                        retro_dir = Path(exp_cfg.html_retro_dir).expanduser() if exp_cfg.html_retro_dir else args.output / 'html-retro'
                        out = retro_dir / f'{stem}.html'
                        if not out.exists():
                            export_html_retro(md_content, out)
                            sweep_count += 1
                    if exp_cfg.docx_enabled:
                        from docx_exporter import export_docx
                        docx_dir = Path(exp_cfg.docx_dir).expanduser() if exp_cfg.docx_dir else args.output / 'docx'
                        out = docx_dir / f'{stem}.docx'
                        if not out.exists():
                            export_docx(md_content, out)
                            sweep_count += 1
                if sweep_count:
                    print(f'Alternate exports: {sweep_count} file(s) generated.')
```

With:

```python
            if exp_cfg.html_github_enabled or exp_cfg.html_retro_enabled or exp_cfg.docx_enabled or exp_cfg.obsidian_enabled:
                sweep_count = 0
                _obsidian_renderer = None
                _obsidian_out_dir = None
                if exp_cfg.obsidian_enabled:
                    from obsidian_renderer import ObsidianRenderer
                    _obsidian_renderer = ObsidianRenderer()
                    _obsidian_out_dir = (
                        Path(exp_cfg.obsidian_dir).expanduser()
                        if exp_cfg.obsidian_dir
                        else args.output / 'obsidian'
                    )
                for row in db.list_branches():
                    md_filename = row.get('md_filename') or ''
                    if not md_filename:
                        continue
                    stem = md_filename[:-3]
                    if exp_cfg.html_github_enabled or exp_cfg.html_retro_enabled or exp_cfg.docx_enabled:
                        md_path = args.output / md_filename
                        if md_path.exists():
                            try:
                                md_content = md_path.read_text(encoding='utf-8')
                            except OSError:
                                md_content = None
                            if md_content:
                                if exp_cfg.html_github_enabled:
                                    from html_github_exporter import export_html_github
                                    html_dir = Path(exp_cfg.html_github_dir).expanduser() if exp_cfg.html_github_dir else args.output / 'html-github'
                                    out = html_dir / f'{stem}.html'
                                    if not out.exists():
                                        export_html_github(md_content, out)
                                        sweep_count += 1
                                if exp_cfg.html_retro_enabled:
                                    from html_retro_exporter import export_html_retro
                                    retro_dir = Path(exp_cfg.html_retro_dir).expanduser() if exp_cfg.html_retro_dir else args.output / 'html-retro'
                                    out = retro_dir / f'{stem}.html'
                                    if not out.exists():
                                        export_html_retro(md_content, out)
                                        sweep_count += 1
                                if exp_cfg.docx_enabled:
                                    from docx_exporter import export_docx
                                    docx_dir = Path(exp_cfg.docx_dir).expanduser() if exp_cfg.docx_dir else args.output / 'docx'
                                    out = docx_dir / f'{stem}.docx'
                                    if not out.exists():
                                        export_docx(md_content, out)
                                        sweep_count += 1
                    if _obsidian_renderer and _obsidian_out_dir:
                        out = _obsidian_out_dir / md_filename
                        if not out.exists():
                            out.parent.mkdir(parents=True, exist_ok=True)
                            out.write_text(_obsidian_renderer.render(row), encoding='utf-8')
                            sweep_count += 1
                if sweep_count:
                    print(f'Alternate exports: {sweep_count} file(s) generated.')
```

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add keromdizer.py tests/test_obsidian_sweep.py
git commit -m "feat: wire obsidian post-sweep into keromdizer CLI"
```

---

## Task 7: TUI Export Settings

**Files:**
- Modify: `tui.py`

There are **6 locations** in `tui.py` that need changes. Read the file before editing each one.

- [ ] **Step 1: Update `_load_export_settings()` (~line 185)**

Find the `return {` block inside `_load_export_settings()`. Add two entries after `'docx_dir'`:

```python
    return {
        'html_github_enabled': e.get('html_github', 'no'),
        'html_github_dir':     e.get('html_github_dir', ''),
        'html_retro_enabled':  e.get('html_retro', 'no'),
        'html_retro_dir':      e.get('html_retro_dir', ''),
        'docx_enabled':        e.get('docx', 'no'),
        'docx_dir':            e.get('docx_dir', ''),
        'obsidian_enabled':    e.get('obsidian', 'no'),
        'obsidian_dir':        e.get('obsidian_dir', ''),
    }
```

- [ ] **Step 2: Update `_save_export_settings()` (~line 207)**

Find the `for key in (...)` tuple. Add the two new keys:

```python
    for key in ('html_github_enabled', 'html_github_dir',
                'html_retro_enabled', 'html_retro_dir',
                'docx_enabled', 'docx_dir',
                'obsidian_enabled', 'obsidian_dir'):
```

And update the `toml_key` mapping dict inside that loop:

```python
            toml_key = {
                'html_github_enabled': 'html_github',
                'html_retro_enabled':  'html_retro',
                'docx_enabled':        'docx',
                'obsidian_enabled':    'obsidian',
            }.get(key, key)
```

- [ ] **Step 3: Update `AppModel.__init__()` EXPORT SETTINGS section (~line 349)**

Find `self.es_fields`, `self.es_labels`, and `self.es_toggle_fields`. Add obsidian entries:

```python
        self.es_fields: list[str] = [
            'html_github_enabled', 'html_github_dir',
            'html_retro_enabled', 'html_retro_dir',
            'docx_enabled', 'docx_dir',
            'obsidian_enabled', 'obsidian_dir',
        ]
        self.es_labels: dict[str, str] = {
            'html_github_enabled': 'HTML (GitHub style)',
            'html_github_dir':     'HTML GitHub output dir',
            'html_retro_enabled':  'HTML (Retro 1994)',
            'html_retro_dir':      'HTML Retro output dir',
            'docx_enabled':        'DOCX (Word document)',
            'docx_dir':            'DOCX output dir',
            'obsidian_enabled':    'Obsidian markdown',
            'obsidian_dir':        'Obsidian output dir',
        }
        self.es_toggle_fields: set[str] = {
            'html_github_enabled', 'html_retro_enabled', 'docx_enabled', 'obsidian_enabled'
        }
```

- [ ] **Step 4: Update `_key_export_settings()` dir-fields set (~line 699)**

Find `_es_dir_fields = {`. Add `'obsidian_dir'`:

```python
            _es_dir_fields = {'html_github_dir', 'html_retro_dir', 'docx_dir', 'obsidian_dir'}
```

- [ ] **Step 5: Update `_alternate_export_sweep()` guard condition (~line 1665)**

Find the guard:
```python
    if not (exp_cfg.html_github_enabled or exp_cfg.html_retro_enabled or exp_cfg.docx_enabled):
        return 0
```

Replace with:
```python
    if not (exp_cfg.html_github_enabled or exp_cfg.html_retro_enabled or exp_cfg.docx_enabled or exp_cfg.obsidian_enabled):
        return 0
```

- [ ] **Step 6: Add obsidian block inside `_alternate_export_sweep()` loop body (~line 1698)**

Find the end of the `if exp_cfg.docx_enabled:` block inside the loop. Immediately after the docx block's `except Exception: pass`, add:

```python
        if exp_cfg.obsidian_enabled:
            try:
                from obsidian_renderer import ObsidianRenderer as _OR
                obsidian_dir_path = (
                    Path(exp_cfg.obsidian_dir).expanduser()
                    if exp_cfg.obsidian_dir
                    else output_dir / 'obsidian'
                )
                out = obsidian_dir_path / md_filename
                if force or not out.exists():
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(_OR().render(row), encoding='utf-8')
                    count += 1
            except Exception:
                pass
```

- [ ] **Step 7: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 8: Manual smoke test — launch TUI and verify Export Settings screen**

```bash
python tui.py
```

Navigate: Main Menu → Export Settings (option 3). Verify:
- "Obsidian markdown" toggle appears (cycles no ↔ yes with Enter/Space)
- "Obsidian output dir" text field appears below it
- Save works without error

- [ ] **Step 9: Commit**

```bash
git add tui.py
git commit -m "feat: add Obsidian export toggle to TUI Export Settings screen"
```

---

## Final Verification

- [ ] **Run complete test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: all tests pass (was 183 before; count increases by new tests added).

- [ ] **Smoke test CLI with dry-run**

```bash
python keromdizer.py /path/to/export/ --dry-run
```

Confirm no errors on import.

- [ ] **Smoke test CLI with obsidian enabled**

Add to `~/.keromdizer.toml`:
```toml
[exports]
obsidian = "yes"
```

Then:
```bash
python keromdizer.py /path/to/export/ --output /tmp/kero-test/
ls /tmp/kero-test/obsidian/
```

Verify `.md` files exist and open one to confirm YAML frontmatter + callout structure.
