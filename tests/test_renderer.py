from datetime import timezone
from models import Message, Branch, Conversation
from renderer import MarkdownRenderer


def _make_conv(branches, model='gpt-4o', create_time=1700000000.0, update_time=1700000100.0):
    return Conversation(
        id='test-id-001',
        title='My Test Chat',
        create_time=create_time,
        update_time=update_time,
        model_slug=model,
        branches=branches,
    )


def _make_branch(messages, index=1):
    return Branch(messages=messages, branch_index=index)


def test_render_contains_title():
    conv = _make_conv([_make_branch([Message(role='user', text='hi')])])
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '# My Test Chat' in md


def test_render_metadata_table_single_branch():
    conv = _make_conv([_make_branch([Message(role='user', text='hi')])])
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '| Date | 2023-11-14 |' in md
    assert '| Model | gpt-4o |' in md
    assert '| Conversation ID | test-id-001 |' in md
    # No Branch row for single-branch conversations
    assert '| Branch |' not in md


def test_render_metadata_table_multi_branch():
    branch1 = _make_branch([Message(role='user', text='hi')], index=1)
    branch2 = _make_branch([Message(role='assistant', text='hello')], index=2)
    conv = _make_conv([branch1, branch2])
    r = MarkdownRenderer()
    md = r.render(conv, branch1)
    assert '| Branch | 1 of 2 |' in md


def test_render_user_message():
    msg = Message(role='user', text='How do I sort a list?')
    conv = _make_conv([_make_branch([msg])])
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '### 👤 User' in md
    assert 'How do I sort a list?' in md


def test_render_assistant_message():
    msg = Message(role='assistant', text='Use `list.sort()`')
    conv = _make_conv([_make_branch([msg])])
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '### 🤖 Assistant' in md
    assert 'Use `list.sort()`' in md


def test_render_preserves_code_fence():
    text = "Here's a function:\n\n```python\ndef hello():\n    print('hi')\n```"
    msg = Message(role='assistant', text=text)
    conv = _make_conv([_make_branch([msg])])
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '```python' in md
    assert "def hello():" in md


def test_render_messages_separated_by_hr():
    msgs = [
        Message(role='user', text='Question'),
        Message(role='assistant', text='Answer'),
    ]
    conv = _make_conv([_make_branch(msgs)])
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    # At least two horizontal rules between/around messages
    assert md.count('\n---\n') >= 2


def test_render_unknown_model():
    conv = _make_conv([_make_branch([Message(role='user', text='hi')])], model=None)
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '| Model | unknown |' in md


def test_render_shared_flag():
    conv = _make_conv([_make_branch([Message(role='user', text='hi')])])
    conv.is_shared = True
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '| Shared | Yes |' in md


def test_render_no_shared_flag_when_false():
    conv = _make_conv([_make_branch([Message(role='user', text='hi')])])
    # is_shared defaults to False
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '| Shared |' not in md


def test_render_audio_count():
    conv = _make_conv([_make_branch([Message(role='user', text='hi')])])
    conv.audio_count = 5
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '| Audio | 5 recordings |' in md


def test_render_audio_count_singular():
    conv = _make_conv([_make_branch([Message(role='user', text='hi')])])
    conv.audio_count = 1
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '| Audio | 1 recording |' in md


def test_render_no_audio_row_when_zero():
    conv = _make_conv([_make_branch([Message(role='user', text='hi')])])
    # audio_count defaults to 0
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '| Audio |' not in md


def test_render_default_persona_user_label():
    msg = Message(role='user', text='hi')
    conv = _make_conv([_make_branch([msg])])
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '### 👤 User' in md


def test_render_default_persona_assistant_label():
    msg = Message(role='assistant', text='hello')
    conv = _make_conv([_make_branch([msg])])
    r = MarkdownRenderer()
    md = r.render(conv, conv.branches[0])
    assert '### 🤖 Assistant' in md


def test_render_custom_user_name():
    from models import PersonaConfig
    msg = Message(role='user', text='hi')
    conv = _make_conv([_make_branch([msg])])
    r = MarkdownRenderer(persona=PersonaConfig(user_name='Matt', assistant_name='Assistant'))
    md = r.render(conv, conv.branches[0])
    assert '### 👤 Matt' in md
    assert '### 👤 User' not in md


def test_render_custom_assistant_name():
    from models import PersonaConfig
    msg = Message(role='assistant', text='hello')
    conv = _make_conv([_make_branch([msg])])
    r = MarkdownRenderer(persona=PersonaConfig(user_name='User', assistant_name='ChatGPT'))
    md = r.render(conv, conv.branches[0])
    assert '### 🤖 ChatGPT' in md
    assert '### 🤖 Assistant' not in md


def test_render_none_persona_uses_defaults():
    from models import PersonaConfig
    msg = Message(role='user', text='hi')
    conv = _make_conv([_make_branch([msg])])
    r = MarkdownRenderer(persona=None)
    md = r.render(conv, conv.branches[0])
    assert '### 👤 User' in md
