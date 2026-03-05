import json
from pathlib import Path

from conversation_parser import ConversationParser
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


def test_extract_messages_filters_system_and_tool(tmp_path):
    mapping = {
        'a': {
            'id': 'a', 'parent': None, 'children': ['b'],
            'message': {
                'author': {'role': 'system'},
                'content': {'content_type': 'text', 'parts': ['system prompt']},
                'create_time': None, 'metadata': {}
            }
        },
        'b': {
            'id': 'b', 'parent': 'a', 'children': [],
            'message': {
                'author': {'role': 'user'},
                'content': {'content_type': 'text', 'parts': ['Hello']},
                'create_time': 1700000010.0, 'metadata': {}
            }
        },
    }
    parser = ConversationParser(tmp_path)
    messages = parser._extract_messages(mapping, ['a', 'b'])
    assert len(messages) == 1
    assert messages[0].role == 'user'
    assert messages[0].text == 'Hello'


def test_extract_messages_filters_non_text_content(tmp_path):
    mapping = {
        'a': {
            'id': 'a', 'parent': None, 'children': ['b'],
            'message': {
                'author': {'role': 'assistant'},
                'content': {'content_type': 'thoughts', 'thoughts': [{'summary': 'thinking', 'content': 'I think'}]},
                'create_time': None, 'metadata': {}
            }
        },
        'b': {
            'id': 'b', 'parent': 'a', 'children': [],
            'message': {
                'author': {'role': 'assistant'},
                'content': {'content_type': 'text', 'parts': ['Here is the answer.']},
                'create_time': 1700000020.0, 'metadata': {}
            }
        },
    }
    parser = ConversationParser(tmp_path)
    messages = parser._extract_messages(mapping, ['a', 'b'])
    assert len(messages) == 1
    assert messages[0].text == 'Here is the answer.'


def test_extract_messages_handles_multimodal(tmp_path):
    mapping = {
        'a': {
            'id': 'a', 'parent': None, 'children': [],
            'message': {
                'author': {'role': 'user'},
                'content': {
                    'content_type': 'multimodal_text',
                    'parts': [
                        'What is this?',
                        {
                            'content_type': 'image_asset_pointer',
                            'asset_pointer': 'sediment://file_abc123',
                            'size_bytes': 100,
                            'width': 100,
                            'height': 100,
                        }
                    ]
                },
                'create_time': 1700000010.0, 'metadata': {}
            }
        },
    }
    parser = ConversationParser(tmp_path)
    messages = parser._extract_messages(mapping, ['a'])
    assert len(messages) == 1
    assert 'What is this?' in messages[0].text
    assert 'file_abc123' in messages[0].text
    assert messages[0].image_refs == ['file_abc123']


def test_parse_fixture_message_content(tmp_path):
    with open(FIXTURE) as f:
        data = json.load(f)
    export = _make_export(tmp_path, data)
    parser = ConversationParser(export)
    convs = parser.parse()
    conv = next(c for c in convs if c.id == 'conv-001')
    main = conv.branches[0]
    # Main branch: user -> assistant -> user
    assert main.messages[0].role == 'user'
    assert 'hello world' in main.messages[0].text.lower()
    assert main.messages[1].role == 'assistant'
    assert '```python' in main.messages[1].text
    assert main.messages[2].role == 'user'


def test_parse_fixture_image_refs(tmp_path):
    with open(FIXTURE) as f:
        data = json.load(f)
    export = _make_export(tmp_path, data)
    parser = ConversationParser(export)
    convs = parser.parse()
    conv = next(c for c in convs if c.id == 'conv-002')
    user_msg = conv.branches[0].messages[0]
    assert 'file_abc123' in user_msg.image_refs
    assert 'assets/file_abc123' in user_msg.text


def test_extract_messages_handles_dalle_image(tmp_path):
    """file-service:// asset pointers (DALL-E) should have the URI prefix stripped.

    The bare file ID ends up in image_refs; copy_asset resolves it from
    dalle-generations/ (handled separately in file_manager.py).
    """
    mapping = {
        'a': {
            'id': 'a', 'parent': None, 'children': [],
            'message': {
                'author': {'role': 'assistant'},
                'content': {
                    'content_type': 'multimodal_text',
                    'parts': [
                        'Here is your image:',
                        {
                            'content_type': 'image_asset_pointer',
                            'asset_pointer': 'file-service://file-AbCdEfGhIj',
                            'size_bytes': 100,
                            'width': 512,
                            'height': 512,
                        }
                    ]
                },
                'create_time': 1700000010.0, 'metadata': {}
            }
        },
    }
    parser = ConversationParser(tmp_path)
    messages = parser._extract_messages(mapping, ['a'])
    assert len(messages) == 1
    assert 'file-AbCdEfGhIj' in messages[0].text
    assert '![image](assets/file-AbCdEfGhIj)' in messages[0].text
    assert messages[0].image_refs == ['file-AbCdEfGhIj']


