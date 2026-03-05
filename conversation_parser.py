import json
from pathlib import Path
from models import Conversation, Branch, Message


class ConversationParser:
    def __init__(self, export_folder: Path):
        self.export_folder = Path(export_folder)
        self._conversations_file = self.export_folder / 'conversations.json'

    def parse(self) -> list[Conversation]:
        if not self._conversations_file.exists():
            raise FileNotFoundError(
                f"conversations.json not found in {self.export_folder}"
            )
        with open(self._conversations_file, encoding='utf-8') as f:
            data = json.load(f)

        shared_ids = self._load_shared_ids()
        conversations = []
        for raw in data:
            try:
                conv = self._parse_conversation(raw)
                if conv is not None:
                    conv.is_shared = conv.id in shared_ids
                    conversations.append(conv)
            except Exception as e:
                title = raw.get('title', 'unknown')
                print(f"Warning: skipping conversation '{title}': {e}")
        return conversations

    def _load_shared_ids(self) -> set[str]:
        """Return set of conversation IDs from shared_conversations.json, or empty set if absent."""
        path = self.export_folder / 'shared_conversations.json'
        if not path.exists():
            return set()
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        return {entry['conversation_id'] for entry in data if 'conversation_id' in entry}

    def _parse_conversation(self, raw: dict) -> Conversation | None:
        mapping = raw.get('mapping', {})
        current_node = raw.get('current_node')

        leaf_ids = self._find_leaf_ids(mapping)
        if not leaf_ids:
            return None

        # Trace main branch first (contains current_node)
        main_path = self._trace_to_root(mapping, current_node) if current_node else []
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

            is_main = current_node in path
            branches.append((is_main, path_key, messages))

        if not branches:
            return None

        # Sort: main branch first
        branches.sort(key=lambda x: (0 if x[0] else 1))
        final_branches = [
            Branch(messages=msgs, branch_index=i + 1)
            for i, (_, _, msgs) in enumerate(branches)
        ]

        conv_id = raw.get('id') or raw.get('conversation_id', '')
        audio_dir = self.export_folder / conv_id / 'audio'
        audio_count = len(list(audio_dir.glob('*.wav'))) if audio_dir.is_dir() else 0

        return Conversation(
            id=conv_id,
            title=raw.get('title', 'Untitled'),
            create_time=raw.get('create_time'),
            update_time=raw.get('update_time'),
            model_slug=raw.get('default_model_slug'),
            branches=final_branches,
            audio_count=audio_count,
        )

    def _find_leaf_ids(self, mapping: dict) -> list[str]:
        return [nid for nid, node in mapping.items() if not node.get('children')]

    def _trace_to_root(self, mapping: dict, start_id: str) -> list[str]:
        path = []
        node_id = start_id
        seen = set()
        while node_id and node_id not in seen:
            seen.add(node_id)
            path.append(node_id)
            node_id = mapping.get(node_id, {}).get('parent')
        path.reverse()
        return path

    def _extract_messages(self, mapping: dict, path_ids: list[str]) -> list[Message]:
        messages = []
        for nid in path_ids:
            node = mapping.get(nid, {})
            msg = node.get('message')
            if not msg:
                continue
            role = msg.get('author', {}).get('role')
            if role not in ('user', 'assistant'):
                continue
            content = msg.get('content', {})
            if not isinstance(content, dict):
                continue
            content_type = content.get('content_type')
            if content_type not in ('text', 'multimodal_text'):
                continue
            parts = content.get('parts') or []
            text = self._parts_to_text(parts)
            image_refs = self._extract_image_refs(parts)
            if not text.strip() and not image_refs:
                continue
            messages.append(Message(
                role=role,
                text=text,
                create_time=msg.get('create_time'),
                image_refs=image_refs,
            ))
        return messages

    def _parts_to_text(self, parts: list) -> str:
        segments = []
        for part in parts:
            if isinstance(part, str):
                segments.append(part)
            elif isinstance(part, dict):
                if part.get('content_type') == 'image_asset_pointer':
                    file_id = self._strip_asset_uri(part.get('asset_pointer', ''))
                    if file_id:
                        segments.append(f'![image](assets/{file_id})')
        return '\n\n'.join(segments)

    def _extract_image_refs(self, parts: list) -> list[str]:
        refs = []
        for part in parts:
            if isinstance(part, dict) and part.get('content_type') == 'image_asset_pointer':
                file_id = self._strip_asset_uri(part.get('asset_pointer', ''))
                if file_id:
                    refs.append(file_id)
        return refs

    def _strip_asset_uri(self, uri: str) -> str:
        """Strip sediment:// or file-service:// URI prefix, returning bare file ID.

        If uri has no recognised prefix it is returned unchanged — bare file IDs
        (no scheme) are valid input.
        """
        for prefix in ('sediment://', 'file-service://'):
            if uri.startswith(prefix):
                return uri[len(prefix):]
        return uri
