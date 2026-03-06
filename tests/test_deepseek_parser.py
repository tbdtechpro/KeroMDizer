import json
import shutil
from pathlib import Path
import pytest
from deepseek_parser import DeepSeekParser

FIXTURE = Path(__file__).parent / 'fixtures' / 'sample_deepseek_conversations.json'


def _setup(tmp_path: Path) -> list:
    shutil.copy(FIXTURE, tmp_path / 'conversations.json')
    return DeepSeekParser(tmp_path).parse()


def _find(convs, conv_id):
    return next(c for c in convs if c.id == conv_id)


def test_parse_basic_conversation(tmp_path):
    """Title, id, model extracted correctly from ds-single-001."""
    convs = _setup(tmp_path)
    conv = _find(convs, 'ds-single-001')
    assert conv.title == 'Single Branch Chat'
    assert conv.model_slug == 'deepseek-chat'


def test_iso_timestamps_parsed(tmp_path):
    """create_time and update_time on Conversation are floats (not strings)."""
    convs = _setup(tmp_path)
    conv = _find(convs, 'ds-single-001')
    assert isinstance(conv.create_time, float)
    assert isinstance(conv.update_time, float)


def test_request_response_roles(tmp_path):
    """REQUEST maps to 'user', RESPONSE maps to 'assistant'."""
    convs = _setup(tmp_path)
    conv = _find(convs, 'ds-single-001')
    branch1 = conv.branches[0]
    roles = [msg.role for msg in branch1.messages]
    assert roles == ['user', 'assistant']


def test_think_fragments_skipped(tmp_path):
    """THINK content does not appear in any message text (ds-reasoner-003)."""
    convs = _setup(tmp_path)
    conv = _find(convs, 'ds-reasoner-003')
    all_text = ' '.join(msg.text for branch in conv.branches for msg in branch.messages)
    assert 'Let me reason step by step' not in all_text


def test_search_fragments_skipped(tmp_path):
    """SEARCH node produces no messages (ds-search-004); only REQUEST and RESPONSE remain."""
    convs = _setup(tmp_path)
    conv = _find(convs, 'ds-search-004')
    branch1 = conv.branches[0]
    assert len(branch1.messages) == 2
    all_text = ' '.join(msg.text for msg in branch1.messages)
    assert 'AI news 2025' not in all_text


def test_branch_main_is_latest_timestamp(tmp_path):
    """Branch 1 is the later-timestamped leaf in ds-branched-002 (n6 path, branch B)."""
    convs = _setup(tmp_path)
    conv = _find(convs, 'ds-branched-002')
    assert len(conv.branches) == 2
    branch1 = conv.branches[0]
    all_text = ' '.join(msg.text for msg in branch1.messages)
    assert 'Branch B answer (latest)' in all_text


def test_model_extracted_from_first_response(tmp_path):
    """model_slug on Conversation equals model from first RESPONSE fragment (ds-reasoner-003)."""
    convs = _setup(tmp_path)
    conv = _find(convs, 'ds-reasoner-003')
    assert conv.model_slug == 'deepseek-reasoner'


def test_empty_node_skipped(tmp_path):
    """Null-message node in ds-null-msg-005 is skipped without raising."""
    convs = _setup(tmp_path)
    ids = [c.id for c in convs]
    assert 'ds-null-msg-005' in ids
    conv = _find(convs, 'ds-null-msg-005')
    branch1 = conv.branches[0]
    assert len(branch1.messages) == 2
