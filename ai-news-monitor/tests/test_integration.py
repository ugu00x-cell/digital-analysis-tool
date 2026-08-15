"""
統合テスト（Integration Test）

各モジュールが連携して正常に動作することを確認。
外部API（X API、Slack）はモック化して依存なし実行。
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from services.collector.rss_scraper import fetch_rss_feeds
from services.notifier.slack_sender import format_news_item_for_slack, send_to_slack
from shared.database import Database
from shared.models import NewsItem


class TestDatabaseIntegration:
    """データベース統合テスト"""

    @pytest.fixture
    def temp_db(self):
        """一時的なテスト用データベース"""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        db = Database(db_path)
        yield db

        # クリーンアップ
        import os

        if os.path.exists(db_path):
            os.remove(db_path)

    def test_insert_and_retrieve_news_items(self, temp_db):
        """ニュースアイテムの挿入と取得"""
        items = [
            NewsItem(
                title="Article 1",
                source="rss",
                url="https://example.com/1",
                published_at=datetime(2026, 8, 15, 10, 0, 0),
                keywords=["AI"],
                raw_text="Test 1",
            ),
            NewsItem(
                title="Article 2",
                source="twitter",
                url="https://twitter.com/test/2",
                published_at=datetime(2026, 8, 15, 11, 0, 0),
                keywords=["LLM"],
                raw_text="Test 2",
            ),
        ]

        # 挿入
        success_count, error_count = temp_db.insert_news_items_batch(items)

        assert success_count == 2
        assert error_count == 0

        # 取得（過去24時間）
        retrieved = temp_db.get_news_items_since(hours=24)

        assert len(retrieved) == 2
        assert retrieved[0].title == "Article 2"  # 最新順

    def test_duplicate_prevention(self, temp_db):
        """重複防止機能テスト"""
        item = NewsItem(
            title="Duplicate Test",
            source="rss",
            url="https://example.com/duplicate",
            published_at=datetime(2026, 8, 15, 10, 0, 0),
            keywords=["test"],
            raw_text="Test",
        )

        # 1度目：成功
        id1 = temp_db.insert_news_item(item)
        assert id1 is not None

        # 2度目：重複なので None を返す
        id2 = temp_db.insert_news_item(item)
        assert id2 is None

        # DB には1件だけ
        retrieved = temp_db.get_news_items_since(hours=24)
        assert len(retrieved) == 1

    def test_notification_logging(self, temp_db):
        """通知履歴ログ機能テスト"""
        news_ids = [1, 2, 3]

        result = temp_db.log_notification(news_ids, status="sent")

        assert result is True


class TestCollectorToSlackWorkflow:
    """収集 → DB保存 → Slack通知 のワークフロー"""

    @pytest.fixture
    def sample_news_items(self):
        """サンプル ニュースアイテム"""
        return [
            NewsItem(
                title="Claude 3.5 Released",
                source="twitter",
                url="https://twitter.com/anthropic/1",
                published_at=datetime(2026, 8, 15, 10, 0, 0),
                keywords=["Claude", "API"],
                raw_text="Claude 3.5 Sonnet is now available",
                author="Anthropic",
            ),
            NewsItem(
                title="RAG Best Practices",
                source="rss",
                url="https://example.com/rag-guide",
                published_at=datetime(2026, 8, 15, 9, 0, 0),
                keywords=["RAG", "LLM"],
                raw_text="Guide to implementing RAG systems",
            ),
        ]

    def test_format_and_send_workflow(self, sample_news_items):
        """フォーマット → 送信 ワークフロー"""
        # フォーマット
        attachments = [
            format_news_item_for_slack(item) for item in sample_news_items
        ]

        assert len(attachments) == 2
        assert all(a["title"] for a in attachments)
        assert all(a["title_link"] for a in attachments)

        # 色分けチェック
        twitter_attachment = attachments[0]
        rss_attachment = attachments[1]

        assert twitter_attachment["color"] == "#1DA1F2"  # Twitter
        assert rss_attachment["color"] == "#FF6600"  # RSS

    @patch("services.notifier.slack_sender.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    @patch("services.notifier.slack_sender.urllib.request.urlopen")
    def test_collect_format_send_workflow(self, mock_urlopen, sample_news_items):
        """完全なワークフロー：収集 → フォーマット → 送信"""
        from services.notifier import slack_sender

        slack_sender.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"

        # モック レスポンス
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_urlopen.return_value = mock_response

        # 実行
        result = send_to_slack(sample_news_items)

        assert result is True
        mock_urlopen.assert_called_once()

        # リクエスト内容をチェック
        call_args = mock_urlopen.call_args
        request = call_args[0][0]

        assert request.full_url == "https://hooks.slack.com/test"


class TestErrorHandling:
    """エラーハンドリング統合テスト"""

    def test_partial_failure_in_batch_insert(self):
        """バッチ挿入中の部分失敗"""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            db = Database(db_path)

            # 重複を含むバッチ
            items = [
                NewsItem(
                    title="Item 1",
                    source="rss",
                    url="https://example.com/1",
                    published_at=datetime.now(),
                    keywords=["test"],
                    raw_text="Test 1",
                ),
                NewsItem(
                    title="Item 1",  # 同じURL（重複）
                    source="rss",
                    url="https://example.com/1",
                    published_at=datetime.now(),
                    keywords=["test"],
                    raw_text="Test 1 duplicate",
                ),
                NewsItem(
                    title="Item 2",
                    source="rss",
                    url="https://example.com/2",
                    published_at=datetime.now(),
                    keywords=["test"],
                    raw_text="Test 2",
                ),
            ]

            success_count, error_count = db.insert_news_items_batch(items)

            # 1件目は成功、2件目は失敗（重複）、3件目は成功
            assert success_count == 2
            assert error_count == 1

        finally:
            import os

            if os.path.exists(db_path):
                os.remove(db_path)

    @patch("services.notifier.slack_sender.SLACK_WEBHOOK_URL", "")
    def test_missing_webhook_url_graceful_handling(self):
        """Webhook URL なしの場合のエラーハンドリング"""
        from services.notifier import slack_sender

        slack_sender.SLACK_WEBHOOK_URL = ""

        items = [
            NewsItem(
                title="Test",
                source="rss",
                url="https://example.com/test",
                published_at=datetime.now(),
                keywords=["test"],
                raw_text="Test",
            )
        ]

        result = send_to_slack(items)

        # エラーが返されるが例外は発生しない
        assert result is False


class TestDataConsistency:
    """データの一貫性テスト"""

    def test_news_item_model_validation(self):
        """NewsItem モデルのバリデーション"""
        from pydantic import ValidationError

        # 有効なアイテム
        valid_item = NewsItem(
            title="Valid Item",
            source="rss",
            url="https://example.com/valid",
            published_at=datetime.now(),
            keywords=["test"],
            raw_text="Content",
        )

        assert valid_item.title == "Valid Item"
        assert valid_item.source == "rss"

        # 無効なアイテム（必須フィールドなし）
        with pytest.raises(ValidationError):
            NewsItem(
                title="Invalid",
                source="rss",
                # url が欠けている
                published_at=datetime.now(),
                keywords=["test"],
                raw_text="Content",
            )

    def test_attachment_consistency(self):
        """Slack アタッチメントのデータ一貫性"""
        item = NewsItem(
            title="Test Article",
            source="twitter",
            url="https://twitter.com/test",
            published_at=datetime(2026, 8, 15, 10, 30, 0),
            keywords=["Claude", "API"],
            raw_text="Article content",
            author="Test User",
        )

        attachment = format_news_item_for_slack(item)

        # タイトルと URL が一致
        assert attachment["title"] == item.title
        assert attachment["title_link"] == item.url

        # キーワードが含まれている
        assert "Claude" in attachment["text"]
        assert "API" in attachment["text"]

        # 著者名が含まれている
        assert "Test User" in attachment["text"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
