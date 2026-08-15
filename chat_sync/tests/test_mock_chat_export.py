"""mock_chat_export.py のユニットテスト。

pytestのtmp_pathで一時ディレクトリを使用し、ファイルI/Oをテストする。
"""

from pathlib import Path

import pytest

from chat_sync import mock_chat_export


@pytest.fixture
def temp_chat_logs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """CHAT_LOGS_DIRを一時ディレクトリに差し替えるフィクスチャ。"""
    temp_dir = tmp_path / "chat_logs"
    monkeypatch.setattr(mock_chat_export, "CHAT_LOGS_DIR", temp_dir)
    return temp_dir


def test_generate_mock_chat_data() -> None:
    """正常系: ダミーチャットデータが期待通りに生成される。"""
    data = mock_chat_export.generate_mock_chat_data()

    assert len(data) == 4  # 4件のダミーメッセージ
    assert data[0]["speaker"] == "User"
    assert data[1]["speaker"] == "Claude"
    assert all("timestamp" in msg and "speaker" in msg and "content" in msg for msg in data)


def test_format_chat_to_markdown() -> None:
    """正常系: チャットデータがMarkdown形式に正しく変換される。"""
    mock_data = [
        {"timestamp": "10:00", "speaker": "User", "content": "こんにちは"},
        {"timestamp": "10:01", "speaker": "Claude", "content": "こんにちは。どうお手伝いしましょうか？"},
    ]

    markdown = mock_chat_export.format_chat_to_markdown(mock_data)

    assert "# Chat Export:" in markdown
    assert "## 10:00 - User" in markdown
    assert "こんにちは" in markdown
    assert "## 10:01 - Claude" in markdown


def test_export_mock_chat_creates_file(temp_chat_logs_dir: Path) -> None:
    """正常系: export_mock_chat()がファイルを作成する。"""
    file_path = mock_chat_export.export_mock_chat()

    assert file_path.exists()
    content = file_path.read_text(encoding="utf-8")
    assert "# Chat Export:" in content
    assert "User" in content
    assert "Claude" in content


def test_export_mock_chat_raises_oserror_on_invalid_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """異常系: ディレクトリ作成不可な場所を指定するとOSErrorを送出する。"""
    blocking_file = tmp_path / "blocked"
    blocking_file.write_text("dummy", encoding="utf-8")
    invalid_chat_logs_dir = blocking_file / "chat_logs"
    monkeypatch.setattr(mock_chat_export, "CHAT_LOGS_DIR", invalid_chat_logs_dir)

    with pytest.raises(OSError):
        mock_chat_export.export_mock_chat()


def test_format_chat_to_markdown_empty_list() -> None:
    """異常系: 空のチャットリストでもエラーなく処理される。"""
    markdown = mock_chat_export.format_chat_to_markdown([])

    assert "# Chat Export:" in markdown
    # 空リストなので、ヘッダーだけが出力される
    assert markdown.count("##") == 0
