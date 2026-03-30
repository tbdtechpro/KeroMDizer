import json
from unittest.mock import MagicMock
import pytest
import requests as req
from curl_cffi.requests.exceptions import HTTPError as _CurlHTTPError
import project_fetcher


# ── helpers ───────────────────────────────────────────────────────────────────

def _ok_response(items: list[dict] | None = None, next_cursor=None) -> MagicMock:
    """Build a successful mock requests.Response."""
    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    if items is not None:
        resp.json.return_value = {'items': items, 'cursor': next_cursor}
    else:
        resp.json.return_value = {}
    return resp


def _err_response(status: int, body: dict | None = None) -> MagicMock:
    """Build a failing mock requests.Response that raises on raise_for_status."""
    resp = MagicMock()
    resp.ok = False
    resp.status_code = status
    resp.text = json.dumps(body) if body else ''
    resp.json.return_value = body or {}
    http_err = _CurlHTTPError(f'HTTP {status}', response=resp)
    resp.raise_for_status.side_effect = http_err
    return resp


def _patch_get(monkeypatch, responses):
    """Monkeypatch requests.get with a side_effect list (validate_token is first)."""
    mock_get = MagicMock(side_effect=responses)
    monkeypatch.setattr(project_fetcher.requests, 'get', mock_get)
    return mock_get


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


# ── validate_token ────────────────────────────────────────────────────────────

def test_validate_token_returns_none_on_success(monkeypatch):
    monkeypatch.setattr(project_fetcher.requests, 'get', MagicMock(return_value=_ok_response()))
    assert project_fetcher.validate_token('tok') is None


def test_validate_token_returns_error_on_401(monkeypatch):
    resp = MagicMock()
    resp.ok = True  # we check status_code explicitly before raise_for_status
    resp.status_code = 401
    resp.raise_for_status = MagicMock()
    monkeypatch.setattr(project_fetcher.requests, 'get', MagicMock(return_value=resp))
    err = project_fetcher.validate_token('tok')
    assert err is not None
    assert '401' in err


def test_validate_token_returns_error_on_403(monkeypatch):
    resp = MagicMock()
    resp.ok = False
    resp.status_code = 403
    resp.json.return_value = {'detail': 'Forbidden by policy'}
    resp.raise_for_status = MagicMock()
    monkeypatch.setattr(project_fetcher.requests, 'get', MagicMock(return_value=resp))
    err = project_fetcher.validate_token('tok')
    assert err is not None
    assert '403' in err
    assert 'Forbidden by policy' in err


def test_validate_token_returns_error_on_network_failure(monkeypatch):
    from curl_cffi.requests.exceptions import ConnectionError as _CurlConnError
    monkeypatch.setattr(
        project_fetcher.requests, 'get',
        MagicMock(side_effect=_CurlConnError('no route')),
    )
    err = project_fetcher.validate_token('tok')
    assert err is not None
    assert 'Network error' in err


# ── fetch_project_map ─────────────────────────────────────────────────────────

def test_fetch_project_map_single_page(monkeypatch):
    _patch_get(monkeypatch, [
        _ok_response([{'conversation_id': 'conv-1'}, {'conversation_id': 'conv-2'}]),
    ])
    result, skipped = project_fetcher.fetch_project_map(
        token='tok',
        projects={'g-p-aaa': 'Tools'},
    )
    assert result == {'conv-1': 'Tools', 'conv-2': 'Tools'}
    assert skipped == 0


def test_fetch_project_map_pagination(monkeypatch):
    mock_get = _patch_get(monkeypatch, [
        _ok_response([{'conversation_id': 'conv-1'}], next_cursor='abc'),
        _ok_response([{'conversation_id': 'conv-2'}]),
    ])
    result, skipped = project_fetcher.fetch_project_map(
        token='tok',
        projects={'g-p-aaa': 'Tools'},
    )
    assert result == {'conv-1': 'Tools', 'conv-2': 'Tools'}
    assert skipped == 0
    assert mock_get.call_count == 2
    assert mock_get.call_args_list[0].kwargs['params']['cursor'] == '0'
    assert mock_get.call_args_list[1].kwargs['params']['cursor'] == 'abc'


def test_fetch_project_map_stops_on_repeated_cursor(monkeypatch):
    """If API echoes back the same cursor, pagination must stop (no infinite loop)."""
    _patch_get(monkeypatch, [
        _ok_response([{'conversation_id': 'conv-1'}], next_cursor='stuck'),
        _ok_response([{'conversation_id': 'conv-2'}], next_cursor='stuck'),
    ])
    result, _ = project_fetcher.fetch_project_map(token='tok', projects={'g-p-aaa': 'Tools'})
    assert 'conv-1' in result


def test_fetch_project_map_multiple_projects(monkeypatch):
    def mock_get(url, **kwargs):
        if 'g-p-aaa' in url:
            return _ok_response([{'conversation_id': 'conv-a'}])
        return _ok_response([{'conversation_id': 'conv-b'}])

    monkeypatch.setattr(project_fetcher.requests, 'get', mock_get)

    result, skipped = project_fetcher.fetch_project_map(
        token='tok',
        projects={'g-p-aaa': 'Tools', 'g-p-bbb': 'Scripts'},
    )
    assert result['conv-a'] == 'Tools'
    assert result['conv-b'] == 'Scripts'
    assert skipped == 0


def test_fetch_project_map_empty_projects():
    result, skipped = project_fetcher.fetch_project_map(token='tok', projects={})
    assert result == {}
    assert skipped == 0


def test_fetch_project_map_calls_progress_cb(monkeypatch):
    _patch_get(monkeypatch, [
        _ok_response([{'conversation_id': 'conv-1'}, {'conversation_id': 'conv-2'}]),
    ])
    calls = []
    project_fetcher.fetch_project_map(
        token='tok',
        projects={'g-p-aaa': 'Tools'},
        progress_cb=lambda name, count: calls.append((name, count)),
    )
    assert calls == [('Tools', 2)]


def test_fetch_project_map_stops_on_empty_items(monkeypatch):
    """Empty items list should stop pagination even if cursor present."""
    _patch_get(monkeypatch, [
        _ok_response([], next_cursor='orphan-cursor'),
    ])
    result, skipped = project_fetcher.fetch_project_map(token='tok', projects={'g-p-aaa': 'Tools'})
    assert result == {}
    assert skipped == 0


def test_fetch_project_map_skips_403(monkeypatch):
    """A 403 on one gizmo should be skipped; others continue."""
    def mock_get(url, **kwargs):
        if 'g-p-bad' in url:
            return _err_response(403)
        return _ok_response([{'conversation_id': 'conv-ok'}])

    monkeypatch.setattr(project_fetcher.requests, 'get', mock_get)

    result, skipped = project_fetcher.fetch_project_map(
        token='tok',
        projects={'g-p-bad': 'Forbidden', 'g-p-ok': 'Works'},
    )
    assert skipped == 1
    assert 'conv-ok' in result
    assert result['conv-ok'] == 'Works'


