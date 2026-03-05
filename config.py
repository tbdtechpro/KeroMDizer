import tomllib
from pathlib import Path

from models import PersonaConfig

CONFIG_PATH = Path.home() / '.keromdizer.toml'

PROVIDER_DEFAULTS: dict[str, str] = {
    'chatgpt': 'ChatGPT',
    'deepseek': 'DeepSeek',
}


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
    data: dict[str, object] = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'rb') as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f'Error parsing {CONFIG_PATH}: {e}') from e

    resolved_user = (user_name.strip() if user_name is not None else None) or (
        data.get('user', {}).get('name') or 'User'
    )
    resolved_assistant = (assistant_name.strip() if assistant_name is not None else None) or (
        data.get('providers', {}).get(provider, {}).get('assistant_name')
        or PROVIDER_DEFAULTS.get(provider, 'Assistant')
    )
    return PersonaConfig(user_name=resolved_user, assistant_name=resolved_assistant)
