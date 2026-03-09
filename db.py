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
        # Migrations — each ALTER TABLE is idempotent (ignored if column already exists)
        for _sql in [
            "ALTER TABLE branches ADD COLUMN md_filename TEXT",
            "ALTER TABLE conversations ADD COLUMN user_alias TEXT",
            "ALTER TABLE conversations ADD COLUMN assistant_alias TEXT",
        ]:
            try:
                self._conn.execute(_sql)
                self._conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists

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
        user_alias: str | None = None,
        assistant_alias: str | None = None,
    ) -> None:
        """Insert or replace a conversation and all its branches.

        user_alias / assistant_alias are the display names that were active at
        import time (may differ from the provider canon if the user configured
        custom names).  Stored so exports can reproduce the same labels without
        needing to re-read config.
        """
        self._conn.execute(
            '''INSERT OR REPLACE INTO conversations
               (conversation_id, provider, title, create_time, update_time, model_slug,
                branch_count, user_alias, assistant_alias)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (conversation_id, provider, title, create_time, update_time, model_slug,
             branch_count, user_alias, assistant_alias),
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
            # Preserve existing md_filename; update if new value provided
            cur_md = self._conn.execute(
                'SELECT md_filename FROM branches WHERE branch_id=?',
                (b['branch_id'],)
            ).fetchone()
            existing_md = cur_md['md_filename'] if cur_md else None
            new_md = b.get('md_filename') or existing_md
            self._conn.execute(
                '''INSERT OR REPLACE INTO branches
                   (branch_id, conversation_id, branch_index, is_main_branch,
                    messages, tags, project, category, syntax,
                    inferred_tags, inferred_syntax, md_filename)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
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
                    new_md,
                ),
            )
        self._conn.commit()

    def get_branch(self, branch_id: str) -> dict | None:
        row = self._conn.execute(
            '''SELECT b.branch_id, b.conversation_id, b.branch_index, b.is_main_branch,
                      b.messages, b.tags, b.project, b.category, b.syntax,
                      b.inferred_tags, b.inferred_syntax, b.md_filename,
                      c.title, c.provider, c.create_time AS conv_create_time, c.model_slug,
                      c.branch_count, c.user_alias, c.assistant_alias
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
                      b.inferred_tags, b.inferred_syntax, b.md_filename,
                      c.title, c.provider, c.create_time AS conv_create_time, c.model_slug,
                      c.branch_count, c.user_alias, c.assistant_alias
               FROM branches b
               JOIN conversations c ON b.conversation_id = c.conversation_id'''
        if main_only:
            q += ' WHERE b.is_main_branch = 1'
        q += ' ORDER BY c.create_time DESC LIMIT ? OFFSET ?'
        rows = self._conn.execute(q, (limit, offset)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def search_branches(
        self,
        query: str = '',
        provider: str = '',
        syntax: str = '',
        main_only: bool = False,
        limit: int = 500,
    ) -> list[dict]:
        """Search branches by text (title, tags, project, message content) and filters."""
        conditions = []
        params: list = []
        if query:
            q = f'%{query}%'
            conditions.append(
                '(c.title LIKE ? OR b.tags LIKE ? OR b.inferred_tags LIKE ? '
                'OR b.project LIKE ? OR b.messages LIKE ?)'
            )
            params.extend([q, q, q, q, q])
        if provider:
            conditions.append('c.provider = ?')
            params.append(provider)
        if syntax:
            s = f'%{syntax}%'
            conditions.append('(b.syntax LIKE ? OR b.inferred_syntax LIKE ?)')
            params.extend([s, s])
        if main_only:
            conditions.append('b.is_main_branch = 1')
        where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
        rows = self._conn.execute(
            f'''SELECT b.branch_id, b.conversation_id, b.branch_index, b.is_main_branch,
                       b.tags, b.project, b.category, b.syntax,
                       b.inferred_tags, b.inferred_syntax, b.md_filename,
                       c.title, c.provider, c.create_time AS conv_create_time, c.model_slug
                FROM branches b
                JOIN conversations c ON b.conversation_id = c.conversation_id
                {where}
                ORDER BY c.create_time DESC LIMIT ?''',
            params + [limit],
        ).fetchall()
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

    def backfill_md_filenames(self, output_dir) -> int:
        """Scan output_dir for .md files and populate md_filename for branches that lack it.

        Reads the title and Branch header from each .md file's first few lines, then
        matches against conversations by title + date + branch_index.  Only updates
        rows where md_filename is currently NULL or empty.  Returns number updated.
        """
        import re
        from pathlib import Path as _Path

        branch_re = re.compile(r'Branch (\d+) of \d+')
        date_re   = re.compile(r'(\d{4}-\d{2}-\d{2})')

        output_dir = _Path(output_dir)
        try:
            md_files = list(output_dir.glob('*.md'))
        except OSError:
            return 0

        updated = 0
        for md_path in md_files:
            try:
                with open(md_path, encoding='utf-8') as f:
                    line1 = f.readline().rstrip('\n')  # "# Title"
                    f.readline()                        # blank
                    line3 = f.readline().rstrip('\n')  # "_date · model · Branch N of M_"
            except OSError:
                continue

            if not line1.startswith('# '):
                continue
            title = line1[2:]

            date_m = date_re.search(line3)
            if not date_m:
                continue
            date_str = date_m.group(1)

            branch_m = branch_re.search(line3)
            branch_idx = int(branch_m.group(1)) if branch_m else 1

            row = self._conn.execute(
                '''SELECT b.branch_id FROM branches b
                   JOIN conversations c ON b.conversation_id = c.conversation_id
                   WHERE c.title = ?
                     AND substr(c.create_time, 1, 10) = ?
                     AND b.branch_index = ?
                     AND (b.md_filename IS NULL OR b.md_filename = '')
                   LIMIT 1''',
                (title, date_str, branch_idx),
            ).fetchone()

            if row:
                self._conn.execute(
                    'UPDATE branches SET md_filename=? WHERE branch_id=?',
                    (md_path.name, row['branch_id']),
                )
                updated += 1

        if updated:
            self._conn.commit()
        return updated

    def close(self) -> None:
        self._conn.close()

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        for json_field in ('messages', 'tags', 'syntax', 'inferred_tags', 'inferred_syntax'):
            if isinstance(d.get(json_field), str):
                d[json_field] = json.loads(d[json_field])
        d['is_main_branch'] = bool(d.get('is_main_branch'))
        return d
