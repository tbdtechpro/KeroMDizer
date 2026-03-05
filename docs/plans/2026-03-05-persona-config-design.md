# Persona Config Design

**Date:** 2026-03-05
**Branch:** feat/persona-config (to be created)
**Status:** Approved

## Summary

Allow users to configure custom display names for the "user" and "assistant" speaker labels in rendered markdown output. Names are set via `~/.keromdizer.toml` (persistent defaults) and can be overridden per-run via CLI flags. Provider-aware: each supported AI provider (chatgpt, deepseek, ...) has its own assistant name entry. Designed to be exposed in the TUI once that layer is added.

## Config File Schema

Location: `~/.keromdizer.toml` (user-global, optional)

```toml
[user]
name = "Matt"

[providers.chatgpt]
assistant_name = "ChatGPT"

[providers.deepseek]
assistant_name = "DeepSeek"
```

Both sections are optional. Tool works with no config file present.

## Data Model

Add `PersonaConfig` to `models.py`:

```python
@dataclass
class PersonaConfig:
    user_name: str = 'User'
    assistant_name: str = 'Assistant'
```

## New Module: `config.py`

Handles TOML loading and persona resolution. Uses `tomllib` (Python 3.11+ stdlib).

```python
import tomllib
from pathlib import Path
from models import PersonaConfig

CONFIG_PATH = Path.home() / '.keromdizer.toml'

PROVIDER_DEFAULTS = {
    'chatgpt': 'ChatGPT',
    'deepseek': 'DeepSeek',
}

def load_persona(provider: str = 'chatgpt', user_name: str | None = None, assistant_name: str | None = None) -> PersonaConfig:
    ...
```

### Fallback chain

| Priority | User name | Assistant name |
|---|---|---|
| 1 (highest) | CLI `--user-name` | CLI `--assistant-name` |
| 2 | `[user].name` in TOML | `[providers.<provider>].assistant_name` in TOML |
| 3 | `"User"` | Provider default (`"ChatGPT"`, `"DeepSeek"`, ...) |
| 4 (lowest) | — | `"Assistant"` (unknown provider) |

## Renderer Changes

`MarkdownRenderer.__init__` accepts optional `PersonaConfig`:

```python
class MarkdownRenderer:
    def __init__(self, persona: PersonaConfig | None = None):
        self.persona = persona or PersonaConfig()
```

Header line in `render()` becomes:

```python
header = f'### 👤 {self.persona.user_name}' if msg.role == 'user' else f'### 🤖 {self.persona.assistant_name}'
```

Emojis (👤, 🤖) remain fixed — decorative, not part of the configurable persona name.

## CLI Changes

Two new optional flags in `keromdizer.py`:

```
--user-name       Override user label (default: from ~/.keromdizer.toml or "User")
--assistant-name  Override assistant label (default: from ~/.keromdizer.toml or provider name)
```

Provider is hardcoded to `'chatgpt'` for the current CLI. When DeepSeek support lands, the parser signals its provider and it's passed to `load_persona()`.

## Python Version

Bump minimum from 3.10 to 3.11 (required for `tomllib` in stdlib). Ubuntu 24.04 ships 3.12 — no practical impact for current users. Update `bootstrap.sh` and `CLAUDE.md`.

## Testing

**Extend `test_renderer.py`:**
- Default `PersonaConfig` renders `### 👤 User` / `### 🤖 Assistant`
- Custom persona renders correctly
- `None` persona falls back to defaults

**New `tests/test_config.py`:**
- No config file → defaults returned
- Config file with `[user]` and `[providers.chatgpt]` → values read correctly
- CLI overrides win over file values
- Missing provider section → falls back to provider default
- Unknown provider → falls back to `"Assistant"`
- Tests monkeypatch `config.CONFIG_PATH` to a `tmp_path` file

## Future / Out of Scope

- `save_config()` for TUI write-back (deferred to TUI feature)
- Configurable emojis (YAGNI)
- Per-conversation persona overrides (YAGNI)
