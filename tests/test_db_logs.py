"""テスト - db_logs モジュール
正常系2・異常系2・境界値1 を各関数で満たす
"""

import pytest
from datetime import datetime

from utils.db import init_db
from utils.db_logs import (
    is_url_sent,
    mark_url_sent,
    get_sent_urls,
    save_log,
    get_logs,
    get_log_stats,
    get_setting,
    save_setting,
    is_domain_sent_today,
    cleanup_old_logs,
)


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """テスト用DBを一時ディレクトリに作成する"""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr("utils.db.DB_PATH", test_db)
    init_db()
    yield test_db


# === is_url_sent: 正常系2 + 異常系2 + 境界値1 ===

class TestIsUrlSent:

    def test_unsent_url(self):
        """正常系: 未送信URLはFalse"""
        assert is_url_sent("https://example.com") is False

    def test_sent_url(self):
        """正常系: 送信済みURLはTrue"""
        mark_url_sent("https://example.com", "success")
        assert is_url_sent("https://example.com") is True

    def test_empty_url(self):
        """異常系: 空文字URLはFalse"""
        assert is_url_sent("") is False

    def test_similar_url_not_matched(self):
        """異常系: 類似URLは別扱い"""
        mark_url_sent("https://example.com/a", "success")
        assert is_url_sent("https://example.com/b") is False

    def test_exact_match_required(self):
        """境界値: 完全一致のみTrue"""
        mark_url_sent("https://example.com", "success")
        assert is_url_sent("https://example.com/") is False


# === mark_url_sent: 正常系2 + 異常系2 + 境界値1 ===

class TestMarkUrlSent:

    def test_mark_success(self):
        """正常系: success状態で記録"""
        mark_url_sent("https://a.com", "success")
        assert is_url_sent("https://a.com") is True

    def test_mark_error(self):
        """正常系: error状態でも記録される"""
        mark_url_sent("https://b.com", "error")
        assert is_url_sent("https://b.com") is True

    def test_overwrite_status(self):
        """異常系: 同一URL再記録で上書き（REPLACE）"""
        mark_url_sent("https://c.com", "error")
        mark_url_sent("https://c.com", "success")
        urls = get_sent_urls()
        assert "https://c.com" in urls

    def test_mark_empty_url(self):
        """異常系: 空文字URLでもエラーにならない"""
        mark_url_sent("", "success")

    def test_mark_special_chars(self):
        """境界値: 特殊文字を含むURL"""
        url = "https://example.com/contact?q=テスト&lang=ja"
        mark_url_sent(url, "success")
        assert is_url_sent(url) is True


# === get_sent_urls: 正常系2 + 異常系2 + 境界値1 ===

class TestGetSentUrls:

    def test_empty_db(self):
        """正常系: 空DBでは空set"""
        assert get_sent_urls() == set()

    def test_multiple_urls(self):
        """正常系: 複数URLがsetで返る"""
        mark_url_sent("https://a.com", "success")
        mark_url_sent("https://b.com", "error")
        mark_url_sent("https://c.com", "success")
        urls = get_sent_urls()
        assert len(urls) == 3
        assert "https://b.com" in urls

    def test_returns_set_type(self):
        """異常系確認: 戻り値がset型"""
        result = get_sent_urls()
        assert isinstance(result, set)

    def test_no_duplicates(self):
        """異常系: 同一URL重複登録でもsetは1件"""
        mark_url_sent("https://x.com", "success")
        mark_url_sent("https://x.com", "error")
        assert len(get_sent_urls()) == 1

    def test_single_url(self):
        """境界値: 1件だけ"""
        mark_url_sent("https://only.com", "success")
        assert get_sent_urls() == {"https://only.com"}


# === save_log: 正常系2 + 異常系2 + 境界値1 ===

class TestSaveLog:

    def test_basic_log(self):
        """正常系: 基本ログ保存"""
        save_log("https://a.com", "A社", "success")
        logs = get_logs()
        assert len(logs) == 1
        assert logs[0]["company_name"] == "A社"

    def test_log_with_all_fields(self):
        """正常系: 全フィールド指定で保存"""
        save_log("https://b.com", "B社", "error",
                 error="timeout", retry=2, ai_used=True)
        log = get_logs()[0]
        assert log["error_reason"] == "timeout"
        assert log["retry_count"] == 2
        assert log["ai_used_flag"] == 1

    def test_empty_company_saves(self):
        """異常系: 企業名空文字でも保存"""
        save_log("https://c.com", "", "success")
        assert len(get_logs()) == 1

    def test_empty_url_saves(self):
        """異常系: URL空文字でも保存"""
        save_log("", "C社", "error")
        assert len(get_logs()) == 1

    def test_boundary_ai_flag_false(self):
        """境界値: ai_used=Falseの場合0が記録される"""
        save_log("https://d.com", "D社", "success", ai_used=False)
        log = get_logs()[0]
        assert log["ai_used_flag"] == 0


# === get_logs: 正常系2 + 異常系2 + 境界値1 ===

