# SQLite DB, JSONL Export, and Tagging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a SQLite database as the live store for all conversation data, retiring manifest.json; enrich records with structured content and auto-inferred tags at import time; export to JSONL; and build a tagging spreadsheet in the TUI's REVIEW screen.

**Architecture:** `DatabaseManager` (`db.py`) is the new source of truth, replacing `manifest.json`. An `inference.py` module runs YAKE keyword extraction and Pygments syntax detection at import time. A `content_parser.py` module splits raw message text into structured prose/code segments. The TUI's REVIEW screen becomes a scrollable table backed by the DB with inline tag editing.

**Tech Stack:** Python stdlib `sqlite3` (DB), `yake` (keyword extraction), `pygments` (syntax detection), existing `bubbletea`/`lipgloss` (TUI). All free, no external API calls.

---

## Task 1: Add runtime dependencies

**Files:**
- Modify: `requirements-dev.txt`
- Modify: `bootstrap.sh`

**Step 1: Add yake and pygments to requirements-dev.txt**

Append to `requirements-dev.txt`:
```
yake
pygments
```

Final file should look like:
```
pytest
git+https://github.com/tbdtechpro/bubbletea.git
git+https://github.com/tbdtechpro/lipgloss.git
yake
pygments
```

**Step 2: Install into venv**

```bash
.venv/bin/pip install yake pygments
```
Expected: both packages install successfully.

**Step 3: Verify imports work**

```bash
.venv/bin/python -c "import yake; import pygments; print('ok')"
```
Expected: `ok`

**Step 4: Update bootstrap.sh — add note about runtime deps**

In `bootstrap.sh`, change the comment on the install step (line 78) from:
```bash
info "Installing dev requirements (pytest)..."
```
to:
```bash
info "Installing requirements (pytest, yake, pygments, bubbletea, lipgloss)..."
```

**Step 5: Commit**

```bash
git add requirements-dev.txt bootstrap.sh
git commit -m "chore: add yake and pygments runtime dependencies"
```

---

## Task 2: BranchConfig model and config loader

**Files:**
- Modify: `models.py`
- Modify: `config.py`
- Create: `tests/test_branch_config.py`

**Step 1: Write failing tests**

Create `tests/test_branch_config.py`:
```python
import pytest
from pathlib import Path
from models import BranchConfig
from config import load_branch_config, load_db_path


def test_branch_config_defaults():
    cfg = BranchConfig()
    assert cfg.import_branches == 'all'
    assert cfg.export_markdown == 'all'
    assert cfg.export_jsonl == 'all'


def test_load_branch_config_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr('config.CONFIG_PATH', tmp_path / 'nonexistent.toml')
    cfg = load_branch_config()
    assert cfg.import_branches == 'all'
    assert cfg.export_markdown == 'all'
    assert cfg.export_jsonl == 'all'


def test_load_branch_config_from_toml(tmp_path, monkeypatch):
    toml = tmp_path / '.keromdizer.toml'
    toml.write_text(
        '[branches]\nimport = "main"\nexport_markdown = "all"\nexport_jsonl = "main"\n',
        encoding='utf-8'
    )
    monkeypatch.setattr('config.CONFIG_PATH', toml)
    cfg = load_branch_config()
    assert cfg.import_branches == 'main'
    assert cfg.export_markdown == 'all'
    assert cfg.export_jsonl == 'main'


def test_load_db_path_default(tmp_path, monkeypatch):
    monkeypatch.setattr('config.CONFIG_PATH', tmp_path / 'nonexistent.toml')
    p = load_db_path()
    assert p == Path.home() / '.keromdizer.db'


def test_load_db_path_from_toml(tmp_path, monkeypatch):
    toml = tmp_path / '.keromdizer.toml'
    toml.write_text('[database]\npath = "/tmp/test.db"\n', encoding='utf-8')
    monkeypatch.setattr('config.CONFIG_PATH', toml)
    p = load_db_path()
    assert p == Path('/tmp/test.db')
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_branch_config.py -v
```
Expected: ImportError or AttributeError — `BranchConfig` and `load_branch_config` don't exist yet.

**Step 3: Add BranchConfig to models.py**

Add after the `PersonaConfig` dataclass in `models.py`:
```python
@dataclass
class BranchConfig:
    import_branches: str = 'all'   # 'main' | 'all'
    export_markdown: str = 'all'   # 'main' | 'all'
    export_jsonl: str = 'all'      # 'main' | 'all'
```

**Step 4: Add load_branch_config and load_db_path to config.py**

Add to `config.py` (after the existing `load_persona` function):
```python
from models import PersonaConfig, BranchConfig  # update the import at top


def load_branch_config() -> BranchConfig:
    """Load branch handling config from ~/.keromdizer.toml."""
    data: dict = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'rb') as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError:
            pass
    b = data.get('branches', {})
    return BranchConfig(
        import_branches=b.get('import', 'all'),
        export_markdown=b.get('export_markdown', 'all'),
        export_jsonl=b.get('export_jsonl', 'all'),
    )


def load_db_path() -> Path:
    """Return configured DB path, defaulting to ~/.keromdizer.db."""
    data: dict = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'rb') as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError:
            pass
    raw = data.get('database', {}).get('path', '')
    if raw:
        return Path(raw).expanduser()
    return Path.home() / '.keromdizer.db'
```

Also update the existing import at the top of `config.py` from:
```python
from models import PersonaConfig
```
to:
```python
from models import PersonaConfig, BranchConfig
```

**Step 5: Run tests to verify they pass**

```bash
pytest tests/test_branch_config.py -v
```
Expected: 5 passed.

**Step 6: Run full test suite to verify no regressions**

```bash
pytest tests/ -v
```
Expected: all existing tests still pass.

**Step 7: Commit**

```bash
git add models.py config.py tests/test_branch_config.py
git commit -m "feat: add BranchConfig dataclass and load_branch_config/load_db_path to config"
```

---

## Task 3: Content parser (prose/code segment extraction)

**Files:**
- Create: `content_parser.py`
- Create: `tests/test_content_parser.py`

**Step 1: Write failing tests**

Create `tests/test_content_parser.py`:
```python
import pytest
from content_parser import parse_content, ContentSegment


def test_plain_prose_only():
    segments = parse_content('Hello world, no code here.')
    assert len(segments) == 1
    assert segments[0].type == 'prose'
    assert segments[0].text == 'Hello world, no code here.'
    assert segments[0].language is None


def test_single_code_block_with_hint():
    text = 'Here is code:\n```python\nprint("hi")\n```\nThat is all.'
    segments = parse_content(text)
    assert len(segments) == 3
    assert segments[0].type == 'prose'
    assert segments[1].type == 'code'
    assert segments[1].language == 'python'
    assert segments[1].text == 'print("hi")\n'
    assert segments[2].type == 'prose'


def test_code_block_without_hint_gets_language_or_none():
    text = '```\ndef foo():\n    pass\n```'
    segments = parse_content(text)
    assert len(segments) == 1
    assert segments[0].type == 'code'
    # language may be guessed by Pygments or None — just check it's a str or None
    assert segments[0].language is None or isinstance(segments[0].language, str)


def test_multiple_code_blocks():
    text = '```python\nx = 1\n```\nSome text.\n```bash\necho hi\n```'
    segments = parse_content(text)
    types = [s.type for s in segments]
    assert types.count('code') == 2
    langs = [s.language for s in segments if s.type == 'code']
    assert 'python' in langs
    assert 'bash' in langs


def test_empty_string():
    assert parse_content('') == []


def test_code_block_only():
    text = '```js\nconsole.log(1)\n```'
    segments = parse_content(text)
    assert len(segments) == 1
    assert segments[0].type == 'code'
    assert segments[0].language == 'js'


def test_prose_stripped_of_surrounding_whitespace():
    text = '\n\nHello\n\n```python\npass\n```\n\nWorld\n\n'
    segments = parse_content(text)
    prose_segs = [s for s in segments if s.type == 'prose']
    assert prose_segs[0].text == 'Hello'
    assert prose_segs[1].text == 'World'
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_content_parser.py -v
```
Expected: `ImportError: No module named 'content_parser'`

