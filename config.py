import tomllib
from pathlib import Path

from models import PersonaConfig, BranchConfig, ExportConfig, SyncConfig

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


_VALID_CONFLICT_MODES = ('preserve', 'overwrite', 'flag')


def load_chatgpt_projects() -> dict[str, str]:
    """Read [chatgpt.projects] from ~/.keromdizer.toml.

    Returns {gizmo_id: project_name}. Empty dict if section absent.
    """
    try:
        data = _load_toml()
    except ValueError:
        return {}
    return dict(data.get('chatgpt', {}).get('projects', {}))


def load_sync_config() -> SyncConfig:
    """Read [sync] section from ~/.keromdizer.toml. Defaults: project_conflict='preserve'."""
    try:
        data = _load_toml()
    except ValueError:
        return SyncConfig()
    raw = data.get('sync', {}).get('project_conflict', 'preserve')
    if raw not in _VALID_CONFLICT_MODES:
        raw = 'preserve'
    return SyncConfig(project_conflict=raw)


def _serialize_toml(data: dict, prefix: str = '') -> list[str]:
    """Minimal recursive TOML serializer for string-valued nested dicts."""
    lines: list[str] = []
    flat = {k: v for k, v in data.items() if not isinstance(v, dict)}
    nested = {k: v for k, v in data.items() if isinstance(v, dict)}
    if flat:
        if prefix:
            lines.append(f'[{prefix}]')
        for k, v in flat.items():
            lines.append(f'{k} = "{v}"')
    for k, v in nested.items():
        sub = f'{prefix}.{k}' if prefix else k
        lines.extend(_serialize_toml(v, sub))
    return lines


def save_sync_config(cfg: SyncConfig) -> None:
    """Write [sync] section to ~/.keromdizer.toml, preserving all other sections."""
    try:
        data = _load_toml()
    except ValueError:
        data = {}
    data.setdefault('sync', {})['project_conflict'] = cfg.project_conflict
    CONFIG_PATH.write_text('\n'.join(_serialize_toml(data)) + '\n', encoding='utf-8')
