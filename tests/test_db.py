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


def test_tags_preserved_on_re_import(db):
    """User-applied tags must survive a re-import of the same conversation."""
    db.upsert_conversation(
        conversation_id='conv-preserve',
        provider='chatgpt',
        title='Preserve',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-01T00:00:00+00:00',
        model_slug=None,
        branch_count=1,
        branches=[{
            'branch_id': 'conv-preserve__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': [],
            'inferred_syntax': [],
        }],
    )
    db.update_branch_tags('conv-preserve__branch_1', ['important', 'keep'], 'MyProject', 'research', [])

    # Re-import with newer update_time (simulates updated conversation)
    db.upsert_conversation(
        conversation_id='conv-preserve',
        provider='chatgpt',
        title='Preserve Updated',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-14T00:00:00+00:00',
        model_slug='gpt-4o',
        branch_count=1,
        branches=[{
            'branch_id': 'conv-preserve__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [{'role': 'user', 'timestamp': None, 'content': []}],
            'inferred_tags': ['new-inferred'],
            'inferred_syntax': [],
        }],
    )

    row = db.get_branch('conv-preserve__branch_1')
    assert row['tags'] == ['important', 'keep']    # user tags preserved
    assert row['project'] == 'MyProject'           # user project preserved
    assert row['category'] == 'research'           # user category preserved
    assert row['inferred_tags'] == ['new-inferred'] # inferred tags updated


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


def test_search_by_title(tmp_path):
    db = DatabaseManager(tmp_path / 'test.db')
    db.upsert_conversation(
        conversation_id='conv-rpi',
        provider='chatgpt',
        title='Raspberry Pi setup',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-01T00:00:00+00:00',
        model_slug=None,
        branch_count=1,
        branches=[{
            'branch_id': 'conv-rpi__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': [],
            'inferred_syntax': [],
        }],
    )
    results = db.search_branches(query='raspberry')
    assert len(results) == 1
    assert results[0]['title'] == 'Raspberry Pi setup'


def test_search_by_message_content(tmp_path):
    db = DatabaseManager(tmp_path / 'test.db')
    db.upsert_conversation(
        conversation_id='conv-k8s',
        provider='chatgpt',
        title='Cluster config',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-01T00:00:00+00:00',
        model_slug=None,
        branch_count=1,
        branches=[{
            'branch_id': 'conv-k8s__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [{'role': 'user', 'content': [{'type': 'prose', 'text': 'kubernetes setup'}], 'timestamp': None}],
            'inferred_tags': [],
            'inferred_syntax': [],
        }],
    )
    results = db.search_branches(query='kubernetes')
    assert len(results) == 1


def test_search_no_match(tmp_path):
    db = DatabaseManager(tmp_path / 'test.db')
    results = db.search_branches(query='zzznomatch')
    assert results == []


def test_search_provider_filter(tmp_path):
    db = DatabaseManager(tmp_path / 'test.db')
    for i, prov in enumerate(['chatgpt', 'deepseek']):
        db.upsert_conversation(
            conversation_id=f'conv-{prov}',
            provider=prov,
            title=f'Conv {prov}',
            create_time='2026-01-01T00:00:00+00:00',
            update_time='2026-01-01T00:00:00+00:00',
            model_slug=None,
            branch_count=1,
            branches=[{
                'branch_id': f'conv-{prov}__branch_1',
                'branch_index': 1,
                'is_main_branch': True,
                'messages': [],
                'inferred_tags': [],
                'inferred_syntax': [],
            }],
        )
    results = db.search_branches(provider='chatgpt')
    assert len(results) == 1
    assert results[0]['provider'] == 'chatgpt'


def test_md_filename_preserved_on_reimport(tmp_path):
    db = DatabaseManager(tmp_path / 'test.db')
    db.upsert_conversation(
        conversation_id='conv-mdf',
        provider='chatgpt',
        title='Test',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-01T00:00:00+00:00',
        model_slug=None,
        branch_count=1,
        branches=[{
            'branch_id': 'conv-mdf__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': [],
            'inferred_syntax': [],
            'md_filename': '2026-01-01_Test.md',
        }],
    )
    # Re-import with md_filename=None (no new filename provided)
    db.upsert_conversation(
        conversation_id='conv-mdf',
        provider='chatgpt',
        title='Test',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-02T00:00:00+00:00',
        model_slug=None,
        branch_count=1,
        branches=[{
            'branch_id': 'conv-mdf__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': [],
            'inferred_syntax': [],
            # no md_filename key
        }],
    )
    row = db.get_branch('conv-mdf__branch_1')
    assert row['md_filename'] == '2026-01-01_Test.md'


