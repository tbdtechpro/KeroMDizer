# ChatGPT Project Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch ChatGPT project associations via the ChatGPT backend API and populate the existing `branches.project` DB column, with a dedicated TUI screen and configurable conflict resolution.

**Architecture:** Two new standalone modules (`retrieve_token.py` for Bearer token retrieval, `project_fetcher.py` for API calls) feed into a new DB method (`bulk_update_projects`) and a new TUI screen (`PROJECTS`). Config is extended with `SyncConfig` (conflict mode) and `load_chatgpt_projects` (gizmo ID map from TOML).

**Tech Stack:** Python stdlib + `requests` (API calls) + `browser_cookie3` (optional auto-extract) + existing `bubblepy`/`pygloss` TUI stack + SQLite via existing `DatabaseManager`

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `project_fetcher.py` | `load_token()`, `fetch_project_map()` — pure network functions |
| Create | `retrieve_token.py` | CLI script: browser auto-extract + paste/stdin → `~/.keromdizer_token.json` |
| Create | `docs/chatgpt-projects-guide.md` | User guide for finding gizmo IDs |
| Create | `tests/test_sync_config.py` | Tests for new config functions |
| Create | `tests/test_project_fetcher.py` | Tests for fetcher (mocked HTTP) |
| Create | `tests/test_retrieve_token.py` | Tests for parse/save helpers |
| Modify | `models.py` | Add `SyncConfig` dataclass |
| Modify | `config.py` | Add `_serialize_toml`, `load_chatgpt_projects`, `load_sync_config`, `save_sync_config` |
| Modify | `db.py` | Add `bulk_update_projects` method |
| Modify | `tui.py` | SETTINGS: add `project_conflict` field; add PROJECTS screen |
| Modify | `requirements-dev.txt` | Add `requests`, `browser_cookie3` |

---

## Task 1: SyncConfig dataclass

**Files:**
- Modify: `models.py`

- [ ] **Step 1: Add SyncConfig to models.py**

  Open `models.py` and append after the `ExportConfig` dataclass (end of file):

  ```python
  @dataclass
  class SyncConfig:
      project_conflict: str = 'preserve'  # 'preserve' | 'overwrite' | 'flag'
  ```

- [ ] **Step 2: Verify import works**

  ```bash
  python -c "from models import SyncConfig; print(SyncConfig())"
  ```

  Expected: `SyncConfig(project_conflict='preserve')`

- [ ] **Step 3: Commit**

  ```bash
  git add models.py
  git commit -m "feat: add SyncConfig dataclass"
  ```

---

## Task 2: Config functions — load_chatgpt_projects, load_sync_config, save_sync_config

**Files:**
- Modify: `config.py`
- Create: `tests/test_sync_config.py`

- [ ] **Step 1: Write failing tests**

  Create `tests/test_sync_config.py`:

  ```python
  import pytest
  from pathlib import Path
  import config
  from models import SyncConfig


  def _write_toml(path: Path, content: str) -> None:
      path.write_text(content, encoding='utf-8')


  # --- load_chatgpt_projects ---

  def test_load_chatgpt_projects_empty_when_no_file(monkeypatch, tmp_path):
      monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'nonexistent.toml')
      assert config.load_chatgpt_projects() == {}


  def test_load_chatgpt_projects_empty_when_section_absent(monkeypatch, tmp_path):
      cfg = tmp_path / 'k.toml'
      _write_toml(cfg, '[user]\nname = "Matt"\n')
      monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
      assert config.load_chatgpt_projects() == {}


  def test_load_chatgpt_projects_reads_gizmo_map(monkeypatch, tmp_path):
      cfg = tmp_path / 'k.toml'
      _write_toml(cfg, '[chatgpt.projects]\ng-p-aaa = "Project A"\ng-p-bbb = "Project B"\n')
      monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
      result = config.load_chatgpt_projects()
      assert result == {'g-p-aaa': 'Project A', 'g-p-bbb': 'Project B'}


  # --- load_sync_config ---

  def test_load_sync_config_defaults_to_preserve(monkeypatch, tmp_path):
      monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'nonexistent.toml')
      cfg = config.load_sync_config()
      assert cfg.project_conflict == 'preserve'


  def test_load_sync_config_reads_value(monkeypatch, tmp_path):
      cfg = tmp_path / 'k.toml'
      _write_toml(cfg, '[sync]\nproject_conflict = "overwrite"\n')
      monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
      result = config.load_sync_config()
      assert result.project_conflict == 'overwrite'


  def test_load_sync_config_unknown_value_falls_back_to_preserve(monkeypatch, tmp_path):
      cfg = tmp_path / 'k.toml'
      _write_toml(cfg, '[sync]\nproject_conflict = "bogus"\n')
      monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
      result = config.load_sync_config()
      assert result.project_conflict == 'preserve'


  # --- save_sync_config ---

  def test_save_sync_config_writes_sync_section(monkeypatch, tmp_path):
      cfg_path = tmp_path / 'k.toml'
      monkeypatch.setattr(config, 'CONFIG_PATH', cfg_path)
      config.save_sync_config(SyncConfig(project_conflict='flag'))
      result = config.load_sync_config()
      assert result.project_conflict == 'flag'


  def test_save_sync_config_preserves_other_sections(monkeypatch, tmp_path):
      cfg_path = tmp_path / 'k.toml'
      _write_toml(cfg_path, '[user]\nname = "Matt"\n')
      monkeypatch.setattr(config, 'CONFIG_PATH', cfg_path)
      config.save_sync_config(SyncConfig(project_conflict='overwrite'))
      persona = config.load_persona()
      assert persona.user_name == 'Matt'


  def test_save_sync_config_preserves_chatgpt_projects(monkeypatch, tmp_path):
      cfg_path = tmp_path / 'k.toml'
      _write_toml(cfg_path, '[chatgpt.projects]\ng-p-aaa = "Project A"\n')
      monkeypatch.setattr(config, 'CONFIG_PATH', cfg_path)
      config.save_sync_config(SyncConfig(project_conflict='overwrite'))
      projects = config.load_chatgpt_projects()
      assert projects == {'g-p-aaa': 'Project A'}
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  pytest tests/test_sync_config.py -v
  ```

  Expected: all FAIL with `AttributeError: module 'config' has no attribute 'load_chatgpt_projects'`

