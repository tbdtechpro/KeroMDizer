import tomllib
from pathlib import Path

from models import PersonaConfig, BranchConfig, ExportConfig

CONFIG_PATH = Path.home() / '.keromdizer.toml'

PROVIDER_DEFAULTS: dict[str, str] = {
    'chatgpt': 'ChatGPT',
    'deepseek': 'DeepSeek',
}


def _load_toml() -> dict:
    """Load ~/.keromdizer.toml, returning empty dict if file missing."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, 'rb') as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f'Error parsing {CONFIG_PATH}: {e}') from e


def load_persona(
    provider: str = 'chatgpt',
    user_name: str | None = None,
    assistant_name: str | None = None,
) -> PersonaConfig:
    """Load persona config from ~/.keromdizer.toml with CLI override support.

    Fallback chain (highest to lowest priority):
      1. CLI args (user_name / assistant_name params)
      2. ~/.keromdizer.toml [user].name / [providers.<provider>].assistant_name
      3. Provider default from PROVIDER_DEFAULTS
      4. 'User' / 'Assistant' (absolute fallback)
    """
    data = _load_toml()
    resolved_user = (user_name.strip() if user_name is not None else None) or (
        data.get('user', {}).get('name') or 'User'
    )
    resolved_assistant = (assistant_name.strip() if assistant_name is not None else None) or (
        data.get('providers', {}).get(provider, {}).get('assistant_name')
        or PROVIDER_DEFAULTS.get(provider, 'Assistant')
    )
    return PersonaConfig(user_name=resolved_user, assistant_name=resolved_assistant)


def load_branch_config() -> BranchConfig:
    """Load branch handling config from ~/.keromdizer.toml."""
    data = _load_toml()
    b = data.get('branches', {})
    return BranchConfig(
        import_branches=b.get('import', 'all'),
        export_markdown=b.get('export_markdown', 'all'),
        export_jsonl=b.get('export_jsonl', 'all'),
    )


def load_db_path() -> Path:
    """Return configured DB path, defaulting to ~/.keromdizer.db."""
    data = _load_toml()
    raw = data.get('database', {}).get('path', '')
    if raw:
        return Path(raw).expanduser()
    return Path.home() / '.keromdizer.db'


def load_export_config() -> ExportConfig:
    """Load export format settings from ~/.keromdizer.toml."""
    data = _load_toml()
    e = data.get('exports', {})
    return ExportConfig(
        html_github_enabled=e.get('html_github', 'no') == 'yes',
        html_github_dir=e.get('html_github_dir', ''),
        html_retro_enabled=e.get('html_retro', 'no') == 'yes',
        html_retro_dir=e.get('html_retro_dir', ''),
        docx_enabled=e.get('docx', 'no') == 'yes',
        docx_dir=e.get('docx_dir', ''),
    )