def test_md_filename_updated_on_reimport(tmp_path):
    db = DatabaseManager(tmp_path / 'test.db')
    db.upsert_conversation(
        conversation_id='conv-mdf2',
        provider='chatgpt',
        title='Test',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-01T00:00:00+00:00',
        model_slug=None,
        branch_count=1,
        branches=[{
            'branch_id': 'conv-mdf2__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': [],
            'inferred_syntax': [],
            'md_filename': 'old.md',
        }],
    )
    db.upsert_conversation(
        conversation_id='conv-mdf2',
        provider='chatgpt',
        title='Test',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-02T00:00:00+00:00',
        model_slug=None,
        branch_count=1,
        branches=[{
            'branch_id': 'conv-mdf2__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': [],
            'inferred_syntax': [],
            'md_filename': 'new.md',
        }],
    )
    row = db.get_branch('conv-mdf2__branch_1')
    assert row['md_filename'] == 'new.md'


def test_md_filename_stored_after_upsert(tmp_path):
    db = DatabaseManager(tmp_path / 'test.db')
    db.upsert_conversation(
        conversation_id='conv-fn',
        provider='chatgpt',
        title='Filename Test',
        create_time='2026-01-01T00:00:00+00:00',
        update_time='2026-01-01T00:00:00+00:00',
        model_slug=None,
        branch_count=1,
        branches=[{
            'branch_id': 'conv-fn__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': [],
            'inferred_syntax': [],
            'md_filename': '2026-01-01_Filename_Test.md',
        }],
    )
    row = db.get_branch('conv-fn__branch_1')
    assert row['md_filename'] == '2026-01-01_Filename_Test.md'


def test_backfill_md_filenames_single_branch(tmp_path):
    """backfill_md_filenames matches a .md file to a branch with NULL md_filename."""
    db = DatabaseManager(tmp_path / 'test.db')
    db.upsert_conversation(
        conversation_id='conv-bf',
        provider='chatgpt',
        title='Backfill Test',
        create_time='2026-02-01T00:00:00+00:00',
        update_time='2026-02-01T00:00:00+00:00',
        model_slug='gpt-4o',
        branch_count=1,
        branches=[{
            'branch_id': 'conv-bf__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': [],
            'inferred_syntax': [],
        }],
    )
    # Write a .md file matching the renderer output format
    md_dir = tmp_path / 'output'
    md_dir.mkdir()
    md_file = md_dir / '2026-02-01_Backfill_Test.md'
    md_file.write_text('# Backfill Test\n\n_2026-02-01  ·  gpt-4o_\n\n---\n')

    count = db.backfill_md_filenames(md_dir)
    assert count == 1
    row = db.get_branch('conv-bf__branch_1')
    assert row['md_filename'] == '2026-02-01_Backfill_Test.md'


def test_backfill_md_filenames_multi_branch(tmp_path):
    """backfill correctly handles Branch N of M subheading."""
    db = DatabaseManager(tmp_path / 'test.db')
    for idx in (1, 2):
        db.upsert_conversation(
            conversation_id='conv-mb',
            provider='chatgpt',
            title='Multi Branch',
            create_time='2026-03-01T00:00:00+00:00',
            update_time='2026-03-01T00:00:00+00:00',
            model_slug=None,
            branch_count=2,
            branches=[{
                'branch_id': f'conv-mb__branch_{idx}',
                'branch_index': idx,
                'is_main_branch': idx == 1,
                'messages': [],
                'inferred_tags': [],
                'inferred_syntax': [],
            }],
        )
    md_dir = tmp_path / 'output'
    md_dir.mkdir()
    (md_dir / '2026-03-01_Multi_Branch.md').write_text(
        '# Multi Branch\n\n_2026-03-01  ·  Branch 1 of 2_\n\n---\n'
    )
    (md_dir / '2026-03-01_Multi_Branch_branch-2.md').write_text(
        '# Multi Branch\n\n_2026-03-01  ·  Branch 2 of 2_\n\n---\n'
    )
    count = db.backfill_md_filenames(md_dir)
    assert count == 2
    assert db.get_branch('conv-mb__branch_1')['md_filename'] == '2026-03-01_Multi_Branch.md'
    assert db.get_branch('conv-mb__branch_2')['md_filename'] == '2026-03-01_Multi_Branch_branch-2.md'


def test_backfill_skips_already_set(tmp_path):
    """backfill does not overwrite an existing md_filename."""
    db = DatabaseManager(tmp_path / 'test.db')
    db.upsert_conversation(
        conversation_id='conv-skip',
        provider='chatgpt',
        title='Skip Test',
        create_time='2026-04-01T00:00:00+00:00',
        update_time='2026-04-01T00:00:00+00:00',
        model_slug=None,
        branch_count=1,
        branches=[{
            'branch_id': 'conv-skip__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': [],
            'inferred_syntax': [],
            'md_filename': 'original.md',
        }],
    )
    md_dir = tmp_path / 'output'
    md_dir.mkdir()
    (md_dir / '2026-04-01_Skip_Test.md').write_text(
        '# Skip Test\n\n_2026-04-01_\n\n---\n'
    )
    count = db.backfill_md_filenames(md_dir)
    assert count == 0
    assert db.get_branch('conv-skip__branch_1')['md_filename'] == 'original.md'
