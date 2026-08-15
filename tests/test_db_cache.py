"""テスト - utils/db_cache.py
正常系2・異常系2・境界値1 を各関数で満たす
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

# テスト用にDB_PATHを一時ファイルに差し替え
import utils.db as db_module

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
db_module.DB_PATH = Path(_tmp.name)
_tmp.close()

from utils.db import init_db
from utils.db_cache import (
    cleanup_stale_cache,
    delete_form_cache,
    get_cache_stats,
    get_form_cache,
    is_cache_reliable,
    save_form_cache,
)


@pytest.fixture(autouse=True)
def setup_db():
    """各テスト前にDBを初期化する"""
    conn = sqlite3.connect(str(db_module.DB_PATH))
    conn.execute("DROP TABLE IF EXISTS form_cache")
    conn.commit()
    conn.close()
    init_db()
    yield


# === get_form_cache: 正常系2 + 異常系2 + 境界値1 ===

class TestGetFormCache:

    def test_returns_none_for_unknown(self):
        """正常系: 未登録ドメインはNone"""
        assert get_form_cache("unknown.com") is None

    def test_returns_dict_after_save(self):
        """正常系: 保存後に正しいdictが返る"""
        mapping = {"email": {"name": "mail", "tag": "input"}}
        save_form_cache("example.com", "https://example.com/contact", mapping, True)
        cache = get_form_cache("example.com")
        assert cache is not None
        assert cache["field_mapping"]["email"]["name"] == "mail"
        assert cache["success_count"] == 1

    def test_empty_domain_returns_none(self):
        """異常系: 空文字ドメインはNone"""
        assert get_form_cache("") is None

    def test_mapping_is_dict_not_string(self):
        """異常系確認: field_mappingはJSON文字列ではなくdict"""
        mapping = {"message": {"name": "body"}}
        save_form_cache("test.com", "https://test.com", mapping, True)
        cache = get_form_cache("test.com")
        assert isinstance(cache["field_mapping"], dict)

    def test_subdomain_separated(self):
        """境界値: サブドメイン違いは別キャッシュ"""
        mapping_a = {"email": {"name": "a"}}
        mapping_b = {"email": {"name": "b"}}
        save_form_cache("www.example.com", "https://www.example.com", mapping_a, True)
        save_form_cache("mail.example.com", "https://mail.example.com", mapping_b, True)
        assert get_form_cache("www.example.com")["field_mapping"]["email"]["name"] == "a"
        assert get_form_cache("mail.example.com")["field_mapping"]["email"]["name"] == "b"


# === save_form_cache: 正常系2 + 異常系2 + 境界値1 ===

class TestSaveFormCache:

    def test_success_increments_count(self):
        """正常系: 成功保存でsuccess_countが増える"""
        mapping = {"email": {"name": "mail"}}
        save_form_cache("a.com", "https://a.com", mapping, True)
        save_form_cache("a.com", "https://a.com", mapping, True)
        cache = get_form_cache("a.com")
        assert cache["success_count"] == 2
        assert cache["fail_count"] == 0

    def test_failure_increments_count(self):
        """正常系: 失敗保存でfail_countが増える"""
        mapping = {"email": {"name": "mail"}}
        save_form_cache("b.com", "https://b.com", mapping, False)
        cache = get_form_cache("b.com")
        assert cache["fail_count"] == 1
        assert cache["last_status"] == "fail"

    def test_empty_mapping_saved(self):
        """異常系: 空mappingでもエラーにならない"""
        save_form_cache("c.com", "https://c.com", {}, True)
        cache = get_form_cache("c.com")
        assert cache["field_mapping"] == {}

    def test_failure_does_not_overwrite_mapping(self):
        """異常系確認: 失敗時にmappingが上書きされない"""
        good = {"email": {"name": "good_mail"}}
        bad = {"email": {"name": "bad_mail"}}
        save_form_cache("d.com", "https://d.com", good, True)
        save_form_cache("d.com", "https://d.com", bad, False)
        cache = get_form_cache("d.com")
        # 成功時のマッピングが保持される
        assert cache["field_mapping"]["email"]["name"] == "good_mail"

    def test_alternating_success_fail(self):
        """境界値: 成功・失敗交互でカウント正確"""
        m = {"email": {"name": "m"}}
        save_form_cache("e.com", "https://e.com", m, True)
        save_form_cache("e.com", "https://e.com", m, False)
        save_form_cache("e.com", "https://e.com", m, True)
        save_form_cache("e.com", "https://e.com", m, False)
        save_form_cache("e.com", "https://e.com", m, True)
        cache = get_form_cache("e.com")
        assert cache["success_count"] == 3
        assert cache["fail_count"] == 2


# === is_cache_reliable: 正常系2 + 異常系2 + 境界値1 ===

class TestIsCacheReliable:

    def test_high_success_reliable(self):
        """正常系: 成功5回・失敗0回は信頼できる"""
        cache = {"success_count": 5, "fail_count": 0}
        assert is_cache_reliable(cache) is True

    def test_moderate_success_reliable(self):
        """正常系: 成功3回・失敗1回（失敗率25%）は信頼できる"""
        cache = {"success_count": 3, "fail_count": 1}
        assert is_cache_reliable(cache) is True

    def test_zero_success_unreliable(self):
        """異常系: 成功0回は信頼できない"""
        cache = {"success_count": 0, "fail_count": 0}
        assert is_cache_reliable(cache) is False

    def test_high_fail_ratio_unreliable(self):
        """異常系: 成功3回・失敗3回（失敗率50%）は信頼できない"""
        cache = {"success_count": 3, "fail_count": 3}
        assert is_cache_reliable(cache) is False

    def test_boundary_just_below_threshold(self):
        """境界値: 成功2回は最低ライン未達（デフォルトmin_success=3）"""
        cache = {"success_count": 2, "fail_count": 0}
        assert is_cache_reliable(cache) is False


# === get_cache_stats: 正常系2 + 異常系2 + 境界値1 ===

class TestGetCacheStats:

    def test_empty_db(self):
        """正常系: 空DBはゼロ"""
        stats = get_cache_stats()
        assert stats["total_cached"] == 0
        assert stats["reliable_count"] == 0

    def test_counts_reliable(self):
        """正常系: 信頼できるキャッシュをカウント"""
        m = {"email": {"name": "m"}}
        # 信頼できる: 3回成功
        for _ in range(3):
            save_form_cache("good.com", "https://good.com", m, True)
        # 信頼できない: 1回のみ
        save_form_cache("new.com", "https://new.com", m, True)

        stats = get_cache_stats()
        assert stats["total_cached"] == 2
        assert stats["reliable_count"] == 1

    def test_all_unreliable(self):
        """異常系: 全て信頼できない場合"""
        m = {"email": {"name": "m"}}
        save_form_cache("x.com", "https://x.com", m, False)
        stats = get_cache_stats()
        assert stats["total_cached"] == 1
        assert stats["reliable_count"] == 0

    def test_mixed_entries(self):
        """異常系: 混合エントリの正確なカウント"""
        m = {"email": {"name": "m"}}
        # 信頼できる2件
        for d in ["a.com", "b.com"]:
            for _ in range(3):
                save_form_cache(d, f"https://{d}", m, True)
        # 信頼できない1件
        save_form_cache("c.com", "https://c.com", m, True)

        stats = get_cache_stats()
        assert stats["total_cached"] == 3
        assert stats["reliable_count"] == 2

    def test_single_reliable_entry(self):
        """境界値: 1件のみで信頼できる"""
        m = {"email": {"name": "m"}}
        for _ in range(3):
            save_form_cache("only.com", "https://only.com", m, True)
        stats = get_cache_stats()
        assert stats["total_cached"] == 1
        assert stats["reliable_count"] == 1


# === delete_form_cache: 正常系2 + 異常系2 + 境界値1 ===

class TestDeleteFormCache:

    def test_delete_existing(self):
        """正常系: 既存エントリを削除"""
        save_form_cache("del.com", "https://del.com", {}, True)
        delete_form_cache("del.com")
        assert get_form_cache("del.com") is None

    def test_other_entries_preserved(self):
        """正常系: 他のエントリは影響なし"""
        save_form_cache("keep.com", "https://keep.com", {}, True)
        save_form_cache("del.com", "https://del.com", {}, True)
        delete_form_cache("del.com")
        assert get_form_cache("keep.com") is not None

    def test_delete_nonexistent(self):
        """異常系: 存在しないドメインでもエラーにならない"""
        delete_form_cache("nonexistent.com")  # エラーなし

    def test_double_delete(self):
        """異常系: 二重削除でもエラーにならない"""
        save_form_cache("dd.com", "https://dd.com", {}, True)
        delete_form_cache("dd.com")
        delete_form_cache("dd.com")  # エラーなし

    def test_delete_one_of_many(self):
        """境界値: 複数中の1件だけ削除"""
        for i in range(5):
            save_form_cache(f"s{i}.com", f"https://s{i}.com", {}, True)
        delete_form_cache("s2.com")
        assert get_form_cache("s2.com") is None
        assert get_form_cache("s0.com") is not None
        assert get_form_cache("s4.com") is not None


# === cleanup_stale_cache: 正常系2 + 異常系2 + 境界値1 ===

class TestCleanupStaleCache:

    def test_no_stale_returns_zero(self):
        """正常系: 古いエントリなしなら0件"""
        save_form_cache("fresh.com", "https://fresh.com", {}, True)
        assert cleanup_stale_cache(days=180) == 0

    def test_recent_preserved(self):
        """正常系: 最近のエントリは削除されない"""
        save_form_cache("new.com", "https://new.com", {}, False)
        cleanup_stale_cache(days=180)
        assert get_form_cache("new.com") is not None

    def test_empty_db_no_error(self):
        """異常系: 空DBでもエラーにならない"""
        assert cleanup_stale_cache(days=1) == 0

    def test_returns_int(self):
        """異常系確認: 戻り値はint型"""
        result = cleanup_stale_cache(days=180)
        assert isinstance(result, int)

    def test_success_entries_not_deleted(self):
        """境界値: 成功実績ありのエントリは古くても削除されない"""
        # 成功実績ありは対象外（success_count > 0）
        save_form_cache("old.com", "https://old.com", {}, True)
        # days=0 → 全てが「古い」扱いになるが成功実績ありなら残る
        deleted = cleanup_stale_cache(days=0)
        assert deleted == 0
        assert get_form_cache("old.com") is not None


def teardown_module():
    """テスト後にDBファイルを削除する"""
    import os
    try:
        os.unlink(str(db_module.DB_PATH))
    except OSError:
        pass
