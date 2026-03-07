import json
import pytest
from pathlib import Path
from db import DatabaseManager
from jsonl_exporter import export_jsonl


@pytest.fixture
def populated_db(tmp_path):
    db = DatabaseManager(tmp_path / 'test.db')
    for i in range(3):
        db.upsert_conversation(
            conversation_id=f'conv-{i}',
            provider='chatgpt',
            title=f'Conversation {i}',
            create_time='2026-01-01T00:00:00+00:00',
            update_time='2026-01-01T00:00:00+00:00',
            model_slug='gpt-4o',
            branch_count=1,
            branches=[{
                'branch_id': f'conv-{i}__branch_1',
                'branch_index': 1,
                'is_main_branch': True,
                'messages': [{'role': 'user', 'timestamp': None,
                              'content': [{'type': 'prose', 'text': 'Hello'}]}],
                'inferred_tags': ['test'],
                'inferred_syntax': [],
            }],
        )
    return db


def test_export_jsonl_creates_file(populated_db, tmp_path):
    out = tmp_path / 'export.jsonl'
    export_jsonl(populated_db, out, branch_mode='all')
    assert out.exists()


def test_export_jsonl_line_count(populated_db, tmp_path):
    out = tmp_path / 'export.jsonl'
    export_jsonl(populated_db, out, branch_mode='all')
    lines = out.read_text().strip().splitlines()
    assert len(lines) == 3


def test_export_jsonl_valid_json_per_line(populated_db, tmp_path):
    out = tmp_path / 'export.jsonl'
    export_jsonl(populated_db, out, branch_mode='all')
    for line in out.read_text().strip().splitlines():
        obj = json.loads(line)
        assert 'id' in obj
        assert 'conversation_id' in obj
        assert 'provider' in obj
        assert 'messages' in obj
        assert 'inferred_tags' in obj
        assert 'tags' in obj
        assert 'schema_version' in obj


def test_export_jsonl_schema_version(populated_db, tmp_path):
    out = tmp_path / 'export.jsonl'
    export_jsonl(populated_db, out, branch_mode='all')
    obj = json.loads(out.read_text().splitlines()[0])
    assert obj['schema_version'] == '1'


def test_export_jsonl_main_only(tmp_path):
    db = DatabaseManager(tmp_path / 'test.db')
    db.upsert_conversation(
        conversation_id='conv-b',
        provider='chatgpt',
        title='Branched',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-01T00:00:00+00:00',
        model_slug=None,
        branch_count=2,
        branches=[
            {'branch_id': 'conv-b__branch_1', 'branch_index': 1, 'is_main_branch': True,
             'messages': [], 'inferred_tags': [], 'inferred_syntax': []},
            {'branch_id': 'conv-b__branch_2', 'branch_index': 2, 'is_main_branch': False,
             'messages': [], 'inferred_tags': [], 'inferred_syntax': []},
        ],
    )
    out = tmp_path / 'export.jsonl'
    export_jsonl(db, out, branch_mode='main')
    lines = out.read_text().strip().splitlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj['is_main_branch'] is True