**Step 3: Implement content_parser.py**

Create `content_parser.py`:
```python
import re
from dataclasses import dataclass

FENCE_RE = re.compile(r'```([a-zA-Z0-9+\-._]*)\n(.*?)```', re.DOTALL)


@dataclass
class ContentSegment:
    type: str            # 'prose' | 'code'
    text: str
    language: str | None = None


def parse_content(text: str) -> list[ContentSegment]:
    """Split message text into alternating prose and code segments."""
    if not text:
        return []
    segments: list[ContentSegment] = []
    last_end = 0
    for match in FENCE_RE.finditer(text):
        prose = text[last_end:match.start()].strip()
        if prose:
            segments.append(ContentSegment(type='prose', text=prose))
        lang_hint = match.group(1).strip().lower()
        code_text = match.group(2)
        language = lang_hint if lang_hint else _guess_language(code_text)
        segments.append(ContentSegment(type='code', text=code_text, language=language))
        last_end = match.end()
    tail = text[last_end:].strip()
    if tail:
        segments.append(ContentSegment(type='prose', text=tail))
    return segments


def _guess_language(code: str) -> str | None:
    try:
        from pygments.lexers import guess_lexer
        lexer = guess_lexer(code)
        # Reject the generic 'text' lexer — return None instead
        if lexer.name.lower() in ('text only', 'text'):
            return None
        return lexer.aliases[0] if lexer.aliases else lexer.name.lower()
    except Exception:
        return None
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_content_parser.py -v
```
Expected: 7 passed.

**Step 5: Run full suite**

```bash
pytest tests/ -v
```
Expected: all pass.

**Step 6: Commit**

```bash
git add content_parser.py tests/test_content_parser.py
git commit -m "feat: add content_parser — split message text into prose/code segments"
```

---

## Task 4: SQLite database manager

**Files:**
- Create: `db.py`
- Create: `tests/test_db.py`

**Step 1: Write failing tests**

Create `tests/test_db.py`:
```python
import json
import pytest
from pathlib import Path
from db import DatabaseManager


@pytest.fixture
def db(tmp_path):
    return DatabaseManager(tmp_path / 'test.db')


def test_db_creates_schema(db):
    # If schema is wrong, other tests would fail — just verify tables exist
    tables = db._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {row[0] for row in tables}
    assert 'conversations' in names
    assert 'branches' in names


def test_needs_update_true_when_not_in_db(db):
    assert db.needs_update('conv-abc', '2026-01-14T00:00:00+00:00') is True


def test_upsert_and_needs_update_false(db):
    db.upsert_conversation(
        conversation_id='conv-1',
        provider='chatgpt',
        title='Test',
        create_time='2026-01-14T00:00:00+00:00',
        update_time='2026-01-14T00:00:00+00:00',
        model_slug='gpt-4o',
        branch_count=1,
        branches=[{
            'branch_id': 'conv-1__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': ['python'],
            'inferred_syntax': ['python'],
        }],
    )
    assert db.needs_update('conv-1', '2026-01-14T00:00:00+00:00') is False


def test_needs_update_true_when_newer(db):
    db.upsert_conversation(
        conversation_id='conv-2',
        provider='chatgpt',
        title='Old',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-01T00:00:00+00:00',
        model_slug=None,
        branch_count=1,
        branches=[{
            'branch_id': 'conv-2__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': [],
            'inferred_syntax': [],
        }],
    )
    assert db.needs_update('conv-2', '2026-01-14T00:00:00+00:00') is True


def test_list_branches_returns_all(db):
    for i in range(3):
        db.upsert_conversation(
            conversation_id=f'conv-{i}',
            provider='chatgpt',
            title=f'Conv {i}',
            create_time='2026-01-01T00:00:00+00:00',
            update_time='2026-01-01T00:00:00+00:00',
            model_slug=None,
            branch_count=1,
            branches=[{
                'branch_id': f'conv-{i}__branch_1',
                'branch_index': 1,
                'is_main_branch': True,
                'messages': [],
                'inferred_tags': [],
                'inferred_syntax': [],
            }],
        )
    rows = db.list_branches()
    assert len(rows) == 3


def test_list_branches_main_only(db):
    db.upsert_conversation(
        conversation_id='conv-br',
        provider='chatgpt',
        title='Branched',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-01T00:00:00+00:00',
        model_slug=None,
        branch_count=2,
        branches=[
            {'branch_id': 'conv-br__branch_1', 'branch_index': 1, 'is_main_branch': True,
             'messages': [], 'inferred_tags': [], 'inferred_syntax': []},
            {'branch_id': 'conv-br__branch_2', 'branch_index': 2, 'is_main_branch': False,
             'messages': [], 'inferred_tags': [], 'inferred_syntax': []},
        ],
    )
    all_rows = db.list_branches()
    main_rows = db.list_branches(main_only=True)
    assert len(all_rows) == 2
    assert len(main_rows) == 1
    assert main_rows[0]['branch_index'] == 1


def test_update_branch_tags(db):
    db.upsert_conversation(
        conversation_id='conv-tag',
        provider='deepseek',
        title='Tagged',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-01T00:00:00+00:00',
        model_slug=None,
        branch_count=1,
        branches=[{
            'branch_id': 'conv-tag__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': [],
            'inferred_syntax': [],
        }],
    )
    db.update_branch_tags(
        branch_id='conv-tag__branch_1',
        tags=['python', 'async'],
        project='MyProject',
        category='debugging',
        syntax=['python'],
    )
    row = db.get_branch('conv-tag__branch_1')
    assert row['tags'] == ['python', 'async']
    assert row['project'] == 'MyProject'
    assert row['category'] == 'debugging'
    assert row['syntax'] == ['python']


def test_get_all_tags_for_autocomplete(db):
    db.upsert_conversation(
        conversation_id='conv-ac',
        provider='chatgpt',
        title='AC',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-01T00:00:00+00:00',
        model_slug=None,
        branch_count=1,
        branches=[{
            'branch_id': 'conv-ac__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': [],
            'inferred_syntax': [],
        }],
    )
    db.update_branch_tags('conv-ac__branch_1', ['alpha', 'beta'], None, None, [])
    tags = db.get_all_tags()
    assert 'alpha' in tags
    assert 'beta' in tags


def test_upsert_overwrites_existing(db):
    for update_time in ['2026-01-01T00:00:00+00:00', '2026-01-14T00:00:00+00:00']:
        db.upsert_conversation(
            conversation_id='conv-ow',
            provider='chatgpt',
            title='Updated Title',
            create_time='2026-01-01T00:00:00+00:00',
            update_time=update_time,
            model_slug='gpt-4o',
            branch_count=1,
            branches=[{
                'branch_id': 'conv-ow__branch_1',
                'branch_index': 1,
                'is_main_branch': True,
                'messages': [],
                'inferred_tags': [],
                'inferred_syntax': [],
            }],
        )
    rows = db.list_branches()
    assert len(rows) == 1  # not duplicated
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_db.py -v
```
Expected: `ImportError: No module named 'db'`

**Step 3: Implement db.py**

