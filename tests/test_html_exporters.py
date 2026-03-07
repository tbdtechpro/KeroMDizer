"""Tests for HTML exporters (GitHub-style and Retro 1994)."""
import pytest
from pathlib import Path
from html_github_exporter import export_html_github
from html_retro_exporter import export_html_retro


MINIMAL_MD = """\
# My Conversation

_2026-01-14  ·  gpt-4o_

---

### 👤 User

Hello world

---

### 🤖 Assistant

Here is some code:
```python
print('hello')
```

---
"""


def test_github_html_file_written(tmp_path):
    out = tmp_path / 'test.html'
    export_html_github(MINIMAL_MD, out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_github_html_contains_title(tmp_path):
    out = tmp_path / 'test.html'
    export_html_github(MINIMAL_MD, out)
    content = out.read_text()
    assert '<h1>My Conversation</h1>' in content


def test_github_html_code_block_pygments(tmp_path):
    out = tmp_path / 'test.html'
    export_html_github(MINIMAL_MD, out)
    content = out.read_text()
    # Pygments wraps code in <div class="highlight">
    assert 'highlight' in content


def test_github_html_user_header_class(tmp_path):
    out = tmp_path / 'test.html'
    export_html_github(MINIMAL_MD, out)
    content = out.read_text()
    assert 'user-header' in content


def test_github_html_assistant_header_class(tmp_path):
    out = tmp_path / 'test.html'
    export_html_github(MINIMAL_MD, out)
    content = out.read_text()
    assert 'assistant-header' in content


def test_github_html_doctype(tmp_path):
    out = tmp_path / 'test.html'
    export_html_github(MINIMAL_MD, out)
    content = out.read_text()
    assert content.startswith('<!DOCTYPE html>')


def test_github_html_creates_parent_dirs(tmp_path):
    out = tmp_path / 'subdir' / 'nested' / 'test.html'
    export_html_github(MINIMAL_MD, out)
    assert out.exists()


def test_retro_html_doctype(tmp_path):
    out = tmp_path / 'retro.html'
    export_html_retro(MINIMAL_MD, out)
    content = out.read_text()
    assert '<!DOCTYPE HTML PUBLIC' in content


def test_retro_html_blink_animation(tmp_path):
    out = tmp_path / 'retro.html'
    export_html_retro(MINIMAL_MD, out)
    content = out.read_text()
    assert 'blink' in content


def test_retro_html_emoji_replaced(tmp_path):
    out = tmp_path / 'retro.html'
    export_html_retro(MINIMAL_MD, out)
    content = out.read_text()
    # 👤 and 🤖 should be replaced by <img> tags
    assert '<img' in content
    assert '👤' not in content
    assert '🤖' not in content


def test_retro_html_file_written(tmp_path):
    out = tmp_path / 'retro.html'
    export_html_retro(MINIMAL_MD, out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_retro_html_netscape_footer(tmp_path):
    out = tmp_path / 'retro.html'
    export_html_retro(MINIMAL_MD, out)
    content = out.read_text()
    assert 'Netscape Navigator' in content
