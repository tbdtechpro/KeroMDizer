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

        conversations = []
        for raw in data:
            try:
                conv = self._parse_conversation(raw)
                if conv is not None:
                    conversations.append(conv)
            except Exception as e:
                title = raw.get('title', 'unknown')
                print(f"Warning: skipping conversation '{title}': {e}")
        return conversations

    def _parse_conversation(self, raw: dict) -> Conversation | None:
        mapping = raw.get('mapping', {})
        current_node = raw.get('current_node')

        leaf_ids = self._find_leaf_ids(mapping)
        if not leaf_ids:
            return None

        # Trace main branch first (contains current_node)
        main_path = self._trace_to_root(mapping, current_node) if current_node else []
        main_path_set = set(main_path)

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

            is_main = bool(main_path_set & set(path)) and (
                current_node in path or leaf_id == current_node
            )
            branches.append((is_main, path_key, messages))

        if not branches:
            return None

        # Sort: main branch first
        branches.sort(key=lambda x: (0 if x[0] else 1))
        final_branches = [
            Branch(messages=msgs, branch_index=i + 1)
            for i, (_, _, msgs) in enumerate(branches)
        ]

        return Conversation(
            id=raw.get('id') or raw.get('conversation_id', ''),
            title=raw.get('title', 'Untitled'),
            create_time=raw.get('create_time'),
            update_time=raw.get('update_time'),
            model_slug=raw.get('default_model_slug'),
            branches=final_branches,
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
        # Stub — implemented in Task 4
        return []
