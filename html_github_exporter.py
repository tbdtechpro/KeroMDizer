"""GitHub-style HTML exporter for KeroMDizer conversations."""
from __future__ import annotations
import html
import re
from pathlib import Path

try:
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import get_lexer_by_name, TextLexer
    from pygments.util import ClassNotFound
    _PYGMENTS = True
except ImportError:
    _PYGMENTS = False


GITHUB_CSS = """\
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
       font-size: 16px; line-height: 1.5; color: #24292e;
       max-width: 800px; margin: 40px auto; padding: 0 20px; }
h1 { font-size: 2em; border-bottom: 1px solid #eaecef; padding-bottom: .3em; }
h3 { font-size: 1.25em; border-bottom: 1px solid #eaecef; padding-bottom: .3em; }
hr { border: 0; border-top: 1px solid #eaecef; margin: 24px 0; }
pre { background: #f6f8fa; border-radius: 6px; padding: 16px; overflow: auto; }
code { background: #f6f8fa; border-radius: 3px; padding: .2em .4em; font-size: 85%; }
pre code { background: none; padding: 0; }
em { color: #6a737d; }
.user-header { color: #0366d6; }
.assistant-header { color: #28a745; }
"""

_FENCE_RE = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)
_INLINE_CODE_RE = re.compile(r'`([^`]+)`')
_BOLD_RE = re.compile(r'\*\*(.+?)\*\*')


def _highlight_code(code: str, lang: str) -> str:
    if not _PYGMENTS:
        return f'<pre><code>{html.escape(code)}</code></pre>'
    try:
        lexer = get_lexer_by_name(lang) if lang else TextLexer()
    except (ClassNotFound, Exception):
        lexer = TextLexer()
    formatter = HtmlFormatter(nowrap=False)
    return highlight(code, lexer, formatter)


def _prose_to_html(text: str) -> str:
    """Convert prose text (no code fences) to HTML paragraphs."""
    text = html.escape(text)
    text = _BOLD_RE.sub(r'<strong>\1</strong>', text)
    text = _INLINE_CODE_RE.sub(r'<code>\1</code>', text)
    paras = [p.strip() for p in text.split('\n\n') if p.strip()]
    return ''.join(f'<p>{p.replace(chr(10), "<br>")}</p>' for p in paras)


def _section_to_html(section: str) -> str:
    """Convert one section (between --- separators) to HTML."""
    section = section.strip()
    if not section:
        return ''

    # H1 title — only the first line; remaining lines handled as separate sections
    if section.startswith('# '):
        first_line, _, rest = section.partition('\n')
        h1 = f'<h1>{html.escape(first_line[2:].strip())}</h1>\n'
        if rest.strip():
            h1 += _section_to_html(rest)
        return h1

    # Italic metadata line: _date · model · branch_
    if section.startswith('_') and section.endswith('_') and '\n' not in section:
        inner = html.escape(section[1:-1])
        return f'<p><em>{inner}</em></p>\n'

    # Role header: ### 👤 User  or  ### 🤖 Assistant
    if section.startswith('### '):
        header_line, _, body = section.partition('\n')
        header_text = html.escape(header_line[4:].strip())
        css_class = 'user-header' if '👤' in header_line else 'assistant-header'
        h3 = f'<h3 class="{css_class}">{header_text}</h3>\n'
        if not body.strip():
            return h3
        # Process body: handle code fences
        parts = _FENCE_RE.split(body)
        html_body = ''
        i = 0
        while i < len(parts):
            if i % 3 == 0:
                prose = parts[i].strip()
                if prose:
                    html_body += _prose_to_html(prose)
            else:
                lang = parts[i]
                code = parts[i + 1] if i + 1 < len(parts) else ''
                html_body += _highlight_code(code.strip(), lang)
                i += 1
            i += 1
        return h3 + html_body + '\n'

    # Fallback: treat as prose
    return _prose_to_html(section) + '\n'


def _md_to_github_html(md: str) -> str:
    """Convert KeroMDizer markdown output to GitHub-style HTML body."""
    sections = re.split(r'\n---\n', md)
    return '\n<hr>\n'.join(
        html_sec
        for s in sections
        if (html_sec := _section_to_html(s))
    )


def export_html_github(md_content: str, output_path: Path) -> None:
    """Write GitHub-style HTML file from rendered markdown string."""
    body = _md_to_github_html(md_content)
    m = re.search(r'^# (.+)$', md_content, re.MULTILINE)
    title = html.escape(m.group(1)) if m else 'Conversation'
    pygments_css = HtmlFormatter().get_style_defs('.highlight') if _PYGMENTS else ''
    doc = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>{GITHUB_CSS}</style>
  <style>{pygments_css}</style>
</head>
<body>
{body}
</body>
</html>
'''
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(doc, encoding='utf-8')
