"""Tests for ObsidianRenderer."""
import pytest


def _branch_row(**overrides) -> dict:
    """Minimal valid branch row matching db.list_branches() shape."""
    base = {
        'branch_id': 'conv1__branch_1',
        'conversation_id': 'conv1',
        'branch_index': 1,
        'is_main_branch': True,
        'messages': [],
        'tags': [],
        'project': None,
        'category': None,
        'syntax': [],
        'inferred_tags': ['python', 'api design'],
        'inferred_syntax': ['python'],
        'md_filename': '2026-01-14_Hello_World.md',
        'title': 'Hello World',
        'provider': 'chatgpt',
        'conv_create_time': '2026-01-14T04:16:34+00:00',
        'model_slug': 'gpt-4o',
        'branch_count': 1,
        'user_alias': 'Matt',
        'assistant_alias': 'ChatGPT',
    }
    base.update(overrides)
    return base


# ── Frontmatter tests ──────────────────────────────────────────────────────────

def test_frontmatter_starts_and_ends_with_dashes():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    row = _branch_row()
    result = r._build_frontmatter(row)
    assert result.startswith('---\n')
    assert result.endswith('\n---')


def test_frontmatter_title_present_and_quoted():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(title='Hello World'))
    assert 'title: "Hello World"' in result


def test_frontmatter_title_with_colon_quoted():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(title='Python: A Guide'))
    assert 'title: "Python: A Guide"' in result


def test_frontmatter_aliases_present():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(title='Hello World'))
    assert 'aliases:' in result
    assert '  - "Hello World"' in result


def test_frontmatter_created_date_only():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(conv_create_time='2026-01-14T04:16:34+00:00'))
    assert 'created: 2026-01-14' in result
    assert 'T' not in result.split('created:')[1].split('\n')[0]


def test_frontmatter_provider_present():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(provider='chatgpt'))
    assert 'provider: chatgpt' in result


def test_frontmatter_model_present():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(model_slug='gpt-4o'))
    assert 'model: gpt-4o' in result


def test_frontmatter_model_omitted_when_null():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(model_slug=None))
    assert 'model:' not in result


def test_frontmatter_conversation_id_present():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(conversation_id='abc-123'))
    assert 'conversation_id: abc-123' in result


def test_frontmatter_branch_fields_omitted_for_single_branch():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(branch_count=1))
    assert 'branch:' not in result
    assert 'branch_count:' not in result


def test_frontmatter_branch_fields_present_for_multi_branch():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(branch_index=2, branch_count=3))
    assert 'branch: 2' in result
    assert 'branch_count: 3' in result


def test_frontmatter_tags_sanitized_and_merged():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    row = _branch_row(inferred_tags=['api design', 'python'], tags=['My Tag!'])
    result = r._build_frontmatter(row)
    assert 'tags:' in result
    assert '  - api-design' in result
    assert '  - python' in result
    assert '  - my-tag' in result


def test_frontmatter_tags_deduplicated():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    # inferred_tags has python twice, tags has it once — should deduplicate
    row = _branch_row(inferred_tags=['python', 'python'], tags=['python'], inferred_syntax=[])
    result = r._build_frontmatter(row)
    # Tags section should have python only once (deduplicated from 3 occurrences)
    tags_start = result.find('tags:')
    tags_end = result.find('\n---', tags_start)
    tags_section = result[tags_start:tags_end]
    assert tags_section.count('  - python') == 1


def test_frontmatter_tags_omitted_when_empty():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(inferred_tags=[], tags=[]))
    assert 'tags:' not in result


def test_frontmatter_project_present_when_set():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(project='my-project'))
    assert 'project: "my-project"' in result


def test_frontmatter_project_omitted_when_null():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(project=None))
    assert 'project:' not in result


def test_frontmatter_category_present_when_set():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(category='work'))
    assert 'category: "work"' in result


def test_frontmatter_syntax_list_present():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(inferred_syntax=['python', 'bash'], syntax=[]))
    assert 'syntax:' in result
    assert '  - python' in result
    assert '  - bash' in result


def test_frontmatter_syntax_omitted_when_empty():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._build_frontmatter(_branch_row(inferred_syntax=[], syntax=[]))
    assert 'syntax:' not in result


# ── Callout tests ──────────────────────────────────────────────────────────────

def test_wrap_callout_header_format():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._wrap_callout('question', '👤 Matt', 'Hello world')
    assert result.startswith('> [!question] 👤 Matt\n')


def test_wrap_callout_body_lines_prefixed():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._wrap_callout('note', 'Label', 'line one\nline two')
    lines = result.split('\n')
    assert '> line one' in lines
    assert '> line two' in lines


