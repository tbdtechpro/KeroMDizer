import pytest
from content_parser import parse_content, ContentSegment


def test_plain_prose_only():
    segments = parse_content('Hello world, no code here.')
    assert len(segments) == 1
    assert segments[0].type == 'prose'
    assert segments[0].text == 'Hello world, no code here.'
    assert segments[0].language is None


def test_single_code_block_with_hint():
    text = 'Here is code:\n```python\nprint("hi")\n```\nThat is all.'
    segments = parse_content(text)
    assert len(segments) == 3
    assert segments[0].type == 'prose'
    assert segments[1].type == 'code'
    assert segments[1].language == 'python'
    assert segments[1].text == 'print("hi")\n'
    assert segments[2].type == 'prose'


def test_code_block_without_hint_gets_language_or_none():
    text = '```\ndef foo():\n    pass\n```'
    segments = parse_content(text)
    assert len(segments) == 1
    assert segments[0].type == 'code'
    # language may be guessed by Pygments or None — just check it's a str or None
    assert segments[0].language is None or isinstance(segments[0].language, str)


def test_multiple_code_blocks():
    text = '```python\nx = 1\n```\nSome text.\n```bash\necho hi\n```'
    segments = parse_content(text)
    types = [s.type for s in segments]
    assert types.count('code') == 2
    langs = [s.language for s in segments if s.type == 'code']
    assert 'python' in langs
    assert 'bash' in langs


def test_empty_string():
    assert parse_content('') == []


def test_code_block_only():
    text = '```js\nconsole.log(1)\n```'
    segments = parse_content(text)
    assert len(segments) == 1
    assert segments[0].type == 'code'
    assert segments[0].language == 'js'


def test_prose_stripped_of_surrounding_whitespace():
    text = '\n\nHello\n\n```python\npass\n```\n\nWorld\n\n'
    segments = parse_content(text)
    prose_segs = [s for s in segments if s.type == 'prose']
    assert prose_segs[0].text == 'Hello'
    assert prose_segs[1].text == 'World'