- [ ] **Step 3: Add _serialize_toml, load_chatgpt_projects, load_sync_config, save_sync_config to config.py**

  Add the following after `load_export_config` (end of `config.py`):

  ```python
  _VALID_CONFLICT_MODES = ('preserve', 'overwrite', 'flag')


  def load_chatgpt_projects() -> dict[str, str]:
      """Read [chatgpt.projects] from ~/.keromdizer.toml.

      Returns {gizmo_id: project_name}. Empty dict if section absent.
      """
      try:
          data = _load_toml()
      except ValueError:
          return {}
      return dict(data.get('chatgpt', {}).get('projects', {}))


  def load_sync_config() -> SyncConfig:
      """Read [sync] section from ~/.keromdizer.toml. Defaults: project_conflict='preserve'."""
      try:
          data = _load_toml()
      except ValueError:
          return SyncConfig()
      raw = data.get('sync', {}).get('project_conflict', 'preserve')
      if raw not in _VALID_CONFLICT_MODES:
          raw = 'preserve'
      return SyncConfig(project_conflict=raw)


  def _serialize_toml(data: dict, prefix: str = '') -> list[str]:
      """Minimal recursive TOML serializer for string-valued nested dicts."""
      lines: list[str] = []
      flat = {k: v for k, v in data.items() if not isinstance(v, dict)}
      nested = {k: v for k, v in data.items() if isinstance(v, dict)}
      if flat:
          if prefix:
              lines.append(f'[{prefix}]')
          for k, v in flat.items():
              lines.append(f'{k} = "{v}"')
      for k, v in nested.items():
          sub = f'{prefix}.{k}' if prefix else k
          lines.extend(_serialize_toml(v, sub))
      return lines


  def save_sync_config(cfg: SyncConfig) -> None:
      """Write [sync] section to ~/.keromdizer.toml, preserving all other sections."""
      try:
          data = _load_toml()
      except ValueError:
          data = {}
      data.setdefault('sync', {})['project_conflict'] = cfg.project_conflict
      CONFIG_PATH.write_text('\n'.join(_serialize_toml(data)) + '\n', encoding='utf-8')
  ```

  Also update the import at the top of `config.py` to include `SyncConfig`:

  ```python
  from models import PersonaConfig, BranchConfig, ExportConfig, SyncConfig
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  pytest tests/test_sync_config.py -v
  ```

  Expected: all PASS

- [ ] **Step 5: Run full suite to check for regressions**

  ```bash
  pytest tests/ -v
  ```

  Expected: all PASS (existing 183 tests + new sync config tests)

- [ ] **Step 6: Commit**

  ```bash
  git add config.py models.py tests/test_sync_config.py
  git commit -m "feat: add SyncConfig dataclass and config functions for project sync"
  ```

---

## Task 3: DB — bulk_update_projects

