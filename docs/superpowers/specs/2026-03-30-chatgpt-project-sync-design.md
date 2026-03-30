# ChatGPT Project Sync — Design Spec

**Date:** 2026-03-30
**Status:** Approved

---

## Overview

Associate ChatGPT conversations in the KeroMDizer DB with their ChatGPT project
names, using the ChatGPT backend API. The project name populates the existing
`branches.project` column (currently only set manually via the REVIEW screen).

Two scopes:
1. **Personal bootstrap** — Matt's 19 project gizmo IDs stored in `~/.keromdizer.toml`
2. **General users** — guided to find their own gizmo IDs via a public docs guide

---

## Architecture

### New files

#### `retrieve_token.py`
Standalone CLI script, mirrors KeroOle's `retrieve_cookies.py`.

**Modes:**
- **Default (no args):** auto-extract `__Secure-next-auth.session-token` cookie
  from the browser via `browser_cookie3` (Firefox first, then Chrome/Chromium),
  then exchange it by calling `https://chatgpt.com/api/auth/session` with
  `requests` to obtain the Bearer access token.
- **`--paste "eyJ..."`** — user pastes the Bearer token directly (e.g. copied
  from the JS snippet: `(await fetch('/api/auth/session').then(r=>r.json())).accessToken`)
- **`--stdin`** — pipe-friendly paste (e.g. `xclip -o | python retrieve_token.py --stdin`)

**Output:** writes `~/.keromdizer_token.json`:
```json
{"access_token": "eyJ...", "fetched_at": "2026-03-30T14:22:00+00:00"}
```

`browser_cookie3` is an optional dependency — all three modes degrade
gracefully if it is absent, with clear error messages pointing to alternatives.

#### `project_fetcher.py`
Pure-functions module (no CLI, no side-effects beyond network calls). Called by
the TUI PROJECTS screen worker thread and optionally by `keromdizer.py`.

**Public API:**
```python
TOKEN_FILE: Path  # ~/.keromdizer_token.json

def load_token(token_file: Path = TOKEN_FILE) -> str | None:
    """Read access_token from token JSON file. Returns None if missing."""

def fetch_project_map(
    token: str,
    projects: dict[str, str],   # {gizmo_id: project_name} from TOML
    progress_cb: Callable[[str, int], None] | None = None,
) -> dict[str, str]:            # {conversation_id: project_name}
    """For each gizmo_id, GET /backend-api/gizmos/{id}/conversations with
    cursor pagination until exhausted. Returns full conversation→project map.
    progress_cb(project_name, conv_count) called after each gizmo completes."""
```

Pagination: follows `cursor` field in API response; stops when cursor is null
or response contains no items.

#### `docs/chatgpt-projects-guide.md`
Public, committed user guide covering:
- What a gizmo ID is and where it appears in project page URLs
- How to find your project URLs (`chatgpt.com/g/{gizmo_id}-{slug}/project`)
- How to add them to `~/.keromdizer.toml` under `[chatgpt.projects]`
- How to retrieve a Bearer token (the JS browser-console snippet)

---

### Modified files

#### `models.py`
New dataclass:
```python
@dataclass
class SyncConfig:
    project_conflict: str = 'preserve'  # 'preserve' | 'overwrite' | 'flag'
```

#### `config.py`
Three additions following existing patterns:

```python
def load_chatgpt_projects() -> dict[str, str]:
    """Read [chatgpt.projects] from ~/.keromdizer.toml.
    Returns {gizmo_id: project_name}. Empty dict if section absent."""

def load_sync_config() -> SyncConfig:
    """Read [sync] section. Defaults: project_conflict = 'preserve'."""

def save_sync_config(cfg: SyncConfig) -> None:
    """Write [sync] section back to ~/.keromdizer.toml, preserving other sections."""
```

TOML format:
```toml
[sync]
project_conflict = "preserve"   # preserve | overwrite | flag

[chatgpt.projects]
"g-p-69b19d003d..." = "App Career Tracker and resume generation"
"g-p-69758729f9..." = "Tech Random"
# ... etc
```

