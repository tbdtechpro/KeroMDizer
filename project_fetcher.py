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
