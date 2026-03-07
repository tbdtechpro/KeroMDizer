import json
from pathlib import Path
from db import DatabaseManager


def export_jsonl(db: DatabaseManager, output_path: Path, branch_mode: str = 'all') -> None:
    """Write all branches from DB to a JSONL file, one record per line."""
    main_only = branch_mode == 'main'
    branches = db.list_branches(main_only=main_only)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for b in branches:
            record = {
                'schema_version': '1',
                'id': b['branch_id'],
                'conversation_id': b['conversation_id'],
                'branch_index': b['branch_index'],
                'is_main_branch': b['is_main_branch'],
                'provider': b['provider'],
                'title': b['title'],
                'create_time': b['conv_create_time'],
                'model_slug': b['model_slug'],
                'tags': b['tags'],
                'project': b['project'],
                'category': b['category'],
                'syntax': b['syntax'],
                'inferred_tags': b['inferred_tags'],
                'inferred_syntax': b['inferred_syntax'],
                'messages': b['messages'],
            }
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
