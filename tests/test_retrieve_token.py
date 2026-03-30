import json
import pytest
import retrieve_token


# ── parse_token_string ────────────────────────────────────────────────────────

def test_parse_token_string_bare_jwt():
    assert retrieve_token.parse_token_string('eyJtest123') == 'eyJtest123'


def test_parse_token_string_strips_whitespace():
    assert retrieve_token.parse_token_string('  eyJtest  \n') == 'eyJtest'


def test_parse_token_string_bearer_prefix():
    assert retrieve_token.parse_token_string('Bearer eyJtest') == 'eyJtest'


def test_parse_token_string_json_access_token():
    raw = json.dumps({'accessToken': 'eyJfromjson'})
    assert retrieve_token.parse_token_string(raw) == 'eyJfromjson'


def test_parse_token_string_json_access_token_snake():
    raw = json.dumps({'access_token': 'eyJsnake'})
    assert retrieve_token.parse_token_string(raw) == 'eyJsnake'


def test_parse_token_string_empty_raises():
    with pytest.raises(ValueError, match='empty'):
        retrieve_token.parse_token_string('   ')


def test_parse_token_string_json_missing_token_raises():
    with pytest.raises(ValueError, match='accessToken'):
        retrieve_token.parse_token_string(json.dumps({'other': 'value'}))


# ── save_token ────────────────────────────────────────────────────────────────

def test_save_token_writes_json(tmp_path):
    dest = tmp_path / 'token.json'
    retrieve_token.save_token('eyJtest', token_file=dest)
    data = json.loads(dest.read_text())
    assert data['access_token'] == 'eyJtest'
    assert 'fetched_at' in data


def test_save_token_overwrites_existing(tmp_path):
    dest = tmp_path / 'token.json'
    dest.write_text(json.dumps({'access_token': 'old'}))
    retrieve_token.save_token('new_token', token_file=dest)
    data = json.loads(dest.read_text())
    assert data['access_token'] == 'new_token'
