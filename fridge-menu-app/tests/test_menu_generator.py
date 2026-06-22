"""menu_generator.pyのユニットテスト"""
import pytest
from unittest.mock import MagicMock, patch

from services.menu_generator import generate_menu_stream


# --- 正常系 ---

def test_generate_menu_stream_yields_text(mock_stream_response):
    """通常の食材入力でテキストチャンクが返ること"""
    with patch("services.menu_generator.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.stream.return_value.__enter__ = lambda s: mock_stream_response
        MockClient.return_value.messages.stream.return_value.__exit__ = MagicMock(return_value=False)

        result = list(generate_menu_stream("卵、玉ねぎ、鶏肉"))
        assert len(result) > 0
        assert any(isinstance(chunk, str) for chunk in result)


def test_generate_menu_stream_multiple_ingredients(mock_stream_response):
    """複数食材でもエラーなく動作すること"""
    with patch("services.menu_generator.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.stream.return_value.__enter__ = lambda s: mock_stream_response
        MockClient.return_value.messages.stream.return_value.__exit__ = MagicMock(return_value=False)

        result = list(generate_menu_stream("卵、玉ねぎ、にんじん、じゃがいも、豚肉、醤油、みりん、酒、砂糖"))
        assert result is not None


# --- 異常系 ---

def test_generate_menu_stream_empty_string_raises():
    """空文字を渡すとValueErrorが発生すること"""
    with pytest.raises(ValueError, match="食材が入力されていません"):
        list(generate_menu_stream(""))


def test_generate_menu_stream_whitespace_only_raises():
    """空白のみの入力でValueErrorが発生すること"""
    with pytest.raises(ValueError, match="食材が入力されていません"):
        list(generate_menu_stream("   "))


# --- 境界値 ---

def test_generate_menu_stream_single_ingredient(mock_stream_response):
    """食材が1つだけでも動作すること"""
    with patch("services.menu_generator.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.stream.return_value.__enter__ = lambda s: mock_stream_response
        MockClient.return_value.messages.stream.return_value.__exit__ = MagicMock(return_value=False)

        result = list(generate_menu_stream("卵"))
        assert result is not None


# --- フィクスチャ ---

@pytest.fixture
def mock_stream_response():
    """Claude APIのストリームレスポンスをモックする"""
    mock = MagicMock()
    mock.text_stream = iter(["親子丼がおすすめです。", "卵と鶏肉を使います。"])
    return mock
