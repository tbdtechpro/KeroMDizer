import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock
import project_fetcher


# ── load_token ────────────────────────────────────────────────────────────────

def test_load_token_returns_none_when_file_missing(tmp_path):
    assert project_fetcher.load_token(tmp_path / 'no.json') is None


def test_load_token_returns_access_token(tmp_path):
    f = tmp_path / 'token.json'
    f.write_text(json.dumps({'access_token': 'eyJtest', 'fetched_at': '2026-03-30'}))
    assert project_fetcher.load_token(f) == 'eyJtest'


def test_load_token_returns_none_when_field_missing(tmp_path):
    f = tmp_path / 'token.json'
    f.write_text(json.dumps({'other': 'value'}))
    assert project_fetcher.load_token(f) is None


# ── fetch_project_map ─────────────────────────────────────────────────────────

def _mock_response(items: list[dict], next_cursor=None) -> MagicMock:
    """Build a mock requests.Response returning the given conversation items."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        'items': items,
        'cursor': next_cursor,
    }
    return resp


def test_fetch_project_map_single_page(monkeypatch):
    responses = [
        _mock_response([
            {'conversation_id': 'conv-1'},
            {'conversation_id': 'conv-2'},
        ]),
    ]
    mock_get = MagicMock(side_effect=responses)
    monkeypatch.setattr(project_fetcher.requests, 'get', mock_get)

    result = project_fetcher.fetch_project_map(
        token='tok',
        projects={'g-p-aaa': 'Tools'},
    )
    assert result == {'conv-1': 'Tools', 'conv-2': 'Tools'}


def test_fetch_project_map_pagination(monkeypatch):
    responses = [
        _mock_response([{'conversation_id': 'conv-1'}], next_cursor='abc'),
        _mock_response([{'conversation_id': 'conv-2'}], next_cursor=None),
    ]
    mock_get = MagicMock(side_effect=responses)
    monkeypatch.setattr(project_fetcher.requests, 'get', mock_get)

    result = project_fetcher.fetch_project_map(
        token='tok',
        projects={'g-p-aaa': 'Tools'},
    )
    assert result == {'conv-1': 'Tools', 'conv-2': 'Tools'}
    assert mock_get.call_count == 2
    # Second call should pass cursor=abc
    _, kwargs = mock_get.call_args_list[1]
    assert kwargs['params']['cursor'] == 'abc'


def test_fetch_project_map_multiple_projects(monkeypatch):
    def mock_get(url, **kwargs):
        if 'g-p-aaa' in url:
            return _mock_response([{'conversation_id': 'conv-a'}])
        else:
            return _mock_response([{'conversation_id': 'conv-b'}])
    monkeypatch.setattr(project_fetcher.requests, 'get', mock_get)

    result = project_fetcher.fetch_project_map(
        token='tok',
        projects={'g-p-aaa': 'Tools', 'g-p-bbb': 'Scripts'},
    )
    assert result['conv-a'] == 'Tools'
    assert result['conv-b'] == 'Scripts'


def test_fetch_project_map_empty_projects():
    result = project_fetcher.fetch_project_map(token='tok', projects={})
    assert result == {}


def test_fetch_project_map_calls_progress_cb(monkeypatch):
    monkeypatch.setattr(
        project_fetcher.requests, 'get',
        MagicMock(return_value=_mock_response([
            {'conversation_id': 'conv-1'},
            {'conversation_id': 'conv-2'},
        ])),
    )
    calls = []
    project_fetcher.fetch_project_map(
        token='tok',
        projects={'g-p-aaa': 'Tools'},
        progress_cb=lambda name, count: calls.append((name, count)),
    )
    assert calls == [('Tools', 2)]


def test_fetch_project_map_stops_on_empty_items(monkeypatch):
    """Empty items list should stop pagination even if cursor present."""
    responses = [
        _mock_response([], next_cursor='orphan-cursor'),
    ]
    monkeypatch.setattr(project_fetcher.requests, 'get', MagicMock(side_effect=responses))
    result = project_fetcher.fetch_project_map(token='tok', projects={'g-p-aaa': 'Tools'})
    assert result == {}
