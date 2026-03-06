from datetime import datetime
from pathlib import Path
from models import Conversation, Branch, Message
from conversation_parser import ConversationParser


class DeepSeekParser(ConversationParser):

    def _load_shared_ids(self) -> set[str]:
        """Always return empty set — DeepSeek has no shared conversations."""
        return set()

    def _parse_iso_timestamp_safe(self, ts: str | None) -> float | None:
        """Parse ISO 8601 string to Unix float. Returns None on error or None input."""
        if ts is None:
            return None
        try:
            return datetime.fromisoformat(ts).timestamp()
        except (ValueError, TypeError):
            return None

    def _extract_model(self, mapping: dict, path_ids: list[str]) -> str | None:
        """Return model from first RESPONSE fragment node in the path."""
        for nid in path_ids:
            node = mapping.get(nid, {})
            msg = node.get('message')
            if not msg:
                continue
            for fragment in msg.get('fragments', []):
                if fragment.get('type') == 'RESPONSE':
                    return msg.get('model')
        return None

    def _parse_conversation(self, raw: dict) -> Conversation | None:
        mapping = raw.get('mapping', {})

        leaf_ids = self._find_leaf_ids(mapping)
        if not leaf_ids:
            return None

        # Main branch = leaf with latest inserted_at timestamp
        def leaf_ts(leaf_id):
            msg = mapping.get(leaf_id, {}).get('message') or {}
            ts = msg.get('inserted_at')
            return self._parse_iso_timestamp_safe(ts) or 0.0

        main_leaf = max(leaf_ids, key=leaf_ts)

        branches = []
        seen_paths = set()

        for leaf_id in leaf_ids:
            path = self._trace_to_root(mapping, leaf_id)
            path_key = tuple(path)
            if path_key in seen_paths:
                continue
            seen_paths.add(path_key)

            messages = self._extract_messages(mapping, path)
            if not messages:
                continue

            is_main = (leaf_id == main_leaf)
            branches.append((is_main, path_key, messages))

        if not branches:
            return None

        # Main branch first
        branches.sort(key=lambda x: (0 if x[0] else 1))
        final_branches = [
            Branch(messages=msgs, branch_index=i + 1)
            for i, (_, _, msgs) in enumerate(branches)
        ]

        # Model: from first RESPONSE in main branch (reuse already-computed path)
        model_slug = self._extract_model(mapping, list(branches[0][1]))

        conv_id = raw.get('id') or raw.get('conversation_id', '')

        return Conversation(
            id=conv_id,
            title=(raw.get('title') or '').strip() or 'Untitled',
            create_time=self._parse_iso_timestamp_safe(raw.get('inserted_at')),
            update_time=self._parse_iso_timestamp_safe(raw.get('updated_at')),
            model_slug=model_slug,
            branches=final_branches,
            audio_count=0,
        )

    def _extract_messages(self, mapping: dict, path_ids: list[str]) -> list[Message]:
        messages = []
        for nid in path_ids:
            node = mapping.get(nid, {})
            msg = node.get('message')
            if not msg:
                continue
            for fragment in msg.get('fragments', []):
                ftype = fragment.get('type')
                if ftype == 'REQUEST':
                    role = 'user'
                elif ftype == 'RESPONSE':
                    role = 'assistant'
                else:
                    continue  # Skip THINK, SEARCH, etc.

                text = fragment.get('content', '') or ''
                if not text.strip():
                    continue

                messages.append(Message(
                    role=role,
                    text=text,
                    create_time=self._parse_iso_timestamp_safe(msg.get('inserted_at')),
                    image_refs=[],
                ))
        return messages