Create `db.py`:
```python
import json
import sqlite3
from pathlib import Path


_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    provider        TEXT NOT NULL,
    title           TEXT,
    create_time     TEXT,
    update_time     TEXT,
    model_slug      TEXT,
    branch_count    INTEGER
);

CREATE TABLE IF NOT EXISTS branches (
    branch_id       TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id),
    branch_index    INTEGER NOT NULL,
    is_main_branch  INTEGER NOT NULL DEFAULT 1,
    messages        TEXT NOT NULL DEFAULT '[]',
    tags            TEXT NOT NULL DEFAULT '[]',
    project         TEXT,
    category        TEXT,
    syntax          TEXT NOT NULL DEFAULT '[]',
    inferred_tags   TEXT NOT NULL DEFAULT '[]',
    inferred_syntax TEXT NOT NULL DEFAULT '[]'
);
"""


class DatabaseManager:
    def __init__(self, db_path: Path):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def needs_update(self, conversation_id: str, update_time: str) -> bool:
        """Return True if conversation is new or has a newer update_time."""
        row = self._conn.execute(
            'SELECT update_time FROM conversations WHERE conversation_id = ?',
            (conversation_id,),
        ).fetchone()
        if row is None:
            return True
        return update_time > (row['update_time'] or '')

    def upsert_conversation(
        self,
        *,
        conversation_id: str,
        provider: str,
        title: str | None,
        create_time: str | None,
        update_time: str | None,
        model_slug: str | None,
        branch_count: int,
        branches: list[dict],
    ) -> None:
        """Insert or replace a conversation and all its branches."""
        self._conn.execute(
            '''INSERT OR REPLACE INTO conversations
               (conversation_id, provider, title, create_time, update_time, model_slug, branch_count)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (conversation_id, provider, title, create_time, update_time, model_slug, branch_count),
        )
        for b in branches:
            # Preserve existing user tags/project/category/syntax on re-import
            existing = self._conn.execute(
                'SELECT tags, project, category, syntax FROM branches WHERE branch_id = ?',
                (b['branch_id'],),
            ).fetchone()
            if existing:
                tags = existing['tags']
                project = existing['project']
                category = existing['category']
                syntax = existing['syntax']
            else:
                tags = '[]'
                project = None
                category = None
                syntax = '[]'
            self._conn.execute(
                '''INSERT OR REPLACE INTO branches
                   (branch_id, conversation_id, branch_index, is_main_branch,
                    messages, tags, project, category, syntax, inferred_tags, inferred_syntax)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    b['branch_id'],
                    conversation_id,
                    b['branch_index'],
                    1 if b['is_main_branch'] else 0,
                    json.dumps(b['messages']),
                    tags,
                    project,
                    category,
                    syntax,
                    json.dumps(b['inferred_tags']),
                    json.dumps(b['inferred_syntax']),
                ),
            )
        self._conn.commit()

    def get_branch(self, branch_id: str) -> dict | None:
        row = self._conn.execute(
            '''SELECT b.*, c.title, c.provider, c.create_time AS conv_create_time,
                      c.model_slug
               FROM branches b
               JOIN conversations c ON b.conversation_id = c.conversation_id
               WHERE b.branch_id = ?''',
            (branch_id,),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_branches(
        self,
        main_only: bool = False,
        offset: int = 0,
        limit: int = 500,
    ) -> list[dict]:
        q = '''SELECT b.branch_id, b.conversation_id, b.branch_index, b.is_main_branch,
                      b.messages, b.tags, b.project, b.category, b.syntax,
                      b.inferred_tags, b.inferred_syntax,
                      c.title, c.provider, c.create_time AS conv_create_time, c.model_slug
               FROM branches b
               JOIN conversations c ON b.conversation_id = c.conversation_id'''
        if main_only:
            q += ' WHERE b.is_main_branch = 1'
        q += ' ORDER BY c.create_time DESC LIMIT ? OFFSET ?'
        rows = self._conn.execute(q, (limit, offset)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def update_branch_tags(
        self,
        branch_id: str,
        tags: list[str],
        project: str | None,
        category: str | None,
        syntax: list[str],
    ) -> None:
        self._conn.execute(
            'UPDATE branches SET tags=?, project=?, category=?, syntax=? WHERE branch_id=?',
            (json.dumps(tags), project, category, json.dumps(syntax), branch_id),
        )
        self._conn.commit()

    def get_all_tags(self) -> list[str]:
        """Return sorted list of all unique user-applied tags (for autocomplete)."""
        rows = self._conn.execute(
            "SELECT tags FROM branches WHERE tags != '[]'"
        ).fetchall()
        seen: set[str] = set()
        for row in rows:
            for tag in json.loads(row['tags']):
                if tag:
                    seen.add(tag)
        return sorted(seen)

    def close(self) -> None:
        self._conn.close()

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        for json_field in ('messages', 'tags', 'syntax', 'inferred_tags', 'inferred_syntax'):
            if isinstance(d.get(json_field), str):
                d[json_field] = json.loads(d[json_field])
        d['is_main_branch'] = bool(d.get('is_main_branch'))
        return d
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_db.py -v
```
Expected: all passed.

**Step 5: Run full suite**

```bash
pytest tests/ -v
```
Expected: all pass.

**Step 6: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: add DatabaseManager with SQLite schema — conversations and branches tables"
```

---

## Task 5: Inference engine (YAKE + Pygments)

**Files:**
- Create: `inference.py`
- Create: `tests/test_inference.py`

**Step 1: Write failing tests**

Create `tests/test_inference.py`:
```python
import pytest
from content_parser import ContentSegment
from inference import infer_tags, infer_syntax, build_full_text


def test_infer_tags_returns_list_of_strings():
    text = 'Python async programming with asyncio event loops and coroutines'
    tags = infer_tags(text)
    assert isinstance(tags, list)
    assert all(isinstance(t, str) for t in tags)


def test_infer_tags_empty_text():
    assert infer_tags('') == []
    assert infer_tags('   ') == []


def test_infer_tags_respects_top_n():
    text = ' '.join(['word'] * 5 + ['python', 'async', 'loop', 'coroutine', 'event',
                                      'thread', 'socket', 'buffer', 'stream', 'queue',
                                      'channel', 'future', 'task'])
    tags = infer_tags(text, top_n=5)
    assert len(tags) <= 5


def test_infer_syntax_from_segments():
    segments = [
        ContentSegment(type='prose', text='Some prose'),
        ContentSegment(type='code', language='python', text='x = 1'),
        ContentSegment(type='code', language='bash', text='echo hi'),
        ContentSegment(type='code', language='python', text='y = 2'),  # duplicate
    ]
    langs = infer_syntax(segments)
    assert langs == ['python', 'bash']  # deduplicated, order preserved


def test_infer_syntax_ignores_prose():
    segments = [ContentSegment(type='prose', text='Just text, no code.')]
    assert infer_syntax(segments) == []


def test_infer_syntax_skips_none_language():
    segments = [
        ContentSegment(type='code', language=None, text='???'),
        ContentSegment(type='code', language='js', text='console.log()'),
    ]
    langs = infer_syntax(segments)
    assert langs == ['js']


def test_build_full_text_concatenates_prose():
    segments = [
        ContentSegment(type='prose', text='Hello world'),
        ContentSegment(type='code', language='python', text='print()'),
        ContentSegment(type='prose', text='Goodbye'),
    ]
    text = build_full_text(segments)
    assert 'Hello world' in text
    assert 'Goodbye' in text
    assert 'print()' in text
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_inference.py -v
```
Expected: `ImportError: No module named 'inference'`

**Step 3: Implement inference.py**

Create `inference.py`:
```python
import yake
from content_parser import ContentSegment


def infer_tags(text: str, top_n: int = 10) -> list[str]:
    """Extract top_n keywords from text using YAKE."""
    if not text or not text.strip():
        return []
    extractor = yake.KeywordExtractor(lan='en', n=1, dedupLim=0.9, top=top_n)
    results = extractor.extract_keywords(text)
    return [kw for kw, _score in results]


