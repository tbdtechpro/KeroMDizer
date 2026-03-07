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
        limit: int = 10000,
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
        """Return sorted list of all unique tags for autocomplete.

        Includes both user-applied tags and inferred_tags so suggestions
        appear even before any manual tagging has been done.
        """
        rows = self._conn.execute(
            'SELECT tags, inferred_tags FROM branches'
        ).fetchall()
        seen: set[str] = set()
        for row in rows:
            for tag in json.loads(row['tags']):
                if tag:
                    seen.add(tag)
            for tag in json.loads(row['inferred_tags']):
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