**Files:**
- Modify: `db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write failing tests**

  Append to `tests/test_db.py` (after existing tests):

  ```python
  # ── bulk_update_projects ──────────────────────────────────────────────────────

  def _seed_conv(db, conv_id: str, project: str | None = None, branch_count: int = 1):
      """Insert a minimal conversation with one branch into db."""
      branches = []
      for i in range(1, branch_count + 1):
          branches.append({
              'branch_id': f'{conv_id}__branch_{i}',
              'branch_index': i,
              'is_main_branch': i == 1,
              'messages': [],
              'inferred_tags': [],
              'inferred_syntax': [],
          })
      db.upsert_conversation(
          conversation_id=conv_id,
          provider='chatgpt',
          title=f'Conv {conv_id}',
          create_time='2026-01-01T00:00:00+00:00',
          update_time='2026-01-01T00:00:00+00:00',
          model_slug='gpt-4o',
          branch_count=branch_count,
          branches=branches,
      )
      if project is not None:
          for b in branches:
              db.update_branch_tags(b['branch_id'], [], project, None, [])


  def test_bulk_update_preserve_fills_null(db):
      _seed_conv(db, 'conv-a')
      applied, conflicts = db.bulk_update_projects({'conv-a': 'Tools'}, 'preserve')
      assert applied == 1
      assert conflicts == 0
      row = db.get_branch('conv-a__branch_1')
      assert row['project'] == 'Tools'


  def test_bulk_update_preserve_skips_existing(db):
      _seed_conv(db, 'conv-b', project='Manual')
      applied, conflicts = db.bulk_update_projects({'conv-b': 'Tools'}, 'preserve')
      assert applied == 0
      assert conflicts == 0
      row = db.get_branch('conv-b__branch_1')
      assert row['project'] == 'Manual'


  def test_bulk_update_overwrite_replaces_existing(db):
      _seed_conv(db, 'conv-c', project='Manual')
      applied, conflicts = db.bulk_update_projects({'conv-c': 'Tools'}, 'overwrite')
      assert applied == 1
      assert conflicts == 1
      row = db.get_branch('conv-c__branch_1')
      assert row['project'] == 'Tools'


  def test_bulk_update_overwrite_fills_null(db):
      _seed_conv(db, 'conv-d')
      applied, conflicts = db.bulk_update_projects({'conv-d': 'Scripts'}, 'overwrite')
      assert applied == 1
      assert conflicts == 0


  def test_bulk_update_flag_same_result_as_overwrite(db):
      _seed_conv(db, 'conv-e', project='Manual')
      applied, conflicts = db.bulk_update_projects({'conv-e': 'Tools'}, 'flag')
      assert applied == 1
      assert conflicts == 1
      row = db.get_branch('conv-e__branch_1')
      assert row['project'] == 'Tools'


  def test_bulk_update_applies_to_all_branches(db):
      _seed_conv(db, 'conv-f', branch_count=3)
      applied, conflicts = db.bulk_update_projects({'conv-f': 'Day Job'}, 'preserve')
      assert applied == 3
      for i in range(1, 4):
          row = db.get_branch(f'conv-f__branch_{i}')
          assert row['project'] == 'Day Job'


  def test_bulk_update_ignores_unknown_conversation(db):
      applied, conflicts = db.bulk_update_projects({'conv-zzz': 'Random'}, 'preserve')
      assert applied == 0
      assert conflicts == 0


  def test_bulk_update_empty_mapping(db):
      applied, conflicts = db.bulk_update_projects({}, 'preserve')
      assert applied == 0
      assert conflicts == 0
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  pytest tests/test_db.py -k "bulk_update" -v
  ```

  Expected: all FAIL with `AttributeError: 'DatabaseManager' object has no attribute 'bulk_update_projects'`

- [ ] **Step 3: Add bulk_update_projects to db.py**

  Add after `update_branch_tags` and before `get_all_tags`:

  ```python
  def bulk_update_projects(
      self,
      mapping: dict[str, str],
      conflict_mode: str = 'preserve',
  ) -> tuple[int, int]:
      """Set project names on branches from a {conversation_id: project_name} mapping.

      conflict_mode:
        'preserve'  — only update rows where project IS NULL or ''
        'overwrite' — always update; conflicts = count of rows that had a value
        'flag'      — same as overwrite; conflicts count is surfaced in TUI

      Returns (applied, conflicts).
      """
      if not mapping:
          return 0, 0

      applied = 0
      conflicts = 0

      for conv_id, project_name in mapping.items():
          rows = self._conn.execute(
              'SELECT branch_id, project FROM branches WHERE conversation_id = ?',
              (conv_id,),
          ).fetchall()

          for row in rows:
              existing = row['project'] or ''
              if conflict_mode == 'preserve' and existing:
                  continue
              if existing and conflict_mode in ('overwrite', 'flag'):
                  conflicts += 1
              self._conn.execute(
                  'UPDATE branches SET project = ? WHERE branch_id = ?',
                  (project_name, row['branch_id']),
              )
              applied += 1

      if applied:
          self._conn.commit()

      return applied, conflicts
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  pytest tests/test_db.py -v
  ```

  Expected: all PASS

- [ ] **Step 5: Commit**

  ```bash
  git add db.py tests/test_db.py
  git commit -m "feat: add bulk_update_projects to DatabaseManager"
  ```

---

## Task 4: project_fetcher.py

**Files:**
- Create: `project_fetcher.py`
- Create: `tests/test_project_fetcher.py`
- Modify: `requirements-dev.txt`

- [ ] **Step 1: Add requests to requirements-dev.txt**

  Append `requests` to `requirements-dev.txt`:

  ```
  pytest
  git+https://github.com/tbdtechpro/bubblepy.git
  git+https://github.com/tbdtechpro/pygloss.git
  yake
  pygments
  python-docx
  requests
  browser_cookie3
  ```

  Install:

  ```bash
  .venv/bin/pip install requests browser_cookie3
  ```

- [ ] **Step 2: Write failing tests**

  Create `tests/test_project_fetcher.py`:

  ```python
  import json
  import pytest
  from pathlib import Path
  from unittest.mock import patch, MagicMock
  import project_fetcher


  # ── load_token ────────────────────────────────────────────────────────────────

  def test_load_token_returns_none_when_file_missing(tmp_path):
      assert project_fetcher.load_token(tmp_path / 'no.json') is None


  def test_load_token_returns_access_token(tmp_path):
      f = tmp_path / 'token.json'
      f.write_text(json.dumps({'access_token': 'eyJtest', 'fetched_at': '2026-03-30'}))
      assert project_fetcher.load_token(f) == 'eyJtest'


  def test_load_token_returns_none_when_field_missing(tmp_path):
      f = tmp_path / 'token.json'
      f.write_text(json.dumps({'other': 'value'}))
      assert project_fetcher.load_token(f) is None


  # ── fetch_project_map ─────────────────────────────────────────────────────────

  def _mock_response(items: list[dict], next_cursor=None) -> MagicMock:
      """Build a mock requests.Response returning the given conversation items."""
      resp = MagicMock()
      resp.raise_for_status = MagicMock()
      resp.json.return_value = {
          'items': items,
          'cursor': next_cursor,
      }
      return resp


  def test_fetch_project_map_single_page(monkeypatch):
      responses = [
          _mock_response([
              {'conversation_id': 'conv-1'},
              {'conversation_id': 'conv-2'},
          ]),
      ]
      mock_get = MagicMock(side_effect=responses)
      monkeypatch.setattr(project_fetcher.requests, 'get', mock_get)

      result = project_fetcher.fetch_project_map(
          token='tok',
          projects={'g-p-aaa': 'Tools'},
      )
      assert result == {'conv-1': 'Tools', 'conv-2': 'Tools'}


  def test_fetch_project_map_pagination(monkeypatch):
      responses = [
          _mock_response([{'conversation_id': 'conv-1'}], next_cursor='abc'),
          _mock_response([{'conversation_id': 'conv-2'}], next_cursor=None),
      ]
      mock_get = MagicMock(side_effect=responses)
      monkeypatch.setattr(project_fetcher.requests, 'get', mock_get)

      result = project_fetcher.fetch_project_map(
          token='tok',
          projects={'g-p-aaa': 'Tools'},
      )
      assert result == {'conv-1': 'Tools', 'conv-2': 'Tools'}
      assert mock_get.call_count == 2
      # Second call should pass cursor=abc
      _, kwargs = mock_get.call_args_list[1]
      assert kwargs['params']['cursor'] == 'abc'


  def test_fetch_project_map_multiple_projects(monkeypatch):
      call_count = [0]
      def mock_get(url, **kwargs):
          call_count[0] += 1
          if 'g-p-aaa' in url:
              return _mock_response([{'conversation_id': 'conv-a'}])
          else:
              return _mock_response([{'conversation_id': 'conv-b'}])
      monkeypatch.setattr(project_fetcher.requests, 'get', mock_get)

      result = project_fetcher.fetch_project_map(
          token='tok',
          projects={'g-p-aaa': 'Tools', 'g-p-bbb': 'Scripts'},
      )
      assert result['conv-a'] == 'Tools'
      assert result['conv-b'] == 'Scripts'


  def test_fetch_project_map_empty_projects():
      result = project_fetcher.fetch_project_map(token='tok', projects={})
      assert result == {}


  def test_fetch_project_map_calls_progress_cb(monkeypatch):
      monkeypatch.setattr(
          project_fetcher.requests, 'get',
          MagicMock(return_value=_mock_response([
              {'conversation_id': 'conv-1'},
              {'conversation_id': 'conv-2'},
          ])),
      )
      calls = []
      project_fetcher.fetch_project_map(
          token='tok',
          projects={'g-p-aaa': 'Tools'},
          progress_cb=lambda name, count: calls.append((name, count)),
      )
      assert calls == [('Tools', 2)]


  def test_fetch_project_map_stops_on_empty_items(monkeypatch):
      """Empty items list should stop pagination even if cursor present."""
      responses = [
          _mock_response([], next_cursor='orphan-cursor'),
      ]
      monkeypatch.setattr(project_fetcher.requests, 'get', MagicMock(side_effect=responses))
      result = project_fetcher.fetch_project_map(token='tok', projects={'g-p-aaa': 'Tools'})
      assert result == {}
  ```

- [ ] **Step 3: Run tests to verify they fail**

  ```bash
  pytest tests/test_project_fetcher.py -v
  ```

  Expected: all FAIL with `ModuleNotFoundError: No module named 'project_fetcher'`

- [ ] **Step 4: Create project_fetcher.py**

  Create `project_fetcher.py`:

  ```python
  """
  project_fetcher.py — fetch conversation→project mapping from ChatGPT backend API.

  Reads Bearer token from ~/.keromdizer_token.json and iterates gizmo IDs from
  ~/.keromdizer.toml [chatgpt.projects] to build a {conversation_id: project_name} map.
  """

  from __future__ import annotations

  import json
  from collections.abc import Callable
  from pathlib import Path

  import requests

  TOKEN_FILE = Path.home() / '.keromdizer_token.json'

  _BASE = 'https://chatgpt.com/backend-api'


  def load_token(token_file: Path = TOKEN_FILE) -> str | None:
      """Read access_token from token JSON file. Returns None if missing or malformed."""
      try:
          data = json.loads(token_file.read_text(encoding='utf-8'))
          return data.get('access_token') or None
      except (OSError, json.JSONDecodeError, ValueError):
          return None


  def fetch_project_map(
      token: str,
      projects: dict[str, str],
      progress_cb: Callable[[str, int], None] | None = None,
  ) -> dict[str, str]:
      """Fetch all conversations for each gizmo and return {conversation_id: project_name}.

      Args:
          token:       ChatGPT Bearer access token.
          projects:    {gizmo_id: project_name} from ~/.keromdizer.toml.
          progress_cb: Optional callback called after each gizmo is fully fetched.
                       Receives (project_name, conversation_count).
      """
      if not projects:
          return {}

      headers = {'Authorization': f'Bearer {token}'}
      result: dict[str, str] = {}

      for gizmo_id, project_name in projects.items():
          conv_ids = _fetch_all_conversations(gizmo_id, headers)
          for conv_id in conv_ids:
              result[conv_id] = project_name
          if progress_cb is not None:
              progress_cb(project_name, len(conv_ids))

      return result


  def _fetch_all_conversations(gizmo_id: str, headers: dict) -> list[str]:
      """Fetch all conversation IDs for one gizmo, following cursor pagination."""
      url = f'{_BASE}/gizmos/{gizmo_id}/conversations'
      cursor: str | None = '0'
      conv_ids: list[str] = []

      while cursor is not None:
          resp = requests.get(url, headers=headers, params={'cursor': cursor}, timeout=30)
          resp.raise_for_status()
          data = resp.json()
          items = data.get('items') or []
          if not items:
              break
          for item in items:
              cid = item.get('conversation_id') or item.get('id')
              if cid:
                  conv_ids.append(cid)
          cursor = data.get('cursor') or None

      return conv_ids
  ```

- [ ] **Step 5: Run tests to verify they pass**

  ```bash
  pytest tests/test_project_fetcher.py -v
  ```

  Expected: all PASS

- [ ] **Step 6: Run full suite**

  ```bash
  pytest tests/ -v
  ```

  Expected: all PASS

- [ ] **Step 7: Commit**

  ```bash
  git add project_fetcher.py tests/test_project_fetcher.py requirements-dev.txt
  git commit -m "feat: add project_fetcher module and requests/browser_cookie3 dependencies"
  ```

---

## Task 5: retrieve_token.py

**Files:**
- Create: `retrieve_token.py`
- Create: `tests/test_retrieve_token.py`

- [ ] **Step 1: Write failing tests**

  Create `tests/test_retrieve_token.py`:

  ```python
  import json
  import pytest
  from pathlib import Path
  from unittest.mock import patch, MagicMock
  import retrieve_token


  # ── parse_token_string ────────────────────────────────────────────────────────

  def test_parse_token_string_bare_jwt():
      assert retrieve_token.parse_token_string('eyJtest123') == 'eyJtest123'


  def test_parse_token_string_strips_whitespace():
      assert retrieve_token.parse_token_string('  eyJtest  \n') == 'eyJtest'


  def test_parse_token_string_bearer_prefix():
      assert retrieve_token.parse_token_string('Bearer eyJtest') == 'eyJtest'


  def test_parse_token_string_json_access_token():
      raw = json.dumps({'accessToken': 'eyJfromjson'})
      assert retrieve_token.parse_token_string(raw) == 'eyJfromjson'


  def test_parse_token_string_json_access_token_snake():
      raw = json.dumps({'access_token': 'eyJsnake'})
      assert retrieve_token.parse_token_string(raw) == 'eyJsnake'


  def test_parse_token_string_empty_raises():
      with pytest.raises(ValueError, match='empty'):
          retrieve_token.parse_token_string('   ')


  def test_parse_token_string_json_missing_token_raises():
      with pytest.raises(ValueError, match='accessToken'):
          retrieve_token.parse_token_string(json.dumps({'other': 'value'}))


  # ── save_token ────────────────────────────────────────────────────────────────

  def test_save_token_writes_json(tmp_path):
      dest = tmp_path / 'token.json'
      retrieve_token.save_token('eyJtest', token_file=dest)
      data = json.loads(dest.read_text())
      assert data['access_token'] == 'eyJtest'
      assert 'fetched_at' in data


  def test_save_token_overwrites_existing(tmp_path):
      dest = tmp_path / 'token.json'
      dest.write_text(json.dumps({'access_token': 'old'}))
      retrieve_token.save_token('new_token', token_file=dest)
      data = json.loads(dest.read_text())
      assert data['access_token'] == 'new_token'
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  pytest tests/test_retrieve_token.py -v
  ```

  Expected: all FAIL with `ModuleNotFoundError: No module named 'retrieve_token'`

- [ ] **Step 3: Create retrieve_token.py**

  Create `retrieve_token.py`:

  ```python
  #!/usr/bin/env python3
  """
  retrieve_token.py — save ChatGPT Bearer token to ~/.keromdizer_token.json.

  Three modes:

    1. Auto-extract from browser (default — requires browser_cookie3):
         python retrieve_token.py

    2. Paste token directly:
         python retrieve_token.py --paste "eyJ..."

    3. Read from stdin (pipe-friendly):
         xclip -o | python retrieve_token.py --stdin

  How to get the token string (modes 2 / 3):
    - Open Chrome/Firefox DevTools (F12) → Console tab
    - Make sure you are logged in at chatgpt.com
    - Paste and run:
        (async () => {
          const s = await fetch('/api/auth/session').then(r => r.json());
          console.log(s.accessToken);
        })();
    - Copy the printed token and pass it to --paste or pipe to --stdin
  """

  from __future__ import annotations

  import argparse
  import json
  import sys
  from datetime import datetime, timezone
  from pathlib import Path

  from project_fetcher import TOKEN_FILE


  def parse_token_string(raw: str) -> str:
      """Extract a Bearer token from various input formats.

      Accepts:
        - Raw JWT string (eyJ...)
        - 'Bearer eyJ...' prefixed string
        - JSON object with 'accessToken' or 'access_token' key

      Raises ValueError on empty input or unrecognised JSON.
      """
      raw = raw.strip()
      if not raw:
          raise ValueError('Input is empty — no token found')

      # Strip Bearer prefix
      if raw.lower().startswith('bearer '):
          raw = raw[7:].strip()

      # Try JSON parse
      if raw.startswith('{'):
          try:
              data = json.loads(raw)
          except json.JSONDecodeError as e:
              raise ValueError(f'Invalid JSON: {e}') from e
          token = data.get('accessToken') or data.get('access_token')
          if not token:
              raise ValueError(
                  'JSON parsed but no accessToken or access_token field found'
              )
          return token

      return raw


  def save_token(token: str, token_file: Path = TOKEN_FILE) -> None:
      """Write token to JSON file with a fetched_at timestamp."""
      token_file.parent.mkdir(parents=True, exist_ok=True)
      token_file.write_text(
          json.dumps({
              'access_token': token,
              'fetched_at': datetime.now(tz=timezone.utc).isoformat(),
          }),
          encoding='utf-8',
      )


  def get_chatgpt_token_from_browser() -> str | None:
      """Try to extract ChatGPT Bearer token from the local browser profile.

      Uses browser_cookie3 to read the __Secure-next-auth.session-token cookie,
      then exchanges it for a Bearer token via /api/auth/session.
      Tries Firefox first (most reliable on Linux), then Chrome/Chromium.
      Returns the access token string, or None on failure.
      """
      try:
          import browser_cookie3
      except ImportError:
          print(
              '[!] browser_cookie3 is not installed.\n'
              '    Install it with: pip install browser_cookie3\n'
              '    Or use --paste / --stdin instead.',
              file=sys.stderr,
          )
          return None

      try:
          import requests
      except ImportError:
          print('[!] requests is not installed: pip install requests', file=sys.stderr)
          return None

      browsers = [
          ('Firefox',  getattr(browser_cookie3, 'firefox',  None)),
          ('Chrome',   getattr(browser_cookie3, 'chrome',   None)),
          ('Chromium', getattr(browser_cookie3, 'chromium', None)),
      ]

      session_cookie: str | None = None
      for browser_name, browser_fn in browsers:
          if browser_fn is None:
              continue
          try:
              cj = browser_fn(domain_name='.chatgpt.com')
              for c in cj:
                  if c.name == '__Secure-next-auth.session-token' and c.value:
                      session_cookie = c.value
                      print(f'[*] Found session cookie in {browser_name}')
                      break
          except Exception as exc:
              print(f'[!] {browser_name}: {exc}', file=sys.stderr)
          if session_cookie:
              break

      if not session_cookie:
          print(
              '[!] No ChatGPT session cookie found in any browser.\n'
              '    Make sure you are logged in at chatgpt.com,\n'
              '    or use --paste / --stdin.',
              file=sys.stderr,
          )
          return None

      try:
          resp = requests.get(
              'https://chatgpt.com/api/auth/session',
              cookies={'__Secure-next-auth.session-token': session_cookie},
              timeout=30,
          )
          resp.raise_for_status()
          token = resp.json().get('accessToken')
          if not token:
              print('[!] Session exchange succeeded but no accessToken in response.', file=sys.stderr)
              return None
          return token
      except Exception as exc:
          print(f'[!] Failed to exchange session cookie for token: {exc}', file=sys.stderr)
          return None


  def main() -> None:
      parser = argparse.ArgumentParser(
          description='Save ChatGPT Bearer token to ~/.keromdizer_token.json.',
          formatter_class=argparse.RawDescriptionHelpFormatter,
          epilog=(
              'Examples:\n'
              '  # Auto-extract from browser (recommended):\n'
              '  python retrieve_token.py\n\n'
              '  # Paste token from browser console JS snippet:\n'
              '  python retrieve_token.py --paste "eyJ..."\n\n'
              '  # Pipe from clipboard (Linux):\n'
              '  xclip -o | python retrieve_token.py --stdin\n'
          ),
      )
      group = parser.add_mutually_exclusive_group()
      group.add_argument(
          '--paste',
          metavar='TOKEN',
          help='Paste the Bearer token directly (or JSON from the console snippet).',
      )
      group.add_argument(
          '--stdin',
          action='store_true',
          help='Read token from stdin (pipe-friendly).',
      )
      args = parser.parse_args()

      if args.paste:
          try:
              token = parse_token_string(args.paste)
          except ValueError as e:
              print(f'[!] {e}', file=sys.stderr)
              sys.exit(1)
      elif args.stdin:
          raw = sys.stdin.read()
          try:
              token = parse_token_string(raw)
          except ValueError as e:
              print(f'[!] {e}', file=sys.stderr)
              sys.exit(1)
      else:
          print('[*] Attempting to extract token from your browser...')
          token = get_chatgpt_token_from_browser()
          if not token:
              sys.exit(1)

      save_token(token)
      print(f'[+] Token saved to {TOKEN_FILE}')
      print('    Note: ChatGPT tokens expire after ~20 minutes. Run the sync soon.')


  if __name__ == '__main__':
      main()
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  pytest tests/test_retrieve_token.py -v
  ```

  Expected: all PASS

- [ ] **Step 5: Run full suite**

  ```bash
  pytest tests/ -v
  ```

  Expected: all PASS

- [ ] **Step 6: Commit**

  ```bash
  git add retrieve_token.py tests/test_retrieve_token.py
  git commit -m "feat: add retrieve_token.py for ChatGPT Bearer token retrieval"
  ```

---

## Task 6: SETTINGS screen — add project_conflict field

**Files:**
- Modify: `tui.py`

- [ ] **Step 1: Add project_conflict to _load_settings**

  In `tui.py`, find `_load_settings()` and update the return dict to include the new field.

  Change:
  ```python
      return {
          'output_dir':        data.get('output', {}).get('dir', './output'),
          'user_name':         data.get('user', {}).get('name', ''),
          'chatgpt_assistant': providers.get('chatgpt', {}).get('assistant_name', ''),
          'deepseek_assistant': providers.get('deepseek', {}).get('assistant_name', ''),
          'import_branches':   branches.get('import', 'all'),
          'export_markdown':   branches.get('export_markdown', 'all'),
          'export_jsonl':      branches.get('export_jsonl', 'all'),
      }
  ```

  To:
  ```python
      raw_conflict = data.get('sync', {}).get('project_conflict', 'preserve')
      if raw_conflict not in ('preserve', 'overwrite', 'flag'):
          raw_conflict = 'preserve'
      return {
          'output_dir':         data.get('output', {}).get('dir', './output'),
          'user_name':          data.get('user', {}).get('name', ''),
          'chatgpt_assistant':  providers.get('chatgpt', {}).get('assistant_name', ''),
          'deepseek_assistant': providers.get('deepseek', {}).get('assistant_name', ''),
          'import_branches':    branches.get('import', 'all'),
          'export_markdown':    branches.get('export_markdown', 'all'),
          'export_jsonl':       branches.get('export_jsonl', 'all'),
          'project_conflict':   raw_conflict,
      }
  ```

- [ ] **Step 2: Add project_conflict to _save_settings**

  In `_save_settings`, after the `if branches_data:` block, add:

  ```python
      sync_conflict = values.get('project_conflict', 'preserve')
      if sync_conflict in ('preserve', 'overwrite', 'flag'):
          data.setdefault('sync', {})['project_conflict'] = sync_conflict
  ```

- [ ] **Step 3: Add project_conflict to AppModel.__init__ SETTINGS state**

  In `AppModel.__init__`, find the SETTINGS section. Change:

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

  To:

  ```python
          self.st_fields: list[str] = [
              'output_dir', 'user_name', 'chatgpt_assistant', 'deepseek_assistant',
              'import_branches', 'export_markdown', 'export_jsonl',
              'project_conflict',
          ]
          self.st_labels: dict[str, str] = {
              'output_dir':         'Output directory',
              'user_name':          'User name',
              'chatgpt_assistant':  'ChatGPT assistant name',
              'deepseek_assistant': 'DeepSeek assistant name',
              'import_branches':    'Import branches',
              'export_markdown':    'Markdown export branches',
              'export_jsonl':       'JSONL export branches',
              'project_conflict':   'Project sync conflict',
          }
          self.st_toggle_fields: set[str] = {'import_branches', 'export_markdown', 'export_jsonl'}
          self.st_cycle3_fields: set[str] = {'project_conflict'}  # 3-value cycle
  ```

- [ ] **Step 4: Update _key_settings toggle logic to handle 3-value cycle**

  In `_key_settings`, find the toggle handler:

  ```python
              if field_key in self.st_toggle_fields:
                  if key in ('enter', ' '):
                      current = self.st_values.get(field_key, 'all')
                      self.st_values[field_key] = 'main' if current == 'all' else 'all'
  ```

  Replace with:

  ```python
              if field_key in self.st_cycle3_fields:
                  if key in ('enter', ' '):
                      cycle = {'preserve': 'overwrite', 'overwrite': 'flag', 'flag': 'preserve'}
                      current = self.st_values.get(field_key, 'preserve')
                      self.st_values[field_key] = cycle.get(current, 'preserve')
              elif field_key in self.st_toggle_fields:
                  if key in ('enter', ' '):
                      current = self.st_values.get(field_key, 'all')
                      self.st_values[field_key] = 'main' if current == 'all' else 'all'
  ```

- [ ] **Step 5: Update _view_settings to render cycle3 fields like toggle fields**

  In `_view_settings`, find:

  ```python
              if fk in self.st_toggle_fields:
                  val_display = sel_style.render(f'[ {value} ]') if focused else muted_style.render(f'  {value}  ')
  ```

  Replace with:

  ```python
              if fk in self.st_toggle_fields or fk in self.st_cycle3_fields:
                  val_display = sel_style.render(f'[ {value} ]') if focused else muted_style.render(f'  {value}  ')
  ```

- [ ] **Step 6: Verify TUI starts without errors**

  ```bash
  python -c "from tui import AppModel; m = AppModel(); print('project_conflict' in m.st_fields)"
  ```

  Expected: `True`

- [ ] **Step 7: Commit**

  ```bash
  git add tui.py
  git commit -m "feat: add project_conflict field to SETTINGS screen"
  ```

---

## Task 7: TUI — PROJECTS screen

**Files:**
- Modify: `tui.py`

- [ ] **Step 1: Add Screen.PROJECTS to the Screen enum**

  Find the `Screen` class (or `_Screen` — check line ~45). Add `PROJECTS`:

  ```python
      PROJECTS        = 'projects'
  ```

  Add it after `REVIEW = 'review'`.

- [ ] **Step 2: Add PROJECTS message types**

  Near the other message dataclasses (search for `_ProgressMsg` or `_DoneMsg`), add:

  ```python
  @dataclasses.dataclass
  class _ProjectProgressMsg:
      project_name: str
      count: int

  @dataclasses.dataclass
  class _ProjectDoneMsg:
      applied: int
      conflicts: int

  @dataclasses.dataclass
  class _ProjectErrorMsg:
      error: str

  @dataclasses.dataclass
  class _TokenSavedMsg:
      success: bool
      message: str
  ```

  (If the file uses `dataclasses` already, import it at top if not present; otherwise use simple classes matching the existing pattern.)

- [ ] **Step 3: Add PROJECTS state to AppModel.__init__**

  In `AppModel.__init__`, after the EXPORT SETTINGS block, add:

  ```python
          # PROJECTS
          from project_fetcher import load_token, TOKEN_FILE
          _tok = load_token()
          self.pj_token_found: bool = _tok is not None
          self.pj_projects_count: int = len(_load_chatgpt_projects())
          self.pj_paste_mode: bool = False
          self.pj_paste_input: str = ''
          self.pj_syncing: bool = False
          self.pj_status: str = ''     # 'ok:...' | 'error:...' | ''
          self.pj_progress: str = ''   # current gizmo name being fetched
          self.pj_applied: int = 0
          self.pj_conflicts: int = 0
  ```

  Add the helper import at the top of `tui.py` (alongside the other imports near the top of the file):

  ```python
  from config import load_chatgpt_projects as _load_chatgpt_projects
  ```

- [ ] **Step 4: Add 'Projects' to menu_items and update the main menu navigation**

  In `AppModel.__init__`, find:

  ```python
          self.menu_items: list[str] = ['Import', 'Settings', 'Export', 'Review', 'Search']
  ```

  Change to:

  ```python
          self.menu_items: list[str] = ['Import', 'Settings', 'Export', 'Review', 'Projects', 'Search']
  ```

  Find the main menu key handler that switches screens based on menu_cursor. It likely looks like:

  ```python
              dest = [Screen.FOLDER_BROWSER, Screen.SETTINGS, Screen.EXPORT_SETTINGS, Screen.REVIEW, Screen.SEARCH]
  ```

  Change to:

  ```python
              dest = [Screen.FOLDER_BROWSER, Screen.SETTINGS, Screen.EXPORT_SETTINGS, Screen.REVIEW, Screen.PROJECTS, Screen.SEARCH]
  ```

- [ ] **Step 5: Register PROJECTS screen in dispatch tables**

  Find the `update` method dispatch dicts. Add `PROJECTS` entries:

  ```python
              Screen.PROJECTS:        self._key_projects,
  ```

  and:

  ```python
              Screen.PROJECTS:        self._view_projects,
  ```

- [ ] **Step 6: Add _cmd_sync_projects worker function**

  Near the other `_cmd_*` functions (after `_cmd_run`), add:

  ```python
  def _cmd_sync_projects(
      token: str,
      projects: dict[str, str],
      conflict_mode: str,
      db: 'DatabaseManager',
      program,
  ) -> None:
      """Fetch project→conversation map from ChatGPT API and update DB.

      Uses daemon thread + program.send() pattern (same as _cmd_run).
      """
      import threading

      def _run() -> None:
          from project_fetcher import fetch_project_map

          def progress_cb(project_name: str, count: int) -> None:
              if program:
                  program.send(_ProjectProgressMsg(project_name=project_name, count=count))

          try:
              mapping = fetch_project_map(token, projects, progress_cb)
              applied, conflicts = db.bulk_update_projects(mapping, conflict_mode)
              if program:
                  program.send(_ProjectDoneMsg(applied=applied, conflicts=conflicts))
          except Exception as exc:
              if program:
                  program.send(_ProjectErrorMsg(error=str(exc)))

      threading.Thread(target=_run, daemon=True).start()


  def _cmd_browser_token(program) -> None:
      """Auto-extract ChatGPT token from browser in a background thread."""
      import threading

      def _run() -> None:
          from retrieve_token import get_chatgpt_token_from_browser, save_token
          try:
              token = get_chatgpt_token_from_browser()
              if token:
                  save_token(token)
                  if program:
                      program.send(_TokenSavedMsg(success=True, message='Token saved'))
              else:
                  if program:
                      program.send(_TokenSavedMsg(success=False, message='No token found in browser — try --paste'))
          except Exception as exc:
              if program:
                  program.send(_TokenSavedMsg(success=False, message=str(exc)))

      threading.Thread(target=_run, daemon=True).start()
  ```

- [ ] **Step 7: Add _key_projects handler**

  Add the following method to `AppModel` (alongside `_key_settings`, `_key_review`, etc.):

  ```python
      def _key_projects(self, msg) -> tuple['AppModel', None]:
          # Handle async messages from worker threads
          if isinstance(msg, _ProjectProgressMsg):
              self.pj_progress = f"Fetching '{msg.project_name}'… {msg.count} conversations"
              return self, None
          if isinstance(msg, _ProjectDoneMsg):
              self.pj_syncing = False
              self.pj_applied = msg.applied
              self.pj_conflicts = msg.conflicts
              conflict_warn = f'  ⚠ {msg.conflicts} conflict(s)' if msg.conflicts else ''
              self.pj_status = f'ok:Applied: {msg.applied}  Conflicts: {msg.conflicts}{conflict_warn}'
              return self, None
          if isinstance(msg, _ProjectErrorMsg):
              self.pj_syncing = False
              self.pj_status = f'error:{msg.error}'
              return self, None
          if isinstance(msg, _TokenSavedMsg):
              if msg.success:
                  from project_fetcher import load_token
                  self.pj_token_found = load_token() is not None
                  self.pj_status = 'ok:Token saved'
              else:
                  self.pj_status = f'error:{msg.message}'
              return self, None

          if not isinstance(msg, tea.KeyMsg):
              return self, None
          key = msg.key

          if self.pj_paste_mode:
              if key == 'escape':
                  self.pj_paste_mode = False
                  self.pj_paste_input = ''
              elif key == 'enter' and self.pj_paste_input:
                  from retrieve_token import parse_token_string, save_token
                  try:
                      token = parse_token_string(self.pj_paste_input)
                      save_token(token)
                      self.pj_token_found = True
                      self.pj_paste_mode = False
                      self.pj_paste_input = ''
                      self.pj_status = 'ok:Token saved'
                  except ValueError as e:
                      self.pj_status = f'error:{e}'
              elif key == 'backspace':
                  self.pj_paste_input = self.pj_paste_input[:-1]
              elif key == 'ctrl+u':
                  self.pj_paste_input = ''
              elif len(key) == 1:
                  self.pj_paste_input += key
              return self, None

          if key in ('escape', 'q'):
              self.screen = Screen.MAIN
          elif key == 'b' and not self.pj_syncing:
              self.pj_status = 'ok:Extracting token from browser…'
              _cmd_browser_token(self._program)
          elif key == 'v' and not self.pj_syncing:
              self.pj_paste_mode = True
              self.pj_paste_input = ''
              self.pj_status = ''
          elif key in ('enter', 'r') and not self.pj_syncing and self.pj_token_found:
              from project_fetcher import load_token
              from config import load_chatgpt_projects, load_sync_config
              token = load_token()
              projects = load_chatgpt_projects()
              if not token:
                  self.pj_status = 'error:No token found — use [B] or [V] first'
              elif not projects:
                  self.pj_status = 'error:No projects configured in ~/.keromdizer.toml'
              else:
                  conflict_mode = self.st_values.get('project_conflict', 'preserve')
                  self.pj_syncing = True
                  self.pj_progress = 'Starting sync…'
                  self.pj_status = ''
                  _cmd_sync_projects(token, projects, conflict_mode, self._db, self._program)

          return self, None
  ```

- [ ] **Step 8: Add _view_projects renderer**

  Add the following method to `AppModel`:

  ```python
      def _view_projects(self) -> str:
          lines = [self._header('Projects'), '']

          # Token status row
          if self.pj_token_found:
              tok_s = success_style.render('● Found')
          else:
              tok_s = error_style.render('○ Missing')
          lines.append(f'  Token status:  {tok_s}')
          lines.append(muted_style.render('                              [B] Sync from browser'))
          lines.append(muted_style.render('                              [V] Paste token'))
          lines.append('')

          # Projects count
          if self.pj_projects_count:
              lines.append(muted_style.render(f'  Projects configured: {self.pj_projects_count}  (from ~/.keromdizer.toml)'))
          else:
              lines.append(error_style.render('  No projects configured — see docs/chatgpt-projects-guide.md'))
          lines.append('')

          # Paste mode input
          if self.pj_paste_mode:
              lines.append(muted_style.render('  Paste token (enter confirm, esc cancel):'))
              display = self.pj_paste_input or ''
              lines.append(f'  {display}\u2588')
              lines.append('')

          # Sync progress / status
          if self.pj_syncing:
              lines.append(muted_style.render(f'  {self.pj_progress}'))
          elif self.pj_status:
              prefix, _, rest = self.pj_status.partition(':')
              s = success_style.render(rest) if prefix == 'ok' else error_style.render(rest)
              lines.append(f'  {s}')
          lines.append('')

          # Action row
          if self.pj_token_found and self.pj_projects_count and not self.pj_syncing:
              lines.append(sel_style.render('  [Enter / R]  Run sync now'))
          elif self.pj_syncing:
              lines.append(muted_style.render('  Syncing…'))
          else:
              lines.append(muted_style.render('  [Enter / R]  Run sync now  (retrieve token first)'))

          lines += ['', self._footer('[B] browser token   [V] paste token   Enter sync   Esc back')]
          return self._panel('\n'.join(lines))
  ```

- [ ] **Step 9: Verify TUI starts without errors**

  ```bash
  python -c "from tui import AppModel; m = AppModel(); print('PROJECTS screen registered')"
  ```

  Expected: `PROJECTS screen registered` (no exceptions)

- [ ] **Step 10: Commit**

  ```bash
  git add tui.py
  git commit -m "feat: add PROJECTS screen to TUI with browser/paste token retrieval and sync"
  ```

---

## Task 8: User guide + final checks

**Files:**
- Create: `docs/chatgpt-projects-guide.md`

- [ ] **Step 1: Create the guide**

  Create `docs/chatgpt-projects-guide.md`:

  ````markdown
  # Finding Your ChatGPT Project Gizmo IDs

  KeroMDizer can automatically associate your imported conversations with their
  ChatGPT project names. To enable this, you need to find the **gizmo ID** for
  each of your projects.

  ---

  ## What is a Gizmo ID?

  Every ChatGPT project has a unique gizmo ID embedded in its URL. It looks like:

  ```
  g-p-69b19d003d948191836ab8081b8fddfc
  ```

  ---

  ## How to Find Your Project URLs

  1. Go to [chatgpt.com](https://chatgpt.com) and log in.
  2. Open a project from the left sidebar.
  3. Look at the browser address bar. The URL will be one of:

     - Project page: `https://chatgpt.com/g/{gizmo_id}-{slug}/project`
     - A chat inside the project: `https://chatgpt.com/g/{gizmo_id}-{slug}/c/{conversation_id}`

  4. Copy the `g-p-...` portion — that is your gizmo ID.

  ---

  ## Add Your Projects to ~/.keromdizer.toml

  Open `~/.keromdizer.toml` (create it if it doesn't exist) and add a
  `[chatgpt.projects]` section:

  ```toml
  [chatgpt.projects]
  "g-p-69b19d003d948191836ab8081b8fddfc" = "My Work Project"
  "g-p-69758729f94481919287e4329d3cfd3a" = "Personal Notes"
  ```

  The key is the gizmo ID; the value is the project name that will appear in your
  exported files and the REVIEW screen.

  ---

  ## Retrieving Your Bearer Token

  The sync requires a short-lived Bearer token from your ChatGPT session.

  ### Option 1 — Auto-extract from browser (easiest)

  ```bash
  python retrieve_token.py
  ```

  This uses your browser's local session cookies. Works best with Firefox.
  You must be logged in to chatgpt.com.

  ### Option 2 — Paste from browser console

  1. Open [chatgpt.com](https://chatgpt.com) in your browser.
  2. Open DevTools (F12) → **Console** tab.
  3. Paste and run:

     ```js
     (async () => {
       const s = await fetch('/api/auth/session').then(r => r.json());
       console.log(s.accessToken);
     })();
     ```

  4. Copy the printed token (starts with `eyJ`).
  5. Run:

     ```bash
     python retrieve_token.py --paste "eyJ..."
     ```

     Or use `[V] Paste token` in the TUI PROJECTS screen.

  ---

  ## Running the Sync

  ### Via TUI

  1. Launch the TUI: `python tui.py`
  2. Select **Projects** from the main menu.
  3. Use **[B]** to auto-extract the token from your browser, or **[V]** to paste.
  4. Press **Enter** to run the sync.

  ### Notes

  - Tokens expire in ~20 minutes. Re-run `retrieve_token.py` if the sync fails with
    an auth error.
  - The sync conflict behaviour can be changed in **Settings → Project sync conflict**:
    - `preserve` (default) — only fills empty project fields
    - `overwrite` — always replaces with the fetched project name
    - `flag` — same as overwrite, but shows a warning count in the UI
  ````

- [ ] **Step 2: Run full test suite one final time**

  ```bash
  pytest tests/ -v
  ```

  Expected: all PASS

- [ ] **Step 3: Commit guide and requirements**

  ```bash
  git add docs/chatgpt-projects-guide.md requirements-dev.txt
  git commit -m "docs: add ChatGPT projects guide; update requirements with requests and browser_cookie3"
  ```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ `retrieve_token.py` — Task 5
- ✅ `project_fetcher.py` with `load_token` / `fetch_project_map` / pagination / progress_cb — Task 4
- ✅ `SyncConfig` dataclass — Task 1
- ✅ `load_chatgpt_projects`, `load_sync_config`, `save_sync_config` — Task 2
- ✅ `bulk_update_projects` with all 3 conflict modes — Task 3
- ✅ PROJECTS screen with token status, browser/paste, sync, progress, summary — Task 7
- ✅ SETTINGS `project_conflict` 3-value cycle field — Task 6
- ✅ `docs/chatgpt-projects-guide.md` — Task 8
- ✅ `requirements-dev.txt` updated — Task 4 Step 1

**Type consistency check:**
- `fetch_project_map` signature matches between `project_fetcher.py` (Task 4) and its call in `_cmd_sync_projects` (Task 7) ✅
- `bulk_update_projects(mapping, conflict_mode)` matches between `db.py` (Task 3) and TUI call (Task 7) ✅
- `save_token(token, token_file=...)` matches between `retrieve_token.py` (Task 5) and `_cmd_browser_token` (Task 7) ✅
- `_TokenSavedMsg`, `_ProjectProgressMsg`, `_ProjectDoneMsg`, `_ProjectErrorMsg` defined in Task 7 Step 2 and consumed in Task 7 Step 7 ✅
- `st_cycle3_fields` added in Task 6 Step 3 and used in Task 6 Step 4 and Step 5 ✅