def test_parse_marks_shared_conversation(tmp_path):
    """Conversations listed in shared_conversations.json get is_shared=True."""
    conv_data = [{
        'id': 'conv-shared-1',
        'title': 'Shared Chat',
        'mapping': {
            'a': {'id': 'a', 'parent': None, 'children': ['b'], 'message': None},
            'b': {
                'id': 'b', 'parent': 'a', 'children': [],
                'message': {
                    'author': {'role': 'user'},
                    'content': {'content_type': 'text', 'parts': ['hello']},
                    'create_time': None, 'metadata': {}
                }
            },
        },
        'current_node': 'b',
        'create_time': 1700000000.0,
        'update_time': 1700000100.0,
        'default_model_slug': 'gpt-4o',
    }]
    export = _make_export(tmp_path, conv_data)
    (export / 'shared_conversations.json').write_text(
        json.dumps([{'conversation_id': 'conv-shared-1', 'id': 'share-abc', 'title': 'Shared Chat', 'is_anonymous': True}]),
        encoding='utf-8',
    )
    parser = ConversationParser(export)
    convs = parser.parse()
    assert convs[0].is_shared is True


def test_parse_not_shared_when_absent(tmp_path):
    """Conversations not in shared_conversations.json get is_shared=False."""
    conv_data = [{
        'id': 'conv-private-1',
        'title': 'Private Chat',
        'mapping': {
            'a': {'id': 'a', 'parent': None, 'children': ['b'], 'message': None},
            'b': {
                'id': 'b', 'parent': 'a', 'children': [],
                'message': {
                    'author': {'role': 'user'},
                    'content': {'content_type': 'text', 'parts': ['hello']},
                    'create_time': None, 'metadata': {}
                }
            },
        },
        'current_node': 'b',
        'create_time': 1700000000.0,
        'update_time': 1700000100.0,
        'default_model_slug': 'gpt-4o',
    }]
    export = _make_export(tmp_path, conv_data)
    # No shared_conversations.json — should work fine, is_shared stays False
    parser = ConversationParser(export)
    convs = parser.parse()
    assert convs[0].is_shared is False


def test_parse_shared_ids_handles_malformed_json(tmp_path, capsys):
    """Malformed shared_conversations.json is warned and gracefully skipped."""
    conv_data = [{
        'id': 'conv-001',
        'title': 'Test',
        'mapping': {
            'a': {'id': 'a', 'parent': None, 'children': ['b'], 'message': None},
            'b': {
                'id': 'b', 'parent': 'a', 'children': [],
                'message': {
                    'author': {'role': 'user'},
                    'content': {'content_type': 'text', 'parts': ['hi']},
                    'create_time': None, 'metadata': {}
                }
            },
        },
        'current_node': 'b',
        'create_time': 1700000000.0,
        'update_time': 1700000100.0,
        'default_model_slug': 'gpt-4o',
    }]
    export = _make_export(tmp_path, conv_data)
    (export / 'shared_conversations.json').write_text('not valid json', encoding='utf-8')
    parser = ConversationParser(export)
    convs = parser.parse()
    assert len(convs) == 1
    assert convs[0].is_shared is False
    captured = capsys.readouterr()
    assert 'Warning' in captured.err
    assert 'shared_conversations.json' in captured.err


def test_parse_not_shared_when_not_in_file(tmp_path):
    """Conversation not listed in shared_conversations.json gets is_shared=False."""
    conv_data = [{
        'id': 'conv-private-2',
        'title': 'Private Chat 2',
        'mapping': {
            'a': {'id': 'a', 'parent': None, 'children': ['b'], 'message': None},
            'b': {
                'id': 'b', 'parent': 'a', 'children': [],
                'message': {
                    'author': {'role': 'user'},
                    'content': {'content_type': 'text', 'parts': ['hello']},
                    'create_time': None, 'metadata': {}
                }
            },
        },
        'current_node': 'b',
        'create_time': 1700000000.0,
        'update_time': 1700000100.0,
        'default_model_slug': 'gpt-4o',
    }]
    export = _make_export(tmp_path, conv_data)
    # shared_conversations.json exists but conv-private-2 is NOT listed
    (export / 'shared_conversations.json').write_text(
        json.dumps([{'conversation_id': 'conv-other-999', 'id': 'share-xyz', 'title': 'Other', 'is_anonymous': False}]),
        encoding='utf-8',
    )
    parser = ConversationParser(export)
    convs = parser.parse()
    assert convs[0].is_shared is False


def test_parse_counts_audio_recordings(tmp_path):
    """Conversations with an audio/ subfolder get audio_count set."""
    conv_id = 'conv-voice-1'
    conv_data = [{
        'id': conv_id,
        'title': 'Voice Chat',
        'mapping': {
            'a': {'id': 'a', 'parent': None, 'children': ['b'], 'message': None},
            'b': {
                'id': 'b', 'parent': 'a', 'children': [],
                'message': {
                    'author': {'role': 'user'},
                    'content': {'content_type': 'text', 'parts': ['hi']},
                    'create_time': None, 'metadata': {}
                }
            },
        },
        'current_node': 'b',
        'create_time': 1700000000.0,
        'update_time': 1700000100.0,
        'default_model_slug': 'gpt-4o',
    }]
    export = _make_export(tmp_path, conv_data)
    audio_dir = export / conv_id / 'audio'
    audio_dir.mkdir(parents=True)
    (audio_dir / 'recording1.wav').write_bytes(b'')
    (audio_dir / 'recording2.wav').write_bytes(b'')
    parser = ConversationParser(export)
    convs = parser.parse()
    assert convs[0].audio_count == 2
