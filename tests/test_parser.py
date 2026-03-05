import json
from pathlib import Path
from models import Message, Branch, Conversation


FIXTURE = Path(__file__).parent / 'fixtures' / 'sample_conversations.json'


def _make_export(tmp_path, conversations):
    """Helper: write conversations.json to a temp folder."""
    (tmp_path / 'conversations.json').write_text(
        json.dumps(conversations), encoding='utf-8'
    )
    return tmp_path


def test_message_creation():
    msg = Message(role='user', text='hello')
    assert msg.role == 'user'
    assert msg.text == 'hello'
    assert msg.image_refs == []


def test_conversation_creation():
    msg = Message(role='user', text='hi')
    branch = Branch(messages=[msg], branch_index=1)
    conv = Conversation(
        id='abc',
        title='Test',
        create_time=1700000000.0,
        update_time=1700000100.0,
        model_slug='gpt-4o',
        branches=[branch],
    )
    assert conv.id == 'abc'
    assert len(conv.branches) == 1
    assert conv.branches[0].branch_index == 1


from conversation_parser import ConversationParser


def test_trace_to_root_simple(tmp_path):
    mapping = {
        'a': {'id': 'a', 'parent': None, 'children': ['b'], 'message': None},
        'b': {'id': 'b', 'parent': 'a', 'children': ['c'], 'message': None},
        'c': {'id': 'c', 'parent': 'b', 'children': [], 'message': None},
    }
    parser = ConversationParser(tmp_path)
    path = parser._trace_to_root(mapping, 'c')
    assert path == ['a', 'b', 'c']


def test_find_leaf_nodes(tmp_path):
    mapping = {
        'a': {'id': 'a', 'parent': None, 'children': ['b', 'c'], 'message': None},
        'b': {'id': 'b', 'parent': 'a', 'children': [], 'message': None},
        'c': {'id': 'c', 'parent': 'a', 'children': [], 'message': None},
    }
    parser = ConversationParser(tmp_path)
    leaves = parser._find_leaf_ids(mapping)
    assert set(leaves) == {'b', 'c'}


def test_parse_fixture_conversation_count(tmp_path):
    with open(FIXTURE) as f:
        data = json.load(f)
    export = _make_export(tmp_path, data)
    parser = ConversationParser(export)
    convs = parser.parse()
    # conv-003 has no user/assistant messages so should be skipped
    assert len(convs) == 2


def test_parse_fixture_branch_count(tmp_path):
    with open(FIXTURE) as f:
        data = json.load(f)
    export = _make_export(tmp_path, data)
    parser = ConversationParser(export)
    convs = parser.parse()
    conv = next(c for c in convs if c.id == 'conv-001')
    # Two leaves: node-d (main) and node-e (alternate)
    assert len(conv.branches) == 2


def test_main_branch_is_index_1(tmp_path):
    with open(FIXTURE) as f:
        data = json.load(f)
    export = _make_export(tmp_path, data)
    parser = ConversationParser(export)
    convs = parser.parse()
    conv = next(c for c in convs if c.id == 'conv-001')
    main = conv.branches[0]
    assert main.branch_index == 1
    # Main branch ends at node-d (the current_node), so has 3 messages: user, assistant, user
    assert len(main.messages) == 3