def infer_syntax(segments: list[ContentSegment]) -> list[str]:
    """Return deduplicated list of code languages, in order of first appearance."""
    seen: list[str] = []
    for seg in segments:
        if seg.type == 'code' and seg.language and seg.language not in seen:
            seen.append(seg.language)
    return seen


def build_full_text(segments: list[ContentSegment]) -> str:
    """Concatenate all segment text for keyword extraction input."""
    return '\n'.join(seg.text for seg in segments)
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_inference.py -v
```
Expected: all passed.

**Step 5: Run full suite**

```bash
pytest tests/ -v
```
Expected: all pass.

**Step 6: Commit**

```bash
git add inference.py tests/test_inference.py
git commit -m "feat: add inference module — YAKE keyword extraction and Pygments syntax detection"
```

---

## Task 6: Import pipeline refactor — DB integration, retire manifest.json

**Files:**
- Modify: `file_manager.py`
- Modify: `keromdizer.py`
- Modify: `tests/test_file_manager.py` (remove manifest-related tests or adapt)

**Background:** `FileManager` currently owns `manifest.json` for deduplication. We transfer that responsibility to `DatabaseManager`. `FileManager` still handles `.md` file writing, filename sanitisation, and asset copying. The `_used_filenames` set is seeded from the DB's existing branch records instead of the manifest.

**Step 1: Read and understand the existing file_manager tests**

```bash
pytest tests/test_file_manager.py -v
```
Note which tests exercise `needs_update`, `save_manifest`, and `_load_manifest` — these will be removed.

**Step 2: Adapt file_manager.py — remove manifest, add _used_filenames from DB**

In `file_manager.py`, replace the constructor and manifest-related methods:

Remove these methods entirely:
- `_load_manifest`
- `save_manifest`
- `needs_update`

Change `__init__` from:
```python
def __init__(self, output_dir: Path):
    self.output_dir = Path(output_dir)
    self.assets_dir = self.output_dir / 'assets'
    self.manifest_path = self.output_dir / 'manifest.json'
    self._manifest: dict = self._load_manifest()
    self._used_filenames: set[str] = {
        f for entry in self._manifest.values() for f in entry.get('files', [])
    }
```

to:
```python
def __init__(self, output_dir: Path, used_filenames: set[str] | None = None):
    self.output_dir = Path(output_dir)
    self.assets_dir = self.output_dir / 'assets'
    self._used_filenames: set[str] = used_filenames or set()
```

Change `write` from updating `self._manifest` to just writing the file:
```python
def write(self, filename: str, content: str) -> None:
    self.output_dir.mkdir(parents=True, exist_ok=True)
    filepath = self.output_dir / filename
    filepath.write_text(content, encoding='utf-8')
```

(The `conversation` parameter is removed — callers no longer pass it.)

**Step 3: Update tests/test_file_manager.py**

Remove tests for `needs_update`, `save_manifest`, `_load_manifest`. Update any test that calls `file_mgr.write(filename, content, conv)` to `file_mgr.write(filename, content)`. Run tests to confirm they still pass.

**Step 4: Update keromdizer.py to use DatabaseManager**

Replace the import pipeline in `keromdizer.py`. The full updated `main()`:

```python
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from config import load_persona, load_branch_config, load_db_path
from parser_factory import build_parser
from renderer import MarkdownRenderer
from file_manager import FileManager
from db import DatabaseManager
from content_parser import parse_content
from inference import infer_tags, infer_syntax, build_full_text


def _to_iso(ts: float | str | None) -> str | None:
    if ts is None:
        return None
    if isinstance(ts, str):
        return ts
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def main():
    arg_parser = argparse.ArgumentParser(
        description='Convert a ChatGPT or DeepSeek export folder to GFM markdown files.'
    )
    arg_parser.add_argument('export_folder', type=Path)
    arg_parser.add_argument('--output', type=Path, default=Path('./output'))
    arg_parser.add_argument('--dry-run', action='store_true')
    arg_parser.add_argument('--user-name', default=None)
    arg_parser.add_argument('--assistant-name', default=None)
    arg_parser.add_argument('--source', choices=['chatgpt', 'deepseek'], default=None)
    arg_parser.add_argument(
        '--export-jsonl',
        type=Path,
        default=None,
        metavar='PATH',
        help='Also write a JSONL export to PATH after importing',
    )
    args = arg_parser.parse_args()

    if not args.export_folder.is_dir():
        print(f'Error: {args.export_folder} is not a directory', file=sys.stderr)
        sys.exit(1)

    branch_cfg = load_branch_config()
    db_path = load_db_path()
    db = DatabaseManager(db_path)

    conv_parser, provider = build_parser(args.export_folder, source=args.source)
    try:
        conversations = conv_parser.parse()
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    try:
        persona = load_persona(
            provider=provider,
            user_name=args.user_name,
            assistant_name=args.assistant_name,
        )
    except ValueError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    renderer = MarkdownRenderer(persona)

    # Seed used filenames from DB to prevent cross-run collisions
    existing_branches = db.list_branches()
    # (filenames are not stored in DB — FileManager tracks them in-memory per run)
    file_mgr = FileManager(args.output)

    written = 0
    skipped = 0

    for conv in conversations:
        update_time_iso = _to_iso(conv.update_time)
        if not db.needs_update(conv.id, update_time_iso or ''):
            skipped += 1
            continue

        # Filter branches by import config
        branches_to_import = (
            [b for b in conv.branches if b.branch_index == 1]
            if branch_cfg.import_branches == 'main'
            else conv.branches
        )

        db_branches = []
        for branch in branches_to_import:
            # Resolve image refs in messages (mutates msg.text)
            for msg in branch.messages:
                resolved = {}
                for file_id in msg.image_refs:
                    actual_name = file_mgr.copy_asset(args.export_folder, file_id)
                    if actual_name:
                        resolved[file_id] = actual_name
                    else:
                        print(f'Warning: image not found in export: {file_id}', file=sys.stderr)
                for old_id, new_name in resolved.items():
                    msg.text = msg.text.replace(f'assets/{old_id})', f'assets/{new_name})')

            # Parse structured content and run inference
            all_segments = []
            msg_records = []
            for msg in branch.messages:
                segments = parse_content(msg.text)
                all_segments.extend(segments)
                msg_records.append({
                    'role': msg.role,
                    'timestamp': _to_iso(msg.create_time),
                    'content': [
                        {'type': s.type, 'text': s.text,
                         **(({'language': s.language}) if s.language else {})}
                        for s in segments
                    ],
                })

            full_text = build_full_text(all_segments)
            i_tags = infer_tags(full_text)
            i_syntax = infer_syntax(all_segments)

            db_branches.append({
                'branch_id': f'{conv.id}__branch_{branch.branch_index}',
                'branch_index': branch.branch_index,
                'is_main_branch': branch.branch_index == 1,
                'messages': msg_records,
                'inferred_tags': i_tags,
                'inferred_syntax': i_syntax,
            })

            # Write markdown (filtered by export_markdown config)
            if branch_cfg.export_markdown == 'main' and branch.branch_index != 1:
                continue
            content = renderer.render(conv, branch)
            filename = file_mgr.make_filename(conv, branch)
            if args.dry_run:
                branch_label = f' (branch {branch.branch_index})' if len(conv.branches) > 1 else ''
                print(f'  Would write: {args.output / filename}{branch_label}')
            else:
                file_mgr.write(filename, content)
                written += 1

        if not args.dry_run and db_branches:
            db.upsert_conversation(
                conversation_id=conv.id,
                provider=provider,
                title=conv.title,
                create_time=_to_iso(conv.create_time),
                update_time=update_time_iso,
                model_slug=conv.model_slug,
                branch_count=len(conv.branches),
                branches=db_branches,
            )

    if not args.dry_run:
        if args.export_jsonl:
            from jsonl_exporter import export_jsonl
            export_jsonl(db, args.export_jsonl, branch_mode=branch_cfg.export_jsonl)
            print(f'JSONL exported to {args.export_jsonl}')
        print(f'Done. Written: {written} file(s), skipped {skipped} up-to-date conversation(s).')
    else:
        total_would_write = sum(
            len([b for b in c.branches
                 if branch_cfg.export_markdown == 'all' or b.branch_index == 1])
            for c in conversations
            if db.needs_update(c.id, _to_iso(c.update_time) or '')
        )
        print(f'Dry run complete. Would write ~{total_would_write} file(s), skip {skipped} conversation(s).')

    db.close()