class TestGetLogs:

    def test_no_filter(self):
        """正常系: フィルターなしで全件取得"""
        save_log("https://a.com", "A", "success")
        save_log("https://b.com", "B", "error")
        assert len(get_logs()) == 2

    def test_filter_by_status(self):
        """正常系: ステータスフィルターで絞り込み"""
        save_log("https://a.com", "A", "success")
        save_log("https://b.com", "B", "error")
        save_log("https://c.com", "C", "success")
        assert len(get_logs("success")) == 2
        assert len(get_logs("error")) == 1

    def test_filter_no_match(self):
        """異常系: 該当なしフィルターでは空リスト"""
        save_log("https://a.com", "A", "success")
        assert get_logs("captcha") == []

    def test_empty_db(self):
        """異常系: 空DBでは空リスト"""
        assert get_logs() == []

    def test_order_newest_first(self):
        """境界値: 新しい順で返る"""
        save_log("https://first.com", "最初", "success")
        save_log("https://second.com", "2番目", "success")
        logs = get_logs()
        assert logs[0]["company_name"] == "2番目"


# === get_log_stats: 正常系2 + 異常系2 + 境界値1 ===

class TestGetLogStats:

    def test_basic_stats(self):
        """正常系: 基本統計"""
        save_log("https://a.com", "A", "success")
        save_log("https://b.com", "B", "success")
        save_log("https://c.com", "C", "error")
        stats = get_log_stats()
        assert stats["total"] == 3
        assert stats["success"] == 2

    def test_success_rate(self):
        """正常系: 成功率の計算"""
        save_log("https://a.com", "A", "success")
        save_log("https://b.com", "B", "error")
        stats = get_log_stats()
        assert stats["success_rate"] == pytest.approx(50.0, abs=0.1)

    def test_empty_stats(self):
        """異常系: 空DBの統計"""
        stats = get_log_stats()
        assert stats["total"] == 0
        assert stats["success_rate"] == 0
        assert stats["ai_rate"] == 0

    def test_ai_stats(self):
        """異常系確認: AI利用統計"""
        save_log("https://a.com", "A", "success", ai_used=True)
        save_log("https://b.com", "B", "error", ai_used=True)
        save_log("https://c.com", "C", "success", ai_used=False)
        stats = get_log_stats()
        assert stats["ai_used"] == 2
        assert stats["ai_success"] == 1
        assert stats["ai_rate"] == pytest.approx(50.0, abs=0.1)

    def test_by_status_dict(self):
        """境界値: by_statusがdict形式"""
        save_log("https://a.com", "A", "success")
        save_log("https://b.com", "B", "captcha")
        stats = get_log_stats()
        assert stats["by_status"]["success"] == 1
        assert stats["by_status"]["captcha"] == 1


# === get_setting / save_setting: 正常系2 + 異常系2 + 境界値1 ===

class TestSettings:

    def test_save_and_get(self):
        """正常系: 設定の保存と取得"""
        save_setting("test_key", "test_value")
        assert get_setting("test_key") == "test_value"

    def test_overwrite(self):
        """正常系: 上書き保存"""
        save_setting("key", "old")
        save_setting("key", "new")
        assert get_setting("key") == "new"

    def test_default_value(self):
        """異常系: 未設定キーはデフォルト値"""
        assert get_setting("nonexistent", "fallback") == "fallback"

    def test_empty_default(self):
        """異常系: デフォルト未指定は空文字"""
        assert get_setting("missing") == ""

    def test_boundary_empty_value(self):
        """境界値: 空文字を値として保存"""
        save_setting("blank", "")
        assert get_setting("blank", "default") == ""


# === is_domain_sent_today: 正常系2 + 異常系2 + 境界値1 ===

class TestIsDomainSentToday:

    def test_not_sent_today(self):
        """正常系: 今日送信していないドメインはFalse"""
        assert is_domain_sent_today("example.com") is False

    def test_sent_today(self):
        """正常系: 今日送信済みドメインはTrue"""
        save_log("https://example.com/contact", "テスト", "success")
        assert is_domain_sent_today("example.com") is True

    def test_different_domain_false(self):
        """異常系: 別ドメインはFalse"""
        save_log("https://a.com/contact", "A", "success")
        assert is_domain_sent_today("b.com") is False

    def test_error_status_not_counted(self):
        """異常系: errorステータスはカウントしない"""
        save_log("https://example.com/contact", "テスト", "error")
        assert is_domain_sent_today("example.com") is False

    def test_subdomain_partial_match(self):
        """境界値: サブドメイン含むURLでもドメイン部分で一致"""
        save_log("https://www.example.com/form", "テスト", "success")
        assert is_domain_sent_today("www.example.com") is True


# === cleanup_old_logs: 正常系2 + 異常系2 + 境界値1 ===

class TestCleanupOldLogs:

    def test_no_old_logs(self):
        """正常系: 古いログなしなら0件削除"""
        save_log("https://a.com", "A", "success")
        deleted = cleanup_old_logs()
        assert deleted == 0

    def test_recent_logs_kept(self):
        """正常系: 最近のログは削除されない"""
        for i in range(5):
            save_log(f"https://{i}.com", f"企業{i}", "success")
        cleanup_old_logs()
        assert len(get_logs()) == 5

    def test_empty_db_no_error(self):
        """異常系: 空DBでもエラーにならない"""
        deleted = cleanup_old_logs()
        assert deleted == 0

    def test_returns_int(self):
        """異常系確認: 戻り値はint型"""
        result = cleanup_old_logs()
        assert isinstance(result, int)

    def test_boundary_exactly_at_limit(self):
        """境界値: ちょうど保持期間内のログは残る"""
        save_log("https://boundary.com", "境界", "success")
        deleted = cleanup_old_logs()
        assert deleted == 0
        assert len(get_logs()) == 1
