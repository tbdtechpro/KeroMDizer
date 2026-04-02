from pathlib import Path
import pytest
import config
from models import PersonaConfig


def _write_toml(path: Path, content: str) -> None:
    path.write_text(content, encoding='utf-8')


def test_load_persona_no_config_file(monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'nonexistent.toml')
    persona = config.load_persona()
    assert persona.user_name == 'User'
    assert persona.assistant_name == 'ChatGPT'  # provider default for 'chatgpt'


def test_load_persona_reads_user_name(monkeypatch, tmp_path):
    cfg = tmp_path / 'keromdizer.toml'
    _write_toml(cfg, '[user]\nname = "Matt"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
    persona = config.load_persona()
    assert persona.user_name == 'Matt'


def test_load_persona_reads_chatgpt_assistant_name(monkeypatch, tmp_path):
    cfg = tmp_path / 'keromdizer.toml'
    _write_toml(cfg, '[providers.chatgpt]\nassistant_name = "GPT"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
    persona = config.load_persona(provider='chatgpt')
    assert persona.assistant_name == 'GPT'


def test_load_persona_reads_deepseek_assistant_name(monkeypatch, tmp_path):
    cfg = tmp_path / 'keromdizer.toml'
    _write_toml(cfg, '[providers.deepseek]\nassistant_name = "DS"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
    persona = config.load_persona(provider='deepseek')
    assert persona.assistant_name == 'DS'


def test_load_persona_cli_user_name_overrides_file(monkeypatch, tmp_path):
    cfg = tmp_path / 'keromdizer.toml'
    _write_toml(cfg, '[user]\nname = "Matt"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
    persona = config.load_persona(user_name='Alice')
    assert persona.user_name == 'Alice'


def test_load_persona_cli_assistant_name_overrides_file(monkeypatch, tmp_path):
    cfg = tmp_path / 'keromdizer.toml'
    _write_toml(cfg, '[providers.chatgpt]\nassistant_name = "GPT"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
    persona = config.load_persona(assistant_name='MyBot')
    assert persona.assistant_name == 'MyBot'


def test_load_persona_missing_provider_uses_provider_default(monkeypatch, tmp_path):
    cfg = tmp_path / 'keromdizer.toml'
    _write_toml(cfg, '[user]\nname = "Matt"\n')  # no [providers.chatgpt]
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
    persona = config.load_persona(provider='chatgpt')
    assert persona.assistant_name == 'ChatGPT'


def test_load_persona_deepseek_provider_default(monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'nonexistent.toml')
    persona = config.load_persona(provider='deepseek')
    assert persona.assistant_name == 'DeepSeek'


def test_load_persona_unknown_provider_falls_back_to_assistant(monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'nonexistent.toml')
    persona = config.load_persona(provider='unknown_provider')
    assert persona.assistant_name == 'Assistant'


def test_load_persona_returns_persona_config_instance(monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'nonexistent.toml')
    persona = config.load_persona()
    assert isinstance(persona, PersonaConfig)


def test_load_persona_empty_string_user_name_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'nonexistent.toml')
    persona = config.load_persona(user_name='')
    assert persona.user_name == 'User'


def test_load_persona_empty_string_assistant_name_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'nonexistent.toml')
    persona = config.load_persona(assistant_name='')
    assert persona.assistant_name == 'ChatGPT'


def test_load_persona_malformed_toml_raises_value_error(monkeypatch, tmp_path):
    cfg = tmp_path / 'bad.toml'
    cfg.write_text('not valid toml [[[[', encoding='utf-8')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
    with pytest.raises(ValueError, match='Error parsing'):
        config.load_persona()


def test_load_export_config_defaults(monkeypatch, tmp_path):
    """load_export_config returns all-disabled defaults when no TOML exists."""
    from config import load_export_config
    monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'nonexistent.toml')
    cfg = load_export_config()
    assert cfg.html_github_enabled is False
    assert cfg.html_retro_enabled is False
    assert cfg.docx_enabled is False
    assert cfg.html_github_dir == ''


def test_load_export_config_obsidian_defaults_to_disabled(monkeypatch, tmp_path):
    from config import load_export_config
    monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'nonexistent.toml')
    cfg = load_export_config()
    assert cfg.obsidian_enabled is False
    assert cfg.obsidian_dir == ''


def test_load_export_config_obsidian_enabled_from_toml(monkeypatch, tmp_path):
    from config import load_export_config
    cfg_file = tmp_path / 'keromdizer.toml'
    _write_toml(cfg_file, '[exports]\nobsidian = "yes"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg_file)
    cfg = load_export_config()
    assert cfg.obsidian_enabled is True


def test_load_export_config_obsidian_dir_from_toml(monkeypatch, tmp_path):
    from config import load_export_config
    cfg_file = tmp_path / 'keromdizer.toml'
    _write_toml(cfg_file, '[exports]\nobsidian = "yes"\nobsidian_dir = "/my/vault"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg_file)
    cfg = load_export_config()
    assert cfg.obsidian_dir == '/my/vault'
