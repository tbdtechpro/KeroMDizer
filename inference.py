import yake
from content_parser import ContentSegment


def infer_tags(text: str, top_n: int = 10) -> list[str]:
    """Extract top_n keywords from text using YAKE."""
    if not text or not text.strip():
        return []
    extractor = yake.KeywordExtractor(lan='en', n=1, dedupLim=0.9, top=top_n)
    results = extractor.extract_keywords(text)
    return [kw for kw, _score in results if "'" not in kw]


def infer_syntax(segments: list[ContentSegment]) -> list[str]:
    """Return deduplicated list of code languages, in order of first appearance."""
    seen: list[str] = []
    for seg in segments:
        if seg.type == 'code' and seg.language and seg.language not in seen:
            seen.append(seg.language)
    return seen


def build_full_text(segments: list[ContentSegment]) -> str:
    """Concatenate all segment text for keyword extraction input."""
    return '\n'.join(seg.text for seg in segments)
