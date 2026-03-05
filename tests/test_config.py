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
