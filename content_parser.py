import re
from dataclasses import dataclass

FENCE_RE = re.compile(r'```([a-zA-Z0-9+\-._]*)\n(.*?)```', re.DOTALL)


@dataclass
class ContentSegment:
    type: str            # 'prose' | 'code'
    text: str
    language: str | None = None


def parse_content(text: str) -> list[ContentSegment]:
    """Split message text into alternating prose and code segments."""
    if not text:
        return []
    segments: list[ContentSegment] = []
    last_end = 0
    for match in FENCE_RE.finditer(text):
        prose = text[last_end:match.start()].strip()
        if prose:
            segments.append(ContentSegment(type='prose', text=prose))
        lang_hint = match.group(1).strip().lower()
        code_text = match.group(2)
        language = lang_hint if lang_hint else _guess_language(code_text)
        segments.append(ContentSegment(type='code', text=code_text, language=language))
        last_end = match.end()
    tail = text[last_end:].strip()
    if tail:
        segments.append(ContentSegment(type='prose', text=tail))
    return segments


def _guess_language(code: str) -> str | None:
    try:
        from pygments.lexers import guess_lexer
        lexer = guess_lexer(code)
        # Reject the generic 'text' lexer — return None instead
        if lexer.name.lower() in ('text only', 'text'):
            return None
        return lexer.aliases[0] if lexer.aliases else lexer.name.lower()
    except Exception:
        return None
