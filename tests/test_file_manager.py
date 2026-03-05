import json
from pathlib import Path
from models import Message, Branch, Conversation
from file_manager import FileManager


def _make_conv(id_, title, create_time=1700000000.0, update_time=1700000100.0, branch_count=1):
    branches = [Branch(messages=[Message(role='user', text='hi')], branch_index=i+1)
                for i in range(branch_count)]
    return Conversation(
        id=id_, title=title,
        create_time=create_time, update_time=update_time,
        model_slug='gpt-4o', branches=branches,
    )


def test_sanitize_filename_basic(tmp_path):
    fm = FileManager(tmp_path)
    assert fm.sanitize_filename('Hello World') == 'Hello_World'


def test_sanitize_filename_special_chars(tmp_path):
    fm = FileManager(tmp_path)
    result = fm.sanitize_filename('Branch · Casper: Setup/Plan?')
    assert '/' not in result
    assert ':' not in result
    assert '?' not in result
    assert '·' not in result


def test_sanitize_filename_truncates_at_80(tmp_path):
    fm = FileManager(tmp_path)
    long_title = 'A' * 100
    assert len(fm.sanitize_filename(long_title)) <= 80


def test_make_filename_single_branch(tmp_path):
    fm = FileManager(tmp_path)
    conv = _make_conv('abc', 'My Chat', branch_count=1)
    name = fm.make_filename(conv, conv.branches[0])
    assert name == '2023-11-14_My_Chat.md'


def test_make_filename_multi_branch_main(tmp_path):
    fm = FileManager(tmp_path)
    conv = _make_conv('abc', 'My Chat', branch_count=3)
    # Branch 1 (main) gets no suffix
    name = fm.make_filename(conv, conv.branches[0])
    assert name == '2023-11-14_My_Chat.md'


def test_make_filename_multi_branch_alternate(tmp_path):
    fm = FileManager(tmp_path)
    conv = _make_conv('abc', 'My Chat', branch_count=3)
    name = fm.make_filename(conv, conv.branches[1])
    assert name == '2023-11-14_My_Chat_branch-2.md'


def test_make_filename_collision_disambiguation(tmp_path):
    fm = FileManager(tmp_path)
    conv1 = _make_conv('id-aabbcc01', 'Same Title', branch_count=1)
    conv2 = _make_conv('id-xxyyzz02', 'Same Title', branch_count=1)
    name1 = fm.make_filename(conv1, conv1.branches[0])
    name2 = fm.make_filename(conv2, conv2.branches[0])
    assert name1 != name2
    assert 'id-aabb' in name2 or 'id-xxyy' in name2


def test_copy_asset_finds_dalle_image(tmp_path):
    """copy_asset should find files in dalle-generations/ subdirectory."""
    export = tmp_path / 'export'
    export.mkdir()
    dalle_dir = export / 'dalle-generations'
    dalle_dir.mkdir()
    # DALL-E file lives in dalle-generations/, not in export root
    fake_img = dalle_dir / 'file-AbCdEfGhIj-some-uuid.webp'
    fake_img.write_bytes(b'fake webp data')

    output = tmp_path / 'output'
    fm = FileManager(output)
    result = fm.copy_asset(export, 'file-AbCdEfGhIj')
    assert result == 'file-AbCdEfGhIj-some-uuid.webp'
    assert (output / 'assets' / 'file-AbCdEfGhIj-some-uuid.webp').exists()
