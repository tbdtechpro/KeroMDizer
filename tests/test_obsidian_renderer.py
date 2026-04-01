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