if __name__ == '__main__':
    main()
```

**Step 5: Run the full test suite**

```bash
pytest tests/ -v
```
Expected: all pass. The TUI tests should still pass because they don't exercise the CLI pipeline directly.

**Step 6: Manual smoke test with real export**

```bash
python keromdizer.py "/home/matt/Downloads/27acb0dfd0a3c5fc91e10df3ec41412e00ff7879d440e4504e23ce0810ffbfff-2026-01-14-04-16-34-d9369f62a9184a8b86ce547d614186fb/" --output /tmp/kero-test-output
```
Expected: completion message, `~/.keromdizer.db` created, `/tmp/kero-test-output/` has .md files.

Second run (deduplication):
```bash
python keromdizer.py "...same folder..." --output /tmp/kero-test-output
```
Expected: `Written: 0 file(s), skipped 391 up-to-date conversation(s).`

**Step 7: Commit**

```bash
git add keromdizer.py file_manager.py tests/test_file_manager.py
git commit -m "feat: integrate DatabaseManager into import pipeline, retire manifest.json"
```

---

## Task 7: JSONL exporter

**Files:**
- Create: `jsonl_exporter.py`
- Create: `tests/test_jsonl_exporter.py`

**Step 1: Write failing tests**

Create `tests/test_jsonl_exporter.py`:
```python
import json
import pytest
from pathlib import Path
from db import DatabaseManager
from jsonl_exporter import export_jsonl


@pytest.fixture
def populated_db(tmp_path):
    db = DatabaseManager(tmp_path / 'test.db')
    for i in range(3):
        is_main = (i % 2 == 0)
        db.upsert_conversation(
            conversation_id=f'conv-{i}',
            provider='chatgpt',
            title=f'Conversation {i}',
            create_time='2026-01-01T00:00:00+00:00',
            update_time='2026-01-01T00:00:00+00:00',
            model_slug='gpt-4o',
            branch_count=1,
            branches=[{
                'branch_id': f'conv-{i}__branch_1',
                'branch_index': 1,
                'is_main_branch': True,
                'messages': [{'role': 'user', 'timestamp': None,
                              'content': [{'type': 'prose', 'text': 'Hello'}]}],
                'inferred_tags': ['test'],
                'inferred_syntax': [],
            }],
        )
    return db


def test_export_jsonl_creates_file(populated_db, tmp_path):
    out = tmp_path / 'export.jsonl'
    export_jsonl(populated_db, out, branch_mode='all')
    assert out.exists()


def test_export_jsonl_line_count(populated_db, tmp_path):
    out = tmp_path / 'export.jsonl'
    export_jsonl(populated_db, out, branch_mode='all')
    lines = out.read_text().strip().splitlines()
    assert len(lines) == 3


def test_export_jsonl_valid_json_per_line(populated_db, tmp_path):
    out = tmp_path / 'export.jsonl'
    export_jsonl(populated_db, out, branch_mode='all')
    for line in out.read_text().strip().splitlines():
        obj = json.loads(line)
        assert 'id' in obj
        assert 'conversation_id' in obj
        assert 'provider' in obj
        assert 'messages' in obj
        assert 'inferred_tags' in obj
        assert 'tags' in obj
        assert 'schema_version' in obj


def test_export_jsonl_schema_version(populated_db, tmp_path):
    out = tmp_path / 'export.jsonl'
    export_jsonl(populated_db, out, branch_mode='all')
    obj = json.loads(out.read_text().splitlines()[0])
    assert obj['schema_version'] == '1'


def test_export_jsonl_main_only(tmp_path):
    db = DatabaseManager(tmp_path / 'test.db')
    db.upsert_conversation(
        conversation_id='conv-b',
        provider='chatgpt',
        title='Branched',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-01T00:00:00+00:00',
        model_slug=None,
        branch_count=2,
        branches=[
            {'branch_id': 'conv-b__branch_1', 'branch_index': 1, 'is_main_branch': True,
             'messages': [], 'inferred_tags': [], 'inferred_syntax': []},
            {'branch_id': 'conv-b__branch_2', 'branch_index': 2, 'is_main_branch': False,
             'messages': [], 'inferred_tags': [], 'inferred_syntax': []},
        ],
    )
    out = tmp_path / 'export.jsonl'
    export_jsonl(db, out, branch_mode='main')
    lines = out.read_text().strip().splitlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj['is_main_branch'] is True
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_jsonl_exporter.py -v
```
Expected: `ImportError: No module named 'jsonl_exporter'`

**Step 3: Implement jsonl_exporter.py**

Create `jsonl_exporter.py`:
```python
import json
from pathlib import Path
from db import DatabaseManager


def export_jsonl(db: DatabaseManager, output_path: Path, branch_mode: str = 'all') -> None:
    """Write all branches from DB to a JSONL file, one record per line."""
    main_only = branch_mode == 'main'
    branches = db.list_branches(main_only=main_only)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for b in branches:
            record = {
                'schema_version': '1',
                'id': b['branch_id'],
                'conversation_id': b['conversation_id'],
                'branch_index': b['branch_index'],
                'is_main_branch': b['is_main_branch'],
                'provider': b['provider'],
                'title': b['title'],
                'create_time': b['conv_create_time'],
                'model_slug': b['model_slug'],
                'tags': b['tags'],
                'project': b['project'],
                'category': b['category'],
                'syntax': b['syntax'],
                'inferred_tags': b['inferred_tags'],
                'inferred_syntax': b['inferred_syntax'],
                'messages': b['messages'],
            }
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_jsonl_exporter.py -v
```
Expected: all passed.

**Step 5: Run full suite**

```bash
pytest tests/ -v
```
Expected: all pass.

**Step 6: Commit**

```bash
git add jsonl_exporter.py tests/test_jsonl_exporter.py
git commit -m "feat: add JSONL exporter — export all branches from DB with --export-jsonl flag"
```

---

## Task 8: SETTINGS screen — branch handling toggles

**Files:**
- Modify: `tui.py`
- Modify: `tests/test_tui.py`

**Background:** The SETTINGS screen currently has 4 text input fields + a Save button (cursor indices 0–4). We add 3 toggle rows (cycle `main` ↔ `all` on Enter/Space) after the text fields, making the tab order: 0 output_dir, 1 user_name, 2 chatgpt_assistant, 3 deepseek_assistant, 4 import_branches, 5 export_markdown, 6 export_jsonl, 7 Save.

**Step 1: Write failing tests**

Add to `tests/test_tui.py`:
```python
def test_settings_branch_toggles_present_in_view():
    model = AppModel()
    model.screen = Screen.SETTINGS
    view = model.view()
    assert 'Import branches' in view
    assert 'Markdown export' in view
    assert 'JSONL export' in view


def test_settings_branch_toggle_cycles_on_enter():
    model = AppModel()
    model.screen = Screen.SETTINGS
    # Navigate to import_branches toggle (index 4)
    for _ in range(4):
        model, _ = model.update(tea.KeyMsg(key='tab'))
    assert model.st_cursor == 4
    initial = model.st_values['import_branches']
    model, _ = model.update(tea.KeyMsg(key='enter'))
    assert model.st_values['import_branches'] != initial


