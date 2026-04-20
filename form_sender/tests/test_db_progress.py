"""テスト - db_progress モジュール
正常系2・異常系2・境界値1 を各関数で満たす
"""

import pytest

from utils.db import init_db
from utils.db_progress import (
    create_session,
    update_progress,
    finish_session,
    get_incomplete_session,
    clear_sessions,
)


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """テスト用DBを一時ディレクトリに作成する"""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr("utils.db.DB_PATH", test_db)
    init_db()
    yield test_db


# === create_session: 正常系2 + 異常系2 + 境界値1 ===

class TestCreateSession:

    def test_returns_string_id(self):
        """正常系: 文字列のセッションIDが返る"""
        sid = create_session(100)
        assert isinstance(sid, str)
        assert len(sid) == 8

    def test_creates_running_session(self):
        """正常系: 作成直後はrunning＋index=0"""
        sid = create_session(50)
        session = get_incomplete_session()
        assert session is not None
        assert session["session_id"] == sid
        assert session["total"] == 50
        assert session["current_index"] == 0
        assert session["status"] == "running"

    def test_unique_ids(self):
        """異常系: 複数作成で異なるIDが生成される"""
        s1 = create_session(10)
        s2 = create_session(20)
        assert s1 != s2

    def test_zero_total(self):
        """異常系: total=0でもエラーにならない"""
        sid = create_session(0)
        assert isinstance(sid, str)

    def test_boundary_total_one(self):
        """境界値: total=1の最小セッション"""
        sid = create_session(1)
        session = get_incomplete_session()
        assert session["total"] == 1


# === update_progress: 正常系2 + 異常系2 + 境界値1 ===

class TestUpdateProgress:

    def test_update_midway(self):
        """正常系: 途中進捗の更新"""
        sid = create_session(10)
        update_progress(sid, 5)
        session = get_incomplete_session()
        assert session["current_index"] == 5

    def test_update_multiple_times(self):
        """正常系: 複数回更新で最新値が反映"""
        sid = create_session(10)
        update_progress(sid, 3)
        update_progress(sid, 7)
        session = get_incomplete_session()
        assert session["current_index"] == 7

    def test_update_nonexistent_session(self):
        """異常系: 存在しないセッションID更新でもエラーなし"""
        update_progress("nonexistent", 5)

    def test_update_after_finish(self):
        """異常系: 完了後の更新でもエラーなし（不整合だが壊れない）"""
        sid = create_session(10)
        finish_session(sid, "completed")
        update_progress(sid, 8)  # エラーにならないことを確認

    def test_boundary_update_to_total(self):
        """境界値: total値まで更新"""
        sid = create_session(3)
        update_progress(sid, 3)
        session = get_incomplete_session()
        assert session["current_index"] == 3


# === finish_session: 正常系2 + 異常系2 + 境界値1 ===

class TestFinishSession:

    def test_complete(self):
        """正常系: completedで終了→未完了セッションなし"""
        sid = create_session(10)
        finish_session(sid, "completed")
        assert get_incomplete_session() is None

    def test_paused(self):
        """正常系: pausedで終了→未完了セッションなし"""
        sid = create_session(10)
        finish_session(sid, "paused")
        assert get_incomplete_session() is None

    def test_cancelled(self):
        """異常系: cancelledステータス"""
        sid = create_session(10)
        finish_session(sid, "cancelled")
        assert get_incomplete_session() is None

    def test_finish_nonexistent(self):
        """異常系: 存在しないセッション終了でもエラーなし"""
        finish_session("nonexistent", "completed")

    def test_boundary_finish_immediately(self):
        """境界値: 作成直後に終了"""
        sid = create_session(100)
        finish_session(sid, "completed")
        assert get_incomplete_session() is None


# === get_incomplete_session: 正常系2 + 異常系2 + 境界値1 ===

class TestGetIncompleteSession:

    def test_returns_running_session(self):
        """正常系: runningセッションがあれば返す"""
        sid = create_session(50)
        result = get_incomplete_session()
        assert result is not None
        assert result["session_id"] == sid

    def test_returns_latest(self):
        """正常系: 複数runningがあれば最新を返す"""
        create_session(10)
        sid2 = create_session(20)
        result = get_incomplete_session()
        assert result["session_id"] == sid2

    def test_none_when_empty(self):
        """異常系: 空DBではNone"""
        assert get_incomplete_session() is None

    def test_none_when_all_completed(self):
        """異常系: 全完了済みならNone"""
        sid = create_session(10)
        finish_session(sid, "completed")
        assert get_incomplete_session() is None

    def test_returns_dict(self):
        """境界値: 戻り値がdict型で全フィールド含む"""
        create_session(5)
        result = get_incomplete_session()
        assert isinstance(result, dict)
        expected = {"session_id", "total", "current_index", "status", "started_at"}
        assert expected.issubset(result.keys())


# === clear_sessions: 正常系2 + 異常系2 + 境界値1 ===

class TestClearSessions:

    def test_clear_all_running(self):
        """正常系: running含む全セッション削除"""
        create_session(10)
        create_session(20)
        clear_sessions()
        assert get_incomplete_session() is None

    def test_clear_completed_too(self):
        """正常系: completed含めて全削除"""
        sid = create_session(10)
        finish_session(sid, "completed")
        create_session(20)
        clear_sessions()
        assert get_incomplete_session() is None

    def test_clear_empty_no_error(self):
        """異常系: 空DBでもエラーなし"""
        clear_sessions()

    def test_double_clear_no_error(self):
        """異常系: 二重クリアでもエラーなし"""
        create_session(10)
        clear_sessions()
        clear_sessions()

    def test_boundary_after_clear_can_create(self):
        """境界値: クリア後に新規セッション作成可能"""
        create_session(10)
        clear_sessions()
        sid = create_session(5)
        session = get_incomplete_session()
        assert session is not None
        assert session["total"] == 5