#### `db.py`
New method:
```python
def bulk_update_projects(
    self,
    mapping: dict[str, str],        # {conversation_id: project_name}
    conflict_mode: str = 'preserve',
) -> tuple[int, int]:               # (applied, conflicts)
```

Behaviour by mode:
- **`preserve`** (default): only writes to rows where `project IS NULL OR project = ''`
- **`overwrite`**: always writes, regardless of existing value
- **`flag`**: always writes; counts rows where `project` was already non-null
  before the write — that count is returned as `conflicts`

Applies to **all branches** of a matched conversation (branch 1, 2, etc. all
receive the same project label, matching the existing pattern where project is
stored per-branch).

Returns `(applied, conflicts)`:
- `applied` — number of branch rows updated
- `conflicts` — number of rows that had an existing non-null project value
  (always 0 for `preserve` mode; meaningful for `flag` and `overwrite`)

#### `tui.py`
**Main menu** — new entry `[P] Projects` inserted between `[R] Review` and
`[S] Settings`.

**New `PROJECTS` screen (`_Screen.PROJECTS`):**

```
Token status:  ● Found  (fetched 2026-03-30)        [B] Sync from browser
               ○ Missing                             [V] Paste token

Projects configured: 19  (from ~/.keromdizer.toml)

Last sync:  2026-03-30 14:22  ·  312 applied  ·  0 conflicts

[Enter / R]  Run sync now
[Esc / Q]    Back to main menu
```

States:
- **Token missing:** sync button greyed out with inline hint ("Retrieve a token
  first with [B] or [V]")
- **No projects configured:** inline hint pointing to the guide doc
- **Syncing:** progress line updates per gizmo as each completes
  (`Fetching 'TBD Engineering'… 42 conversations`)
- **Complete:** summary bar `Applied: 312  Skipped: 47  Conflicts: 0`
- **Error:** red inline message with the error string

Worker: daemon thread + `program.send(msg)` pattern, consistent with existing
`_cmd_run` / `_cmd_scan`. Messages: `_ProjectProgressMsg`, `_ProjectDoneMsg`,
`_ProjectErrorMsg`.

**`SETTINGS` screen** — field 8 (after existing 7):
- Label: `Project conflict`
- Values cycle on Enter/Space: `preserve` → `overwrite` → `flag`
- Saved via `save_sync_config()` on Save (same Save button at index 8, tab
  wraps at modulo 9)

#### `requirements-dev.txt`
Add:
```
requests
browser_cookie3
```

---

## Data flow

```
User opens PROJECTS screen
    → reads token from ~/.keromdizer_token.json
    → reads projects from ~/.keromdizer.toml [chatgpt.projects]
    → [B] triggers browser auto-extract (retrieve_token logic inline or imported)
    → [V] opens paste input field
    → [Enter/R] spawns worker thread:
         project_fetcher.fetch_project_map(token, projects, progress_cb)
             → for each gizmo: GET /backend-api/gizmos/{id}/conversations (paginated)
             → returns {conversation_id: project_name}
         db.bulk_update_projects(mapping, conflict_mode)
             → returns (applied, conflicts)
         sends _ProjectDoneMsg(applied, conflicts)
    → screen renders summary
```

---

## Conflict modes

| Mode | Behaviour | `applied` | `conflicts` |
|---|---|---|---|
| `preserve` | Only fill NULL/empty project fields | rows written | always 0 |
| `overwrite` | Always overwrite | rows written | rows that had existing value |
| `flag` | Always overwrite + report | rows written | rows that had existing value |

`overwrite` and `flag` produce the same DB result; `flag` differs only in that
the UI explicitly surfaces the conflict count as a warning.

---

## Out of scope (potential future work)

- Auto-discover gizmo IDs via API (no confirmed endpoint at time of writing)
- Token refresh / expiry handling (tokens are short-lived; user re-runs retrieve_token.py)
- Persisting last-sync timestamp (can be added to token file or a separate state file)
- CLI `--sync-projects` flag on `keromdizer.py`