def test_settings_tab_wraps_at_8():
    model = AppModel()
    model.screen = Screen.SETTINGS
    for _ in range(8):
        model, _ = model.update(tea.KeyMsg(key='tab'))
    assert model.st_cursor == 0


def test_settings_save_persists_branch_config(tmp_path, monkeypatch):
    import tomllib
    toml_path = tmp_path / '.keromdizer.toml'
    monkeypatch.setattr('tui.Path.home', lambda: tmp_path)
    model = AppModel()
    model.screen = Screen.SETTINGS
    model.st_values['import_branches'] = 'main'
    # Tab to Save button (index 7) and press enter
    for _ in range(7):
        model, _ = model.update(tea.KeyMsg(key='tab'))
    model, _ = model.update(tea.KeyMsg(key='enter'))
    assert toml_path.exists()
    data = tomllib.loads(toml_path.read_text())
    assert data['branches']['import'] == 'main'
```

**Step 2: Run new tests to verify they fail**

```bash
pytest tests/test_tui.py -k "branch_toggle or branch_config or wraps_at_8" -v
```
Expected: FAIL.

**Step 3: Update _load_settings in tui.py**

In `_load_settings`, add branch fields to the returned dict:
```python
branches = data.get('branches', {})
return {
    'output_dir':         data.get('output', {}).get('dir', './output'),
    'user_name':          data.get('user', {}).get('name', ''),
    'chatgpt_assistant':  providers.get('chatgpt', {}).get('assistant_name', ''),
    'deepseek_assistant': providers.get('deepseek', {}).get('assistant_name', ''),
    'import_branches':    branches.get('import', 'all'),
    'export_markdown':    branches.get('export_markdown', 'all'),
    'export_jsonl':       branches.get('export_jsonl', 'all'),
}
```

**Step 4: Update _save_settings in tui.py**

Add branch saving to `_save_settings`:
```python
branches_data = {}
if values.get('import_branches'):
    branches_data['import'] = values['import_branches']
if values.get('export_markdown'):
    branches_data['export_markdown'] = values['export_markdown']
if values.get('export_jsonl'):
    branches_data['export_jsonl'] = values['export_jsonl']
if branches_data:
    data['branches'] = branches_data
```

**Step 5: Update AppModel.__init__ for the new fields**

In `__init__`, update the SETTINGS section:
```python
self.st_fields: list[str] = [
    'output_dir', 'user_name', 'chatgpt_assistant', 'deepseek_assistant',
    'import_branches', 'export_markdown', 'export_jsonl',
]
self.st_labels: dict[str, str] = {
    'output_dir':         'Output directory',
    'user_name':          'User name',
    'chatgpt_assistant':  'ChatGPT assistant name',
    'deepseek_assistant': 'DeepSeek assistant name',
    'import_branches':    'Import branches',
    'export_markdown':    'Markdown export branches',
    'export_jsonl':       'JSONL export branches',
}
self.st_toggle_fields: set[str] = {'import_branches', 'export_markdown', 'export_jsonl'}
```

**Step 6: Update _key_settings to handle toggle fields**

In `_key_settings`, the tab wrap changes to `n_fields + 1` (still the same formula — Save is at `len(st_fields)`). Add toggle handling:

```python
elif self.st_cursor < n_fields:
    field_key = self.st_fields[self.st_cursor]
    if field_key in self.st_toggle_fields:
        # Toggle on enter or space
        if key in ('enter', ' '):
            current = self.st_values.get(field_key, 'all')
            self.st_values[field_key] = 'main' if current == 'all' else 'all'
    else:
        # Text input (existing behaviour)
        current = self.st_values.get(field_key, '')
        if key == 'backspace':
            self.st_values[field_key] = current[:-1]
        elif key == 'ctrl+u':
            self.st_values[field_key] = ''
        elif len(key) == 1:
            self.st_values[field_key] = current + key
    self.st_status = ''
```

**Step 7: Update _view_settings to render toggle fields differently**

In `_view_settings`, update the field rendering loop:
```python
for i, fk in enumerate(self.st_fields):
    label = self.st_labels[fk]
    value = self.st_values.get(fk, '')
    focused = (i == self.st_cursor)
    label_s = sel_style.render(label) if focused else muted_style.render(label)
    if fk in self.st_toggle_fields:
        val_display = sel_style.render(f'[ {value} ]') if focused else muted_style.render(f'  {value}  ')
    else:
        val_display = f'{value}\u2588' if focused else value or muted_style.render('(default)')
    lines.append(f'  {label_s}')
    lines.append(f'  {val_display}')
    lines.append('')
```

**Step 8: Run tests to verify they pass**

```bash
pytest tests/test_tui.py -v
```
Expected: all passed (including the new tests and the existing tab-wrap tests for SETTINGS).

**Step 9: Commit**

```bash
git add tui.py tests/test_tui.py
git commit -m "feat: add branch handling toggles to SETTINGS screen"
```

---

## Task 9: REVIEW screen — scrollable branch table

**Files:**
- Modify: `tui.py`
- Modify: `tests/test_tui.py`

**Background:** The REVIEW screen currently is a placeholder (Esc → MAIN). It will become a scrollable table of branches loaded from the DB. The DB is opened once in `AppModel.__init__` using `load_db_path()`. When the user navigates to REVIEW from MAIN, the branch list is (re)loaded from the DB. If the DB has no records, a friendly empty state is shown.

**Step 1: Write failing tests**

Add to `tests/test_tui.py`:
```python
def test_review_screen_renders_empty_state(monkeypatch):
    # Patch DB to return no branches
    monkeypatch.setattr('tui.DatabaseManager', lambda path: _MockDB([]))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    view = model.view()
    assert 'No conversations' in view or 'empty' in view.lower() or 'import' in view.lower()


def test_review_screen_shows_branch_titles(monkeypatch):
    rows = [
        {'branch_id': 'c1__branch_1', 'conversation_id': 'c1', 'branch_index': 1,
         'is_main_branch': True, 'title': 'My Chat', 'provider': 'chatgpt',
         'conv_create_time': '2026-01-14T00:00:00+00:00', 'model_slug': 'gpt-4o',
         'tags': [], 'project': None, 'category': None, 'syntax': [],
         'inferred_tags': [], 'inferred_syntax': [], 'messages': []},
    ]
    monkeypatch.setattr('tui.DatabaseManager', lambda path: _MockDB(rows))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    view = model.view()
    assert 'My Chat' in view


def test_review_cursor_moves_down(monkeypatch):
    rows = [
        _make_row('c1', 'First Chat'),
        _make_row('c2', 'Second Chat'),
    ]
    monkeypatch.setattr('tui.DatabaseManager', lambda path: _MockDB(rows))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    assert model.rv_cursor == 0
    model, _ = model.update(tea.KeyMsg(key='down'))
    assert model.rv_cursor == 1


def test_review_cursor_does_not_go_below_last(monkeypatch):
    rows = [_make_row('c1', 'Only')]
    monkeypatch.setattr('tui.DatabaseManager', lambda path: _MockDB(rows))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    model, _ = model.update(tea.KeyMsg(key='down'))
    assert model.rv_cursor == 0


def test_review_escape_returns_to_main(monkeypatch):
    monkeypatch.setattr('tui.DatabaseManager', lambda path: _MockDB([]))
    model = AppModel()
    model.screen = Screen.REVIEW
    model, _ = model.update(tea.KeyMsg(key='escape'))
    assert model.screen == Screen.MAIN
```

Add helpers near the top of `test_tui.py` (after imports):
```python
class _MockDB:
    def __init__(self, rows):
        self._rows = rows
    def list_branches(self, main_only=False, offset=0, limit=500):
        return self._rows
    def get_all_tags(self):
        return []
    def update_branch_tags(self, *a, **kw):
        pass
    def close(self):
        pass

