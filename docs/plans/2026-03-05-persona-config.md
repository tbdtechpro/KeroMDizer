# Persona Config Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow users to configure custom display names for user and assistant speaker labels via `~/.keromdizer.toml` and CLI flags, with per-provider assistant name defaults.

**Architecture:** New `PersonaConfig` dataclass in `models.py` holds resolved names. New `config.py` loads `~/.keromdizer.toml` (using `tomllib`, stdlib in Python 3.11+) and resolves names through a 4-level fallback chain. `MarkdownRenderer` accepts `PersonaConfig` in its constructor. CLI wires it all together with two new optional flags.

**Tech Stack:** Python 3.11+ stdlib only (`tomllib`, `dataclasses`, `pathlib`). pytest with `monkeypatch` for config tests.

---

### Task 1: Bump Python minimum version to 3.11

`tomllib` is Python 3.11+ stdlib. The project previously required 3.10+.

**Files:**
- Modify: `bootstrap.sh:8` (MIN_PYTHON_MINOR variable)
- Modify: `bootstrap.sh:38` (candidate list)
- Modify: `bootstrap.sh:50` (error message)
- Modify: `CLAUDE.md` (Python Version section)

**Step 1: Edit bootstrap.sh**

Change line 8:
```bash
MIN_PYTHON_MINOR=11  # Requires Python 3.11+
```

Change line 38 — remove `python3.10` from the candidate list:
```bash
for candidate in python3.12 python3.11 python3; do
```

Change line 50 — update the error message:
```bash
    info "Python 3.11+ not found — installing python3.12 via apt..."
```

**Step 2: Edit CLAUDE.md Python Version section**

Find:
```
Requires **Python 3.10+** — uses `X | Y` union type syntax and `list[str]` generics. Ubuntu 24.04 ships Python 3.12 by default. `bootstrap.sh` handles installation if needed.
```

Replace with:
```
Requires **Python 3.11+** — uses `X | Y` union type syntax, `list[str]` generics, and `tomllib` (stdlib). Ubuntu 24.04 ships Python 3.12 by default. `bootstrap.sh` handles installation if needed.
```

**Step 3: Verify Python version in current venv**

```bash
python --version
```
Expected: `Python 3.11.x` or `3.12.x`

**Step 4: Commit**

```bash
git add bootstrap.sh CLAUDE.md
git commit -m "chore: bump Python minimum version to 3.11 for tomllib"
```

---

### Task 2: Add PersonaConfig to models.py

**Files:**
- Modify: `models.py` (append new dataclass)

**Step 1: Add PersonaConfig at the end of models.py**

The file currently ends at line 29. Append after the existing `Conversation` dataclass:

```python
@dataclass
class PersonaConfig:
    user_name: str = 'User'
    assistant_name: str = 'Assistant'
```

**Step 2: Verify no import errors**

```bash
python -c "from models import PersonaConfig; print(PersonaConfig())"
```
Expected: `PersonaConfig(user_name='User', assistant_name='Assistant')`

**Step 3: Run existing tests to confirm nothing broke**

```bash
pytest tests/ -v
```
Expected: all existing tests pass (27 tests).

**Step 4: Commit**

```bash
git add models.py
git commit -m "feat: add PersonaConfig dataclass to models"
```

---

### Task 3: Write failing tests for config.py

**Files:**
- Create: `tests/test_config.py`

**Step 1: Create tests/test_config.py**

