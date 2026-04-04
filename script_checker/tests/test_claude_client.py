"""claude_client のユニットテスト（API呼び出しはモック）"""

import json
import pytest

from services.claude_client import _strip_code_fence


class TestStripCodeFence:
    """コードブロック除去のテスト"""

    def test_json_with_fence(self) -> None:
        """正常系：```json ... ``` が除去される"""
        text = '```json\n{"key": "value"}\n```'
        result = _strip_code_fence(text)
        assert result == '{"key": "value"}'

    def test_plain_json(self) -> None:
        """正常系：コードブロックなしはそのまま返る"""
        text = '{"key": "value"}'
        result = _strip_code_fence(text)
        assert result == '{"key": "value"}'

    def test_fence_with_language(self) -> None:
        """正常系：```python など言語指定つきでも除去される"""
        text = '```python\nprint("hello")\n```'
        result = _strip_code_fence(text)
        assert result == 'print("hello")'

    def test_empty_string(self) -> None:
        """境界値：空文字列"""
        assert _strip_code_fence("") == ""

    def test_only_backticks(self) -> None:
        """異常系：バッククォートのみ"""
        result = _strip_code_fence("```\n```")
        assert result == ""

    def test_nested_backticks_preserved(self) -> None:
        """正常系：内部のバッククォートは保持される"""
        text = '```\ncode with `backtick` inside\n```'
        result = _strip_code_fence(text)
        assert "`backtick`" in result

    def test_whitespace_trimmed(self) -> None:
        """正常系：前後の空白が除去される"""
        text = '  \n```json\n{"a": 1}\n```\n  '
        result = _strip_code_fence(text)
        parsed = json.loads(result)
        assert parsed == {"a": 1}
