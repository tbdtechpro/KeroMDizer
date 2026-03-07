import pytest
from content_parser import ContentSegment
from inference import infer_tags, infer_syntax, build_full_text


def test_infer_tags_returns_list_of_strings():
    text = 'Python async programming with asyncio event loops and coroutines'
    tags = infer_tags(text)
    assert isinstance(tags, list)
    assert all(isinstance(t, str) for t in tags)


def test_infer_tags_empty_text():
    assert infer_tags('') == []
    assert infer_tags('   ') == []


def test_infer_tags_respects_top_n():
    text = ' '.join(['word'] * 5 + ['python', 'async', 'loop', 'coroutine', 'event',
                                      'thread', 'socket', 'buffer', 'stream', 'queue',
                                      'channel', 'future', 'task'])
    tags = infer_tags(text, top_n=5)
    assert len(tags) <= 5


def test_infer_syntax_from_segments():
    segments = [
        ContentSegment(type='prose', text='Some prose'),
        ContentSegment(type='code', language='python', text='x = 1'),
        ContentSegment(type='code', language='bash', text='echo hi'),
        ContentSegment(type='code', language='python', text='y = 2'),  # duplicate
    ]
    langs = infer_syntax(segments)
    assert langs == ['python', 'bash']  # deduplicated, order preserved


def test_infer_syntax_ignores_prose():
    segments = [ContentSegment(type='prose', text='Just text, no code.')]
    assert infer_syntax(segments) == []


def test_infer_syntax_skips_none_language():
    segments = [
        ContentSegment(type='code', language=None, text='???'),
        ContentSegment(type='code', language='js', text='console.log()'),
    ]
    langs = infer_syntax(segments)
    assert langs == ['js']


def test_build_full_text_concatenates_prose():
    segments = [
        ContentSegment(type='prose', text='Hello world'),
        ContentSegment(type='code', language='python', text='print()'),
        ContentSegment(type='prose', text='Goodbye'),
    ]
    text = build_full_text(segments)
    assert 'Hello world' in text
    assert 'Goodbye' in text
    assert 'print()' in text