```python
import tomllib
from pathlib import Path
import pytest
import config
from models import PersonaConfig


def _write_toml(path: Path, content: str) -> None:
    path.write_text(content, encoding='utf-8')


def test_load_persona_no_config_file(monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'nonexistent.toml')
    persona = config.load_persona()
    assert persona.user_name == 'User'
    assert persona.assistant_name == 'ChatGPT'  # provider default for 'chatgpt'


def test_load_persona_reads_user_name(monkeypatch, tmp_path):
    cfg = tmp_path / 'keromdizer.toml'
    _write_toml(cfg, '[user]\nname = "Matt"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
    persona = config.load_persona()
    assert persona.user_name == 'Matt'


def test_load_persona_reads_chatgpt_assistant_name(monkeypatch, tmp_path):
    cfg = tmp_path / 'keromdizer.toml'
    _write_toml(cfg, '[providers.chatgpt]\nassistant_name = "GPT"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
    persona = config.load_persona(provider='chatgpt')
    assert persona.assistant_name == 'GPT'


def test_load_persona_reads_deepseek_assistant_name(monkeypatch, tmp_path):
    cfg = tmp_path / 'keromdizer.toml'
    _write_toml(cfg, '[providers.deepseek]\nassistant_name = "DS"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
    persona = config.load_persona(provider='deepseek')
    assert persona.assistant_name == 'DS'


def test_load_persona_cli_user_name_overrides_file(monkeypatch, tmp_path):
    cfg = tmp_path / 'keromdizer.toml'
    _write_toml(cfg, '[user]\nname = "Matt"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
    persona = config.load_persona(user_name='Alice')
    assert persona.user_name == 'Alice'


def test_load_persona_cli_assistant_name_overrides_file(monkeypatch, tmp_path):
    cfg = tmp_path / 'keromdizer.toml'
    _write_toml(cfg, '[providers.chatgpt]\nassistant_name = "GPT"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
    persona = config.load_persona(assistant_name='MyBot')
    assert persona.assistant_name == 'MyBot'


def test_load_persona_missing_provider_uses_provider_default(monkeypatch, tmp_path):
    cfg = tmp_path / 'keromdizer.toml'
    _write_toml(cfg, '[user]\nname = "Matt"\n')  # no [providers.chatgpt]
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
    persona = config.load_persona(provider='chatgpt')
    assert persona.assistant_name == 'ChatGPT'


def test_load_persona_deepseek_provider_default(monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'nonexistent.toml')
    persona = config.load_persona(provider='deepseek')
    assert persona.assistant_name == 'DeepSeek'


def test_load_persona_unknown_provider_falls_back_to_assistant(monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'nonexistent.toml')
    persona = config.load_persona(provider='unknown_provider')
    assert persona.assistant_name == 'Assistant'


def test_load_persona_returns_persona_config_instance(monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'nonexistent.toml')
    persona = config.load_persona()
    assert isinstance(persona, PersonaConfig)
```

**Step 2: Run tests to confirm they all fail**

```bash
pytest tests/test_config.py -v
```
Expected: all 10 tests FAIL with `ModuleNotFoundError: No module named 'config'`

---

### Task 4: Implement config.py

**Files:**
- Create: `config.py`

**Step 1: Create config.py**

```python
import tomllib
from pathlib import Path

from models import PersonaConfig

CONFIG_PATH = Path.home() / '.keromdizer.toml'

PROVIDER_DEFAULTS: dict[str, str] = {
    'chatgpt': 'ChatGPT',
    'deepseek': 'DeepSeek',
}


def load_persona(
    provider: str = 'chatgpt',
    user_name: str | None = None,
    assistant_name: str | None = None,
) -> PersonaConfig:
    """Load persona config from ~/.keromdizer.toml with CLI override support.

    Fallback chain (highest to lowest priority):
      1. CLI args (user_name / assistant_name params)
      2. ~/.keromdizer.toml [user].name / [providers.<provider>].assistant_name
      3. Provider default from PROVIDER_DEFAULTS
      4. 'User' / 'Assistant' (absolute fallback)
    """
    data: dict = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'rb') as f:
            data = tomllib.load(f)

    resolved_user = (
        user_name
        or data.get('user', {}).get('name')
        or 'User'
    )
    resolved_assistant = (
        assistant_name
        or data.get('providers', {}).get(provider, {}).get('assistant_name')
        or PROVIDER_DEFAULTS.get(provider, 'Assistant')
    )
    return PersonaConfig(user_name=resolved_user, assistant_name=resolved_assistant)
```

**Step 2: Run tests to confirm they all pass**

```bash
pytest tests/test_config.py -v
```
Expected: all 10 tests PASS.

**Step 3: Run full test suite to confirm no regressions**

```bash
pytest tests/ -v
```
Expected: all tests pass (now 37 total).

**Step 4: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: add config.py with load_persona() and TOML support"
```

---

### Task 5: Write failing renderer persona tests

**Files:**
- Modify: `tests/test_renderer.py` (append new tests)

**Step 1: Append persona tests to tests/test_renderer.py**

Add at the end of the file:

```python
def test_render_default_persona_user_label():
    msg = Message(role='user', text='hi')
    conv = _make_conv([_make_branch([msg])])
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '### 👤 User' in md


def test_render_default_persona_assistant_label():
    msg = Message(role='assistant', text='hello')
    conv = _make_conv([_make_branch([msg])])
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '### 🤖 Assistant' in md


def test_render_custom_user_name():
    from models import PersonaConfig
    msg = Message(role='user', text='hi')
    conv = _make_conv([_make_branch([msg])])
    r = MarkdownRenderer(persona=PersonaConfig(user_name='Matt', assistant_name='Assistant'))
    md = r.render(conv, conv.branches[0])
    assert '### 👤 Matt' in md
    assert '### 👤 User' not in md


def test_render_custom_assistant_name():
    from models import PersonaConfig
    msg = Message(role='assistant', text='hello')
    conv = _make_conv([_make_branch([msg])])
    r = MarkdownRenderer(persona=PersonaConfig(user_name='User', assistant_name='ChatGPT'))
    md = r.render(conv, conv.branches[0])
    assert '### 🤖 ChatGPT' in md
    assert '### 🤖 Assistant' not in md


