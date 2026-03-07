import json
import pytest
from pathlib import Path
from db import DatabaseManager


@pytest.fixture
def db(tmp_path):
    return DatabaseManager(tmp_path / 'test.db')


def test_db_creates_schema(db):
    tables = db._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {row[0] for row in tables}
    assert 'conversations' in names
    assert 'branches' in names


def test_needs_update_true_when_not_in_db(db):
    assert db.needs_update('conv-abc', '2026-01-14T00:00:00+00:00') is True


def test_upsert_and_needs_update_false(db):
    db.upsert_conversation(
        conversation_id='conv-1',
        provider='chatgpt',
        title='Test',
        create_time='2026-01-14T00:00:00+00:00',
        update_time='2026-01-14T00:00:00+00:00',
        model_slug='gpt-4o',
        branch_count=1,
        branches=[{
            'branch_id': 'conv-1__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': ['python'],
            'inferred_syntax': ['python'],
        }],
    )
    assert db.needs_update('conv-1', '2026-01-14T00:00:00+00:00') is False


def test_needs_update_true_when_newer(db):
    db.upsert_conversation(
        conversation_id='conv-2',
        provider='chatgpt',
        title='Old',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-01T00:00:00+00:00',
        model_slug=None,
        branch_count=1,
        branches=[{
            'branch_id': 'conv-2__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': [],
            'inferred_syntax': [],
        }],
    )
    assert db.needs_update('conv-2', '2026-01-14T00:00:00+00:00') is True


def test_list_branches_returns_all(db):
    for i in range(3):
        db.upsert_conversation(
            conversation_id=f'conv-{i}',
            provider='chatgpt',
            title=f'Conv {i}',
            create_time='2026-01-01T00:00:00+00:00',
            update_time='2026-01-01T00:00:00+00:00',
            model_slug=None,
            branch_count=1,
            branches=[{
                'branch_id': f'conv-{i}__branch_1',
                'branch_index': 1,
                'is_main_branch': True,
                'messages': [],
                'inferred_tags': [],
                'inferred_syntax': [],
            }],
        )
    rows = db.list_branches()
    assert len(rows) == 3


def test_list_branches_main_only(db):
    db.upsert_conversation(
        conversation_id='conv-br',
        provider='chatgpt',
        title='Branched',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-01T00:00:00+00:00',
        model_slug=None,
        branch_count=2,
        branches=[
            {'branch_id': 'conv-br__branch_1', 'branch_index': 1, 'is_main_branch': True,
             'messages': [], 'inferred_tags': [], 'inferred_syntax': []},
            {'branch_id': 'conv-br__branch_2', 'branch_index': 2, 'is_main_branch': False,
             'messages': [], 'inferred_tags': [], 'inferred_syntax': []},
        ],
    )
    all_rows = db.list_branches()
    main_rows = db.list_branches(main_only=True)
    assert len(all_rows) == 2
    assert len(main_rows) == 1
    assert main_rows[0]['branch_index'] == 1


def test_update_branch_tags(db):
    db.upsert_conversation(
        conversation_id='conv-tag',
        provider='deepseek',
        title='Tagged',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-01T00:00:00+00:00',
        model_slug=None,
        branch_count=1,
        branches=[{
            'branch_id': 'conv-tag__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': [],
            'inferred_syntax': [],
        }],
    )
    db.update_branch_tags(
        branch_id='conv-tag__branch_1',
        tags=['python', 'async'],
        project='MyProject',
        category='debugging',
        syntax=['python'],
    )
    row = db.get_branch('conv-tag__branch_1')
    assert row['tags'] == ['python', 'async']
    assert row['project'] == 'MyProject'
    assert row['category'] == 'debugging'
    assert row['syntax'] == ['python']


def test_get_all_tags_for_autocomplete(db):
    db.upsert_conversation(
        conversation_id='conv-ac',
        provider='chatgpt',
        title='AC',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-01T00:00:00+00:00',
        model_slug=None,
        branch_count=1,
        branches=[{
            'branch_id': 'conv-ac__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': [],
            'inferred_syntax': [],
        }],
    )
    db.update_branch_tags('conv-ac__branch_1', ['alpha', 'beta'], None, None, [])
    tags = db.get_all_tags()
    assert 'alpha' in tags
    assert 'beta' in tags


def test_upsert_overwrites_existing(db):
    for update_time in ['2026-01-01T00:00:00+00:00', '2026-01-14T00:00:00+00:00']:
        db.upsert_conversation(
            conversation_id='conv-ow',
            provider='chatgpt',
            title='Updated Title',
            create_time='2026-01-01T00:00:00+00:00',
            update_time=update_time,
            model_slug='gpt-4o',
            branch_count=1,
            branches=[{
                'branch_id': 'conv-ow__branch_1',
                'branch_index': 1,
                'is_main_branch': True,
                'messages': [],
                'inferred_tags': [],
                'inferred_syntax': [],
            }],
        )
    rows = db.list_branches()
    assert len(rows) == 1  # not duplicated
