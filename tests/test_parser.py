from models import Message, Branch, Conversation


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
