import pytest
from pathlib import Path
import config
from models import SyncConfig


def _write_toml(path: Path, content: str) -> None:
    path.write_text(content, encoding='utf-8')


# --- load_chatgpt_projects ---

def test_load_chatgpt_projects_empty_when_no_file(monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'nonexistent.toml')
    assert config.load_chatgpt_projects() == {}


def test_load_chatgpt_projects_empty_when_section_absent(monkeypatch, tmp_path):
    cfg = tmp_path / 'k.toml'
    _write_toml(cfg, '[user]\nname = "Matt"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
    assert config.load_chatgpt_projects() == {}


def test_load_chatgpt_projects_reads_gizmo_map(monkeypatch, tmp_path):
    cfg = tmp_path / 'k.toml'
    _write_toml(cfg, '[chatgpt.projects]\ng-p-aaa = "Project A"\ng-p-bbb = "Project B"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
    result = config.load_chatgpt_projects()
    assert result == {'g-p-aaa': 'Project A', 'g-p-bbb': 'Project B'}


# --- load_sync_config ---

def test_load_sync_config_defaults_to_preserve(monkeypatch, tmp_path):
    monkeypatch.setattr(config, 'CONFIG_PATH', tmp_path / 'nonexistent.toml')
    cfg = config.load_sync_config()
    assert cfg.project_conflict == 'preserve'


def test_load_sync_config_reads_value(monkeypatch, tmp_path):
    cfg = tmp_path / 'k.toml'
    _write_toml(cfg, '[sync]\nproject_conflict = "overwrite"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
    result = config.load_sync_config()
    assert result.project_conflict == 'overwrite'


def test_load_sync_config_unknown_value_falls_back_to_preserve(monkeypatch, tmp_path):
    cfg = tmp_path / 'k.toml'
    _write_toml(cfg, '[sync]\nproject_conflict = "bogus"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg)
    result = config.load_sync_config()
    assert result.project_conflict == 'preserve'


# --- save_sync_config ---

def test_save_sync_config_writes_sync_section(monkeypatch, tmp_path):
    cfg_path = tmp_path / 'k.toml'
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg_path)
    config.save_sync_config(SyncConfig(project_conflict='flag'))
    result = config.load_sync_config()
    assert result.project_conflict == 'flag'


def test_save_sync_config_preserves_other_sections(monkeypatch, tmp_path):
    cfg_path = tmp_path / 'k.toml'
    _write_toml(cfg_path, '[user]\nname = "Matt"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg_path)
    config.save_sync_config(SyncConfig(project_conflict='overwrite'))
    persona = config.load_persona()
    assert persona.user_name == 'Matt'


def test_save_sync_config_preserves_chatgpt_projects(monkeypatch, tmp_path):
    cfg_path = tmp_path / 'k.toml'
    _write_toml(cfg_path, '[chatgpt.projects]\ng-p-aaa = "Project A"\n')
    monkeypatch.setattr(config, 'CONFIG_PATH', cfg_path)
    config.save_sync_config(SyncConfig(project_conflict='overwrite'))
    projects = config.load_chatgpt_projects()
    assert projects == {'g-p-aaa': 'Project A'}
