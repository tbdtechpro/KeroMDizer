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
