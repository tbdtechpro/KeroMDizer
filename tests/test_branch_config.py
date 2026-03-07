import pytest
from pathlib import Path
from models import BranchConfig
from config import load_branch_config, load_db_path


def test_branch_config_defaults():
    cfg = BranchConfig()
    assert cfg.import_branches == 'all'
    assert cfg.export_markdown == 'all'
    assert cfg.export_jsonl == 'all'


def test_load_branch_config_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr('config.CONFIG_PATH', tmp_path / 'nonexistent.toml')
    cfg = load_branch_config()
    assert cfg.import_branches == 'all'
    assert cfg.export_markdown == 'all'
    assert cfg.export_jsonl == 'all'


def test_load_branch_config_from_toml(tmp_path, monkeypatch):
    toml = tmp_path / '.keromdizer.toml'
    toml.write_text(
        '[branches]\nimport = "main"\nexport_markdown = "all"\nexport_jsonl = "main"\n',
        encoding='utf-8'
    )
    monkeypatch.setattr('config.CONFIG_PATH', toml)
    cfg = load_branch_config()
    assert cfg.import_branches == 'main'
    assert cfg.export_markdown == 'all'
    assert cfg.export_jsonl == 'main'


def test_load_db_path_default(tmp_path, monkeypatch):
    monkeypatch.setattr('config.CONFIG_PATH', tmp_path / 'nonexistent.toml')
    p = load_db_path()
    assert p == Path.home() / '.keromdizer.db'


def test_load_db_path_from_toml(tmp_path, monkeypatch):
    toml = tmp_path / '.keromdizer.toml'
    toml.write_text('[database]\npath = "/tmp/test.db"\n', encoding='utf-8')
    monkeypatch.setattr('config.CONFIG_PATH', toml)
    p = load_db_path()
    assert p == Path('/tmp/test.db')
