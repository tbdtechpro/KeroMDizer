import json
import pytest
from pathlib import Path
from parser_factory import detect_source, build_parser


def test_detect_source_deepseek(tmp_path):
    """user.json with 'mobile' field → 'deepseek'."""
    user_json = tmp_path / 'user.json'
    user_json.write_text(json.dumps({
        "user_id": "abc", "email": "x@y.com", "mobile": None, "oauth_profiles": None
    }), encoding='utf-8')
    assert detect_source(tmp_path) == 'deepseek'


def test_detect_source_chatgpt_no_user_json(tmp_path):
    """No user.json → 'chatgpt'."""
    assert detect_source(tmp_path) == 'chatgpt'


def test_detect_source_chatgpt_no_mobile_field(tmp_path):
    """user.json without 'mobile' field → 'chatgpt'."""
    user_json = tmp_path / 'user.json'
    user_json.write_text(json.dumps({"user_id": "abc"}), encoding='utf-8')
    assert detect_source(tmp_path) == 'chatgpt'


def test_build_parser_returns_deepseek_parser(tmp_path):
    """build_parser with deepseek source returns DeepSeekParser instance."""
    from deepseek_parser import DeepSeekParser
    parser, provider = build_parser(tmp_path, source='deepseek')
    assert isinstance(parser, DeepSeekParser)


def test_build_parser_source_override(tmp_path):
    """Explicit source='chatgpt' overrides even if user.json has 'mobile'."""
    from conversation_parser import ConversationParser
    from deepseek_parser import DeepSeekParser
    user_json = tmp_path / 'user.json'
    user_json.write_text(json.dumps({"mobile": None}), encoding='utf-8')
    parser, provider = build_parser(tmp_path, source='chatgpt')
    assert isinstance(parser, ConversationParser)
    assert not isinstance(parser, DeepSeekParser)
    assert provider == 'chatgpt'


def test_build_parser_returns_provider_string(tmp_path):
    """build_parser returns tuple; second element is the provider string."""
    _, provider = build_parser(tmp_path, source='deepseek')
    assert provider == 'deepseek'
