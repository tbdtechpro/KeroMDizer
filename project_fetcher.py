"""
project_fetcher.py — fetch conversation→project mapping from ChatGPT backend API.

Reads Bearer token from ~/.keromdizer_token.json and iterates gizmo IDs from
~/.keromdizer.toml [chatgpt.projects] to build a {conversation_id: project_name} map.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from curl_cffi import requests
from curl_cffi.requests.exceptions import HTTPError as _HTTPError, RequestException as _RequestException

TOKEN_FILE = Path.home() / '.keromdizer_token.json'

_BASE = 'https://chatgpt.com/backend-api'

# Headers required by the ChatGPT backend — without these the API returns 403.
# OAI-Client-Version is a deploy-specific build hash; update if requests start
# failing with 403 again after a ChatGPT deployment.
_OAI_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:149.0) '
        'Gecko/20100101 Firefox/149.0'
    ),
    'OAI-Language': 'en-US',
    'OAI-Device-Id': 'aabb38b5-d023-4b2f-bf44-59ba6f651ecc',
    'OAI-Client-Version': 'prod-80ec947d8ad58141eec80e90da47cc7d76fb08aa',
    'OAI-Client-Build-Number': '5588781',
}


def check_token_audience(token: str) -> str | None:
    """Decode the JWT payload and warn if the token is not for the ChatGPT web backend.

    Returns a warning string if the audience looks wrong, or None if it looks fine.
    Does not verify the signature — only reads the claims.
    """
    import base64
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None  # not a JWT, let it fail at the API
        padded = parts[1] + '=' * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except Exception:
        return None  # unreadable, let the API decide

    aud = payload.get('aud') or []
    if isinstance(aud, str):
        aud = [aud]

    # ChatGPT web tokens are issued for chatgpt.com; API tokens for api.openai.com/v1.
    # If only api.openai.com is present, this is the wrong token type.
    has_chatgpt = any('chatgpt.com' in a for a in aud)
    has_api_only = any('api.openai.com' in a for a in aud) and not has_chatgpt
    if has_api_only:
        return (
            'This looks like an OpenAI API token (aud: api.openai.com), '
            'not a ChatGPT web token. Use the browser console JS snippet instead — '
            'see docs/chatgpt-projects-guide.md'
        )
    return None


def load_token(token_file: Path = TOKEN_FILE) -> str | None:
    """Read access_token from token JSON file. Returns None if missing or malformed."""
    try:
        data = json.loads(token_file.read_text(encoding='utf-8'))
        return data.get('access_token') or None
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def load_token_age(token_file: Path = TOKEN_FILE) -> str | None:
    """Return a human-readable age string for the saved token (e.g. '3m ago', '2h ago').

    Returns None if the file is missing or has no fetched_at field.
    """
    try:
        data = json.loads(token_file.read_text(encoding='utf-8'))
        fetched_at = data.get('fetched_at')
        if not fetched_at:
            return None
    except (OSError, json.JSONDecodeError, ValueError):
        return None

    from datetime import datetime, timezone
    try:
        saved = datetime.fromisoformat(fetched_at)
        now = datetime.now(tz=timezone.utc)
        seconds = int((now - saved).total_seconds())
    except (ValueError, TypeError):
        return None

    if seconds < 60:
        return f'{seconds}s ago'
    if seconds < 3600:
        return f'{seconds // 60}m ago'
    return f'{seconds // 3600}h ago'


def validate_token(token: str) -> str | None:
    """Check that the token is accepted by the ChatGPT backend.

    Hits /backend-api/conversations?limit=1 — a confirmed-working lightweight endpoint.
    Returns None on success, or an error string describing the problem.
    """
    try:
        resp = requests.get(
            f'{_BASE}/conversations',
            headers={**_OAI_HEADERS, 'Authorization': f'Bearer {token}'},
            params={'limit': 1},
            timeout=15,
            impersonate='firefox',
        )
        if resp.status_code == 401:
            return 'Token rejected (401 Unauthorized) — use [B] or [V] to get a fresh token'
        if resp.status_code == 403:
            try:
                body = resp.json()
                detail = body.get('detail') or body.get('message') or resp.text[:120]
            except Exception:
                detail = resp.text[:120]
            return f'Token rejected (403 Forbidden): {detail}'
        resp.raise_for_status()
        return None
    except _RequestException as exc:
        return f'Network error during token check: {exc}'


def fetch_project_map(
    token: str,
    projects: dict[str, str],
    progress_cb: Callable[[str, int], None] | None = None,
) -> tuple[dict[str, str], int]:
    """Fetch all conversations for each gizmo and return ({conv_id: project_name}, skipped_count).

    Args:
        token:       ChatGPT Bearer access token.
        projects:    {gizmo_id: project_name} from ~/.keromdizer.toml.
        progress_cb: Optional callback called after each gizmo is fully fetched.
                     Receives (project_name, conversation_count).

    Returns a tuple of (mapping dict, number of gizmos skipped due to 403 Forbidden).
    """
    if not projects:
        return {}, 0

    headers = {**_OAI_HEADERS, 'Authorization': f'Bearer {token}'}
    result: dict[str, str] = {}
    skipped = 0

    for gizmo_id, project_name in projects.items():
        try:
            conv_ids = _fetch_all_conversations(gizmo_id, headers)
        except _HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 403:
                skipped += 1
                if progress_cb is not None:
                    progress_cb(project_name, 0)
                continue
            # Attach response body to non-403 HTTP errors for easier debugging
            if exc.response is not None:
                try:
                    body = exc.response.text[:200]
                except Exception:
                    body = ''
                raise _HTTPError(
                    f'{exc} — response body: {body}', response=exc.response
                ) from exc
            raise
        for conv_id in conv_ids:
            result[conv_id] = project_name
        if progress_cb is not None:
            progress_cb(project_name, len(conv_ids))

    return result, skipped


def _fetch_all_conversations(gizmo_id: str, headers: dict) -> list[str]:
    """Fetch all conversation IDs for one gizmo, following cursor pagination.

    Endpoint: GET /backend-api/gizmos/{gizmo_id}/conversations?cursor=0
    Confirmed format from chatgpt-projects-reference.md (captured 2026-03-29).
    """
    url = f'{_BASE}/gizmos/{gizmo_id}/conversations'
    cursor: str | None = '0'
    conv_ids: list[str] = []

    while cursor is not None:
        resp = requests.get(url, headers=headers, params={'cursor': cursor}, timeout=30, impersonate='firefox')
        if not resp.ok:
            try:
                body = resp.json()
                detail = body.get('detail') or body.get('message') or resp.text[:200]
            except Exception:
                detail = resp.text[:200]
            resp.reason = f'{resp.reason} — {detail}'
        resp.raise_for_status()
        data = resp.json()
        items = data.get('items') or []
        if not items:
            break
        for item in items:
            cid = item.get('conversation_id') or item.get('id')
            if cid:
                conv_ids.append(cid)
        new_cursor = data.get('cursor') or None
        if not new_cursor or new_cursor == cursor:
            break
        cursor = new_cursor

    return conv_ids
