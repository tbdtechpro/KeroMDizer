import json
from pathlib import Path
from conversation_parser import ConversationParser
from deepseek_parser import DeepSeekParser


def detect_source(export_folder: Path) -> str:
    """Detect export source from folder contents.

    Returns 'deepseek' if user.json contains a 'mobile' field (DeepSeek-specific).
    Returns 'chatgpt' otherwise (safe default).
    """
    user_json = export_folder / 'user.json'
    if user_json.exists():
        try:
            data = json.loads(user_json.read_text(encoding='utf-8'))
            if 'mobile' in data:
                return 'deepseek'
        except (json.JSONDecodeError, OSError):
            pass
    return 'chatgpt'


def build_parser(export_folder: Path, source: str | None = None) -> tuple[ConversationParser, str]:
    """Build the appropriate parser for the given export folder.

    Args:
        export_folder: Path to the export directory
        source: 'chatgpt' or 'deepseek', or None for auto-detection

    Returns:
        (parser_instance, provider_string) tuple
    """
    provider = source or detect_source(export_folder)
    parser = DeepSeekParser(export_folder) if provider == 'deepseek' else ConversationParser(export_folder)
    return parser, provider