def _make_row(conv_id, title):
    return {
        'branch_id': f'{conv_id}__branch_1',
        'conversation_id': conv_id, 'branch_index': 1,
        'is_main_branch': True, 'title': title, 'provider': 'chatgpt',
        'conv_create_time': '2026-01-14T00:00:00+00:00', 'model_slug': 'gpt-4o',
        'tags': [], 'project': None, 'category': None, 'syntax': [],
        'inferred_tags': [], 'inferred_syntax': [], 'messages': [],
    }
```

**Step 2: Run new tests to verify they fail**

```bash
pytest tests/test_tui.py -k "review" -v
```
Expected: FAIL.

**Step 3: Add REVIEW state to AppModel.__init__**

Add DB initialisation and REVIEW state to `__init__`:
```python
# DB (opened lazily — path from config)
from config import load_db_path
from db import DatabaseManager
_db_path = load_db_path()
self._db: DatabaseManager = DatabaseManager(_db_path)

# REVIEW
self.rv_rows: list[dict] = []
self.rv_cursor: int = 0
self.rv_editing: bool = False
```

**Step 4: Add _load_review_data method**

```python
def _load_review_data(self) -> None:
    self.rv_rows = self._db.list_branches()
    self.rv_cursor = max(0, min(self.rv_cursor, len(self.rv_rows) - 1))
```

**Step 5: Update _key_main to load review data on entry**

In `_key_main`, when the user selects "Review" (index 2):
```python
elif key == 'enter' and self.menu_cursor == 2:
    self._load_review_data()
    self.screen = Screen.REVIEW
```

**Step 6: Implement _key_review**

Replace the existing stub:
```python
def _key_review(self, msg):
    if not isinstance(msg, tea.KeyMsg):
        return self, None
    key = msg.key
    if key == 'escape':
        self.screen = Screen.MAIN
    elif key in ('down', 'j') and self.rv_rows:
        self.rv_cursor = min(self.rv_cursor + 1, len(self.rv_rows) - 1)
    elif key in ('up', 'k') and self.rv_rows:
        self.rv_cursor = max(self.rv_cursor - 1, 0)
    elif key == 'enter' and self.rv_rows:
        self.rv_editing = True
        self.screen = Screen.REVIEW  # editing handled in Task 10
    return self, None