def test_wrap_callout_blank_lines_become_bare_gt():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r._wrap_callout('note', 'Label', 'para one\n\npara two')
    lines = result.split('\n')
    # blank line must be '>' not '> ' (no trailing space)
    assert '>' in lines
    assert all(l != '> ' for l in lines)


def test_wrap_callout_code_fence_lines_prefixed():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    body = '```python\ndef foo():\n    pass\n```'
    result = r._wrap_callout('abstract', 'Label', body)
    assert '> ```python' in result
    assert '> def foo():' in result
    assert '> ```' in result


def test_segments_to_text_prose_only():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    content = [{'type': 'prose', 'text': 'Hello world'}]
    assert r._segments_to_text(content) == 'Hello world'


def test_segments_to_text_code_wrapped_in_fences():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    content = [{'type': 'code', 'language': 'python', 'text': 'print("hi")'}]
    result = r._segments_to_text(content)
    assert result == '```python\nprint("hi")\n```'


def test_segments_to_text_mixed_separated_by_blank_line():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    content = [
        {'type': 'prose', 'text': 'See this:'},
        {'type': 'code', 'language': 'bash', 'text': 'echo hi'},
    ]
    result = r._segments_to_text(content)
    assert 'See this:' in result
    assert '```bash\necho hi\n```' in result
    assert 'See this:\n\n```bash' in result


def test_segments_to_text_code_no_language():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    content = [{'type': 'code', 'language': None, 'text': 'some text'}]
    result = r._segments_to_text(content)
    assert result == '```\nsome text\n```'


# ── Image conversion tests ─────────────────────────────────────────────────────

def test_image_converted_to_wikilink():
    from obsidian_renderer import _IMAGE_RE
    text = '![alt text](assets/file_abc-sanitized.jpg)'
    result = _IMAGE_RE.sub(lambda m: f'![[{m.group(1)}]]', text)
    assert result == '![[file_abc-sanitized.jpg]]'


def test_image_no_alt_converted():
    from obsidian_renderer import _IMAGE_RE
    text = '![](assets/image.png)'
    result = _IMAGE_RE.sub(lambda m: f'![[{m.group(1)}]]', text)
    assert result == '![[image.png]]'


def test_non_asset_image_not_converted():
    from obsidian_renderer import _IMAGE_RE
    text = '![](https://example.com/image.png)'
    result = _IMAGE_RE.sub(lambda m: f'![[{m.group(1)}]]', text)
    assert result == '![](https://example.com/image.png)'


# ── render() integration tests ─────────────────────────────────────────────────

def _make_row_with_messages() -> dict:
    return _branch_row(
        messages=[
            {
                'role': 'user',
                'timestamp': '2026-01-14T04:16:34+00:00',
                'content': [{'type': 'prose', 'text': 'What is Python?'}],
            },
            {
                'role': 'assistant',
                'timestamp': '2026-01-14T04:16:35+00:00',
                'content': [
                    {'type': 'prose', 'text': 'Python is a language.'},
                    {'type': 'code', 'language': 'python', 'text': 'print("hello")'},
                ],
            },
        ]
    )


def test_render_starts_with_frontmatter():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r.render(_make_row_with_messages())
    assert result.startswith('---\n')


def test_render_contains_title_heading():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r.render(_make_row_with_messages())
    assert '\n# Hello World\n' in result


def test_render_user_turn_uses_question_callout():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r.render(_make_row_with_messages())
    assert '> [!question] 👤 Matt' in result


def test_render_assistant_turn_uses_abstract_callout():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r.render(_make_row_with_messages())
    assert '> [!abstract] 🤖 ChatGPT' in result


def test_render_message_content_inside_callout():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r.render(_make_row_with_messages())
    assert '> What is Python?' in result
    assert '> Python is a language.' in result
    assert '> ```python' in result


def test_render_image_converted_to_wikilink():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    row = _branch_row(messages=[{
        'role': 'user',
        'timestamp': None,
        'content': [{'type': 'prose', 'text': '![](assets/file_abc.jpg)'}],
    }])
    result = r.render(row)
    assert '![[file_abc.jpg]]' in result
    assert '![](assets/' not in result


def test_render_empty_messages_produces_valid_output():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    result = r.render(_branch_row(messages=[]))
    assert result.startswith('---\n')
    assert '# Hello World' in result


def test_render_fallback_persona_when_aliases_missing():
    from obsidian_renderer import ObsidianRenderer
    r = ObsidianRenderer()
    row = _branch_row(
        user_alias=None,
        assistant_alias=None,
        messages=[
            {'role': 'user', 'timestamp': None, 'content': [{'type': 'prose', 'text': 'Hi'}]},
            {'role': 'assistant', 'timestamp': None, 'content': [{'type': 'prose', 'text': 'Hello'}]},
        ],
    )
    result = r.render(row)
    assert '👤 User' in result
    assert '🤖 Assistant' in result
