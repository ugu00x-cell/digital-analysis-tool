"""file_helper.py のユニットテスト。

pytestのtmp_pathフィクスチャでtasks/ディレクトリを一時的に差し替えてテストする。
"""

from pathlib import Path

import pytest

from voice_tasklist.utils import file_helper


@pytest.fixture
def temp_tasks_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """TASKS_DIRを一時ディレクトリに差し替えるフィクスチャ。"""
    temp_dir = tmp_path / "tasks"
    monkeypatch.setattr(file_helper, "TASKS_DIR", temp_dir)
    return temp_dir


def test_append_task_creates_file_with_heading(temp_tasks_dir: Path) -> None:
    """正常系: 初回追記時にファイルが見出し付きで新規作成される。"""
    file_path = file_helper.append_task("牛乳を買う")

    assert file_path.exists()
    content = file_path.read_text(encoding="utf-8")
    assert "タスク一覧" in content
    assert "牛乳を買う" in content


def test_append_task_appends_multiple_lines(temp_tasks_dir: Path) -> None:
    """正常系: 複数回呼び出すと行が追記されていく。"""
    file_helper.append_task("タスクA")
    file_path = file_helper.append_task("タスクB")

    content = file_path.read_text(encoding="utf-8")
    assert content.count("- [ ]") == 2
    assert "タスクA" in content
    assert "タスクB" in content


def test_append_task_raises_oserror_on_invalid_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """異常系: ディレクトリ作成不可な場所を指定するとOSErrorを送出する。

    既存のファイルをディレクトリパスとして扱わせることで
    mkdir失敗（NotADirectoryError系のOSError）を再現する。
    """
    blocking_file = tmp_path / "blocked"
    blocking_file.write_text("dummy", encoding="utf-8")
    invalid_tasks_dir = blocking_file / "tasks"
    monkeypatch.setattr(file_helper, "TASKS_DIR", invalid_tasks_dir)

    with pytest.raises(OSError):
        file_helper.append_task("エラーになるはずのタスク")


def test_append_task_empty_string(temp_tasks_dir: Path) -> None:
    """異常系: 空文字のタスクでも例外を出さず、空行として記録される。"""
    file_path = file_helper.append_task("")

    content = file_path.read_text(encoding="utf-8")
    assert "- [ ] (" in content


def test_get_today_task_file_path_format(temp_tasks_dir: Path) -> None:
    """境界値: ファイル名がYYYY-MM-DD.mdの形式になっている。"""
    file_path = file_helper.get_today_task_file_path()

    assert file_path.suffix == ".md"
    # YYYY-MM-DD は10文字（ハイフン2つ含む）
    assert len(file_path.stem) == 10
    assert file_path.stem.count("-") == 2
