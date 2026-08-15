"""learner.py のユニットテスト"""

import json
import os
import sqlite3
import tempfile

import pytest

# テスト用にDB_PATHを一時ファイルに差し替え
import config

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
config.DB_PATH = type(config.DB_PATH)(_tmp.name)
_tmp.close()

from engine.learner import (
    get_all_results,
    get_form_cache,
    get_stats,
    init_db,
    save_form_cache,
    save_result,
)


@pytest.fixture(autouse=True)
def setup_db():
    """各テスト前にDBを初期化する"""
    # テーブルを削除して再作成
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.execute("DROP TABLE IF EXISTS send_results")
    conn.execute("DROP TABLE IF EXISTS form_cache")
    conn.commit()
    conn.close()
    init_db()
    yield


class TestSaveAndGetResults:
    """送信結果の保存・取得テスト"""

    def test_save_and_retrieve(self) -> None:
        """正常系：保存した結果が取得できる"""
        save_result("テスト株式会社", "https://example.com", "success")
        results = get_all_results()
        assert len(results) == 1
        assert results[0]["company_name"] == "テスト株式会社"
        assert results[0]["status"] == "success"

    def test_multiple_results(self) -> None:
        """正常系：複数件の保存"""
        save_result("A社", "https://a.com", "success")
        save_result("B社", "https://b.com", "error", "タイムアウト")
        results = get_all_results()
        assert len(results) == 2

    def test_error_detail_saved(self) -> None:
        """正常系：エラー詳細が保存される"""
        save_result("C社", "https://c.com", "error", "フォームなし")
        results = get_all_results()
        assert results[0]["error_detail"] == "フォームなし"


class TestFormCache:
    """フォームキャッシュのテスト"""

    def test_save_and_get_cache(self) -> None:
        """正常系：キャッシュの保存と取得"""
        mapping = {"email": {"name": "email", "tag": "input"}}
        save_form_cache("example.com", "https://example.com/contact", mapping, True)

        cache = get_form_cache("example.com")
        assert cache is not None
        assert cache["success_count"] == 1
        assert cache["field_mapping"]["email"]["name"] == "email"

    def test_cache_miss(self) -> None:
        """正常系：未キャッシュのドメイン"""
        assert get_form_cache("unknown.com") is None

    def test_cache_update_counts(self) -> None:
        """正常系：成功/失敗カウントが加算される"""
        mapping = {"email": {"name": "mail"}}
        save_form_cache("test.com", "https://test.com", mapping, True)
        save_form_cache("test.com", "https://test.com", mapping, False)

        cache = get_form_cache("test.com")
        assert cache["success_count"] == 1
        assert cache["fail_count"] == 1


class TestStats:
    """統計情報のテスト"""

    def test_empty_stats(self) -> None:
        """境界値：データなしの統計"""
        stats = get_stats()
        assert stats["total"] == 0
        assert stats["success_rate"] == 0

    def test_stats_with_data(self) -> None:
        """正常系：データありの統計"""
        save_result("A社", "https://a.com", "success")
        save_result("B社", "https://b.com", "success")
        save_result("C社", "https://c.com", "error")

        stats = get_stats()
        assert stats["total"] == 3
        assert stats["success"] == 2
        assert abs(stats["success_rate"] - 66.7) < 1


def teardown_module():
    """テスト後にDBファイルを削除する"""
    try:
        os.unlink(str(config.DB_PATH))
    except OSError:
        pass