def test_render_none_persona_uses_defaults():
    from models import PersonaConfig
    msg = Message(role='user', text='hi')
    conv = _make_conv([_make_branch([msg])])
    r = MarkdownRenderer(persona=None)
    md = r.render(conv, conv.branches[0])
    assert '### 👤 User' in md
```

**Step 2: Run new tests to confirm they fail**

```bash
pytest tests/test_renderer.py::test_render_custom_user_name tests/test_renderer.py::test_render_custom_assistant_name tests/test_renderer.py::test_render_none_persona_uses_defaults -v
```
Expected: FAIL with `TypeError: MarkdownRenderer.__init__() got an unexpected keyword argument 'persona'`

---

### Task 6: Update MarkdownRenderer to accept PersonaConfig

**Files:**
- Modify: `renderer.py`

The current `renderer.py` is 47 lines. Key changes:
- Add `PersonaConfig` to imports (line 2)
- Add `__init__` accepting optional `PersonaConfig` (after class declaration, line 5)
- Replace hardcoded header string (line 35)

**Step 1: Edit renderer.py**

Update the import on line 2:
```python
from models import Conversation, Branch, PersonaConfig
```

Replace the class body — add `__init__` before `render`:
```python
class MarkdownRenderer:
    def __init__(self, persona: PersonaConfig | None = None):
        self.persona = persona or PersonaConfig()

    def render(self, conversation: Conversation, branch: Branch) -> str:
```

Replace line 35 (the header assignment):
```python
            header = f'### 👤 {self.persona.user_name}' if msg.role == 'user' else f'### 🤖 {self.persona.assistant_name}'
```

**Step 2: Run renderer tests**

```bash
pytest tests/test_renderer.py -v
```
Expected: all renderer tests PASS (existing 13 + 5 new = 18 total).

Note: `test_render_user_message` asserts `'### 👤 User' in md` and `test_render_assistant_message` asserts `'### 🤖 Assistant' in md` — these must still pass because `MarkdownRenderer()` with no args uses `PersonaConfig()` defaults (`'User'`, `'Assistant'`).

**Step 3: Run full test suite**

```bash
pytest tests/ -v
```
Expected: all tests pass (42 total).

**Step 4: Commit**

```bash
git add renderer.py tests/test_renderer.py
git commit -m "feat: MarkdownRenderer accepts PersonaConfig for custom speaker labels"
```

---

### Task 7: Wire persona config into keromdizer.py CLI

**Files:**
- Modify: `keromdizer.py`

**Step 1: Add imports at top of keromdizer.py**

Current imports (lines 1-7):
```python
import argparse
import sys
from pathlib import Path

from conversation_parser import ConversationParser
from renderer import MarkdownRenderer
from file_manager import FileManager
```

Add `load_persona` import:
```python
import argparse
import sys
from pathlib import Path

from config import load_persona
from conversation_parser import ConversationParser
from renderer import MarkdownRenderer
from file_manager import FileManager
```

**Step 2: Add CLI flags inside main(), after the existing --dry-run argument (line 29)**

```python
    arg_parser.add_argument(
        '--user-name',
        default=None,
        help='Override user label in output (default: from ~/.keromdizer.toml or "User")',
    )
    arg_parser.add_argument(
        '--assistant-name',
        default=None,
        help='Override assistant label in output (default: from ~/.keromdizer.toml or provider name)',
    )
```

**Step 3: Build PersonaConfig and pass to renderer (after args = arg_parser.parse_args(), before renderer = MarkdownRenderer())**

Replace line 43 (`renderer = MarkdownRenderer()`) with:
```python
    persona = load_persona(
        provider='chatgpt',
        user_name=args.user_name,
        assistant_name=args.assistant_name,
    )
    renderer = MarkdownRenderer(persona)
```

**Step 4: Smoke test with --help**

```bash
python keromdizer.py --help
```
Expected output includes:
```
  --user-name USER_NAME
  --assistant-name ASSISTANT_NAME
```

**Step 5: Smoke test dry run with override flags**

```bash
python keromdizer.py /home/matt/Downloads/27acb0dfd0a3c5fc91e10df3ec41412e00ff7879d440e4504e23ce0810ffbfff-2026-01-14-04-16-34-d9369f62a9184a8b86ce547d614186fb/ --dry-run --user-name Matt --assistant-name ChatGPT 2>/dev/null | head -5
```
Expected: dry run output (no errors).

**Step 6: Run full test suite one final time**

```bash
pytest tests/ -v
```
Expected: all 42 tests pass.

**Step 7: Commit**

```bash
git add keromdizer.py
git commit -m "feat: add --user-name and --assistant-name CLI flags with TOML config support"
```