```

**Step 7: Implement _view_review**

Replace the placeholder:
```python
def _view_review(self) -> str:
    lines = [self._header('Review & Tag'), '']
    if not self.rv_rows:
        lines.append(muted_style.render('  No conversations in database.'))
        lines.append(muted_style.render('  Run an import first.'))
        lines += ['', self._footer('esc back')]
        return self._panel('\n'.join(lines))

    w = min(self.width - 4, 80)
    title_w = max(20, w - 32)  # leave room for date + provider columns

    # Column headers
    header = (
        f'  {"Date":<12}{"Provider":<10}{"Title":<{title_w}}'
    )
    lines.append(muted_style.render(header))
    lines.append(muted_style.render('  ' + '─' * (w - 4)))

    visible = max(4, self.height - 10)
    start = max(0, min(self.rv_cursor - visible // 2, len(self.rv_rows) - visible))
    start = max(0, start)
    shown = self.rv_rows[start:start + visible]

    for i, row in enumerate(shown):
        idx = start + i
        date_str = (row.get('conv_create_time') or '')[:10]
        provider = (row.get('provider') or '')[:8]
        title = (row.get('title') or 'Untitled')
        if len(title) > title_w - 1:
            title = title[:title_w - 2] + '…'
        tag_indicator = ' [tagged]' if row.get('tags') else ''
        cell = f'  {date_str:<12}{provider:<10}{title}{tag_indicator}'
        if idx == self.rv_cursor:
            lines.append(sel_style.render(cell))
        else:
            lines.append(cell)

    lines += ['', self._footer('↑↓ navigate   enter edit tags   esc back')]
    return self._panel('\n'.join(lines))
```

**Step 8: Run tests to verify they pass**

```bash
pytest tests/test_tui.py -v
```
Expected: all passed.

**Step 9: Commit**

```bash
git add tui.py tests/test_tui.py
git commit -m "feat: implement REVIEW screen with scrollable branch table"
```

---

## Task 10: REVIEW screen — tag editor with autocomplete

**Files:**
- Modify: `tui.py`
- Modify: `tests/test_tui.py`

**Background:** Pressing Enter on a row in the REVIEW table opens a tag editor panel. The editor has fields: Tags (array, comma-separated entry), Project (string), Category (string), Syntax (array). Inferred fields are shown read-only. As the user types in the Tags field, matching existing tags from the DB are shown as autocomplete suggestions. Tab accepts the top suggestion and inserts it with a trailing comma ready for the next tag. Ctrl+S saves to DB.

**Step 1: Write failing tests**

Add to `tests/test_tui.py`:
```python
def test_review_enter_opens_editor(monkeypatch):
    rows = [_make_row('c1', 'Chat')]
    monkeypatch.setattr('tui.DatabaseManager', lambda path: _MockDB(rows))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    model, _ = model.update(tea.KeyMsg(key='enter'))
    assert model.rv_editing is True
    view = model.view()
    assert 'Tags' in view


def test_review_editor_escape_returns_to_table(monkeypatch):
    rows = [_make_row('c1', 'Chat')]
    monkeypatch.setattr('tui.DatabaseManager', lambda path: _MockDB(rows))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    model, _ = model.update(tea.KeyMsg(key='enter'))
    model, _ = model.update(tea.KeyMsg(key='escape'))
    assert model.rv_editing is False


def test_review_editor_typing_updates_tags_draft(monkeypatch):
    rows = [_make_row('c1', 'Chat')]
    monkeypatch.setattr('tui.DatabaseManager', lambda path: _MockDB(rows))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    model, _ = model.update(tea.KeyMsg(key='enter'))
    for ch in 'pyt':
        model, _ = model.update(tea.KeyMsg(key=ch))
    assert 'pyt' in model.rv_edit_values.get('tags_draft', '')


def test_review_editor_autocomplete_shown(monkeypatch):
    class MockDBWithTags(_MockDB):
        def get_all_tags(self):
            return ['python', 'pytest', 'rust']
    rows = [_make_row('c1', 'Chat')]
    monkeypatch.setattr('tui.DatabaseManager', lambda path: MockDBWithTags(rows))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    model, _ = model.update(tea.KeyMsg(key='enter'))
    for ch in 'py':
        model, _ = model.update(tea.KeyMsg(key=ch))
    view = model.view()
    assert 'python' in view or 'pytest' in view


def test_review_editor_ctrl_s_saves(monkeypatch):
    saved = {}
    class MockDBSave(_MockDB):
        def update_branch_tags(self, branch_id, tags, project, category, syntax):
            saved['branch_id'] = branch_id
            saved['tags'] = tags
    rows = [_make_row('c1', 'Chat')]
    monkeypatch.setattr('tui.DatabaseManager', lambda path: MockDBSave(rows))
    model = AppModel()
    model.screen = Screen.REVIEW
    model._load_review_data()
    model, _ = model.update(tea.KeyMsg(key='enter'))
    model.rv_edit_values['tags_draft'] = 'python, async'
    model, _ = model.update(tea.KeyMsg(key='ctrl+s'))
    assert saved.get('branch_id') == 'c1__branch_1'
    assert 'python' in saved.get('tags', [])
    assert 'async' in saved.get('tags', [])
```

**Step 2: Run new tests to verify they fail**

```bash
pytest tests/test_tui.py -k "editor" -v
```
Expected: FAIL.

**Step 3: Add editor state to AppModel.__init__**

Add to the REVIEW section of `__init__`:
```python
self.rv_editing: bool = False
self.rv_edit_field: int = 0   # 0=tags, 1=project, 2=category, 3=syntax
self.rv_edit_values: dict[str, str] = {}
self.rv_autocomplete: list[str] = []
self.rv_all_tags: list[str] = []
self.rv_status: str = ''
```

**Step 4: Add _open_editor and _save_edit helper methods**

```python
def _open_editor(self) -> None:
    if not self.rv_rows:
        return
    row = self.rv_rows[self.rv_cursor]
    self.rv_edit_field = 0
    self.rv_edit_values = {
        'tags_draft':  ', '.join(row.get('tags') or []),
        'project':     row.get('project') or '',
        'category':    row.get('category') or '',
        'syntax_draft': ', '.join(row.get('syntax') or []),
    }
    self.rv_all_tags = self._db.get_all_tags()
    self.rv_autocomplete = []
    self.rv_editing = True
    self.rv_status = ''

def _save_edit(self) -> None:
    if not self.rv_rows:
        return
    row = self.rv_rows[self.rv_cursor]
    tags = [t.strip() for t in self.rv_edit_values.get('tags_draft', '').split(',') if t.strip()]
    project = self.rv_edit_values.get('project', '').strip() or None
    category = self.rv_edit_values.get('category', '').strip() or None
    syntax = [s.strip() for s in self.rv_edit_values.get('syntax_draft', '').split(',') if s.strip()]
    self._db.update_branch_tags(row['branch_id'], tags, project, category, syntax)
    # Update in-memory row so the table reflects the change immediately
    row['tags'] = tags
    row['project'] = project
    row['category'] = category
    row['syntax'] = syntax
    self.rv_all_tags = self._db.get_all_tags()
    self.rv_status = 'ok:Saved'
```

**Step 5: Update _key_review to handle editing**

Update `_key_review`:
```python
def _key_review(self, msg):
    if not isinstance(msg, tea.KeyMsg):
        return self, None
    key = msg.key

    if self.rv_editing:
        edit_fields = ['tags_draft', 'project', 'category', 'syntax_draft']
        n = len(edit_fields)
        if key == 'escape':
            self.rv_editing = False
            self.rv_status = ''
        elif key == 'ctrl+s':
            self._save_edit()
        elif key == 'tab':
            self.rv_edit_field = (self.rv_edit_field + 1) % (n + 1)  # +1 for Save
            self.rv_autocomplete = []
        elif key == 'shift+tab':
            self.rv_edit_field = (self.rv_edit_field - 1) % (n + 1)
            self.rv_autocomplete = []
        elif key == 'enter' and self.rv_edit_field == n:
            self._save_edit()
        elif self.rv_edit_field < n:
            fk = edit_fields[self.rv_edit_field]
            current = self.rv_edit_values.get(fk, '')
            if key == 'backspace':
                self.rv_edit_values[fk] = current[:-1]
            elif key == 'ctrl+u':
                self.rv_edit_values[fk] = ''
            elif len(key) == 1:
                self.rv_edit_values[fk] = current + key
            # Update autocomplete for tags field
            if fk == 'tags_draft':
                partial = self.rv_edit_values[fk].rsplit(',', 1)[-1].strip()
                if partial:
                    self.rv_autocomplete = [
                        t for t in self.rv_all_tags if t.lower().startswith(partial.lower())
                    ][:5]
                else:
                    self.rv_autocomplete = []
        return self, None

    # Not editing — table navigation
    if key == 'escape':
        self.screen = Screen.MAIN
    elif key in ('down', 'j') and self.rv_rows:
        self.rv_cursor = min(self.rv_cursor + 1, len(self.rv_rows) - 1)
    elif key in ('up', 'k') and self.rv_rows:
        self.rv_cursor = max(self.rv_cursor - 1, 0)
    elif key == 'enter' and self.rv_rows:
        self._open_editor()
    return self, None
```

**Step 6: Update _view_review to show editor when rv_editing is True**

Add an editor view branch at the top of `_view_review`:
```python
def _view_review(self) -> str:
    if self.rv_editing and self.rv_rows:
        return self._view_review_editor()
    # ... existing table view ...
```

Add `_view_review_editor` method:
```python
def _view_review_editor(self) -> str:
    row = self.rv_rows[self.rv_cursor]
    lines = [self._header(f'Edit: {(row.get("title") or "Untitled")[:40]}'), '']
    edit_fields = ['tags_draft', 'project', 'category', 'syntax_draft']
    labels = {
        'tags_draft':   'Tags (comma-separated)',
        'project':      'Project',
        'category':     'Category',
        'syntax_draft': 'Syntax (comma-separated)',
    }
    for i, fk in enumerate(edit_fields):
        focused = (i == self.rv_edit_field)
        label = labels[fk]
        value = self.rv_edit_values.get(fk, '')
        label_s = sel_style.render(label) if focused else muted_style.render(label)
        val_display = f'{value}\u2588' if focused else value or muted_style.render('(empty)')
        lines.append(f'  {label_s}')
        lines.append(f'  {val_display}')
        # Autocomplete suggestions under the tags field
        if focused and fk == 'tags_draft' and self.rv_autocomplete:
            lines.append(muted_style.render('  Suggestions: ' + '  '.join(self.rv_autocomplete[:5])))
        lines.append('')

    # Read-only inferred section
    lines.append(muted_style.render('  Inferred tags:   ' + ', '.join(row.get('inferred_tags') or [])))
    lines.append(muted_style.render('  Inferred syntax: ' + ', '.join(row.get('inferred_syntax') or [])))
    lines.append('')

    # Save button
    save_focused = (self.rv_edit_field == len(edit_fields))
    btn = sel_style.render('[ Save ]') if save_focused else muted_style.render('[ Save ]')
    lines.append(f'  {btn}')

    if self.rv_status:
        prefix, _, rest = self.rv_status.partition(':')
        s = success_style.render(rest) if prefix == 'ok' else error_style.render(rest)
        lines += ['', f'  {s}']

    lines += ['', self._footer('tab next field   ctrl+s save   esc back')]
    return self._panel('\n'.join(lines))
```

**Step 7: Run tests to verify they pass**

```bash
pytest tests/test_tui.py -v
```
Expected: all passed.

**Step 8: Run full suite**

```bash
pytest tests/ -v
```
Expected: all pass.

**Step 9: Commit**

```bash
git add tui.py tests/test_tui.py
git commit -m "feat: implement REVIEW tag editor with autocomplete and DB persistence"
```

---

## Task 11: Integration verification and documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `memory/MEMORY.md` (auto-memory)

**Step 1: Run complete test suite**

```bash
pytest tests/ -v
```
Expected: all tests pass. Check total count — should be ~160+ (was 131 before this feature).

**Step 2: Full end-to-end smoke test**

```bash
# Import with DB
python keromdizer.py "/path/to/chatgpt-export/" --output /tmp/kero-test

# Verify DB was created
ls -lh ~/.keromdizer.db

# Export JSONL
python keromdizer.py "/path/to/chatgpt-export/" --output /tmp/kero-test --export-jsonl /tmp/kero-test/export.jsonl

# Inspect JSONL
head -n 1 /tmp/kero-test/export.jsonl | python -m json.tool | head -40

# Launch TUI and verify REVIEW screen shows conversations
python tui.py
```

**Step 3: Update CLAUDE.md**

Update the Architecture section, Key Files table, and Output Format section to reflect:
- New files: `db.py`, `content_parser.py`, `inference.py`, `jsonl_exporter.py`
- `manifest.json` retirement
- `BranchConfig` and `load_branch_config`/`load_db_path` in `config.py`
- REVIEW screen functionality
- `--export-jsonl` CLI flag

**Step 4: Final commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for feature #20 — DB, JSONL export, tagging"
```
