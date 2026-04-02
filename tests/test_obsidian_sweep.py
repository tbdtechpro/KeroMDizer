"""Integration test: obsidian post-sweep writes files from DB rows."""
import pytest
from pathlib import Path
from db import DatabaseManager
from obsidian_renderer import ObsidianRenderer


def _populate_db(db: DatabaseManager) -> None:
    db.upsert_conversation(
        conversation_id='test1',
        provider='chatgpt',
        title='Test Conversation',
        create_time='2026-01-14T00:00:00+00:00',
        update_time='2026-01-14T00:00:00+00:00',
        model_slug='gpt-4o',
        branch_count=1,
        branches=[{
            'branch_id': 'test1__branch_1',
            'branch_index': 1,
            'is_main_branch': True,
            'messages': [],
            'inferred_tags': ['python'],
            'inferred_syntax': ['python'],
            'md_filename': '2026-01-14_Test_Conversation.md',
        }],
        user_alias='Matt',
        assistant_alias='ChatGPT',
    )


def test_obsidian_sweep_writes_file(tmp_path):
    db = DatabaseManager(tmp_path / 'test.db')
    _populate_db(db)
    renderer = ObsidianRenderer()
    obsidian_dir = tmp_path / 'obsidian'

    for row in db.list_branches():
        md_filename = row.get('md_filename') or ''
        if not md_filename:
            continue
        out = obsidian_dir / md_filename
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(renderer.render(row), encoding='utf-8')

    db.close()
    out_file = obsidian_dir / '2026-01-14_Test_Conversation.md'
    assert out_file.exists()
    content = out_file.read_text(encoding='utf-8')
    assert content.startswith('---\n')
    assert 'title: "Test Conversation"' in content


def test_obsidian_sweep_skips_existing_files(tmp_path):
    db = DatabaseManager(tmp_path / 'test.db')
    _populate_db(db)
    renderer = ObsidianRenderer()
    obsidian_dir = tmp_path / 'obsidian'
    obsidian_dir.mkdir()

    # Pre-write a sentinel file
    sentinel = obsidian_dir / '2026-01-14_Test_Conversation.md'
    sentinel.write_text('SENTINEL', encoding='utf-8')

    for row in db.list_branches():
        md_filename = row.get('md_filename') or ''
        if not md_filename:
            continue
        out = obsidian_dir / md_filename
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(renderer.render(row), encoding='utf-8')

    db.close()
    assert sentinel.read_text(encoding='utf-8') == 'SENTINEL'
