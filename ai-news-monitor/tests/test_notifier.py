"""
Slack 通知サービスのユニットテスト

Webhook 通知機能とフォーマッティング ロジックのテスト。
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from services.notifier.slack_sender import (
    format_news_item_for_slack,
    send_test_message,
    send_to_slack,
)
from shared.models import NewsItem


class TestFormatNewsItemForSlack:
    """NewsItem を Slack 形式にフォーマット"""

    @pytest.fixture
    def sample_news_item(self):
        """サンプル NewsItem"""
        return NewsItem(
            title="Claude 3.5 Sonnet Released",
            source="twitter",
            url="https://twitter.com/anthropic/status/12345",
            published_at=datetime(2026, 8, 15, 10, 30, 0),
            keywords=["Claude", "API"],
            raw_text="Claude 3.5 Sonnet is now available with improved performance",
            author="Anthropic",
        )

    def test_format_twitter_news(self, sample_news_item):
        """Twitter ソースのニュースをフォーマット"""
        attachment = format_news_item_for_slack(sample_news_item)

        assert attachment is not None
        assert attachment["color"] == "#1DA1F2"  # Twitter Blue
        assert attachment["title"] == "Claude 3.5 Sonnet Released"
        assert attachment["title_link"] == sample_news_item.url
        assert "Claude" in attachment["text"]

    def test_format_rss_news(self):
        """RSS ソースのニュースをフォーマット"""
        item = NewsItem(
            title="AI Trends in 2026",
            source="rss",
            url="https://example.com/article",
            published_at=datetime(2026, 8, 15, 10, 0, 0),
            keywords=["AI", "trends"],
            raw_text="Latest AI trends",
            author="Tech Blog",
        )

        attachment = format_news_item_for_slack(item)

        assert attachment["color"] == "#FF6600"  # RSS Orange
        assert attachment["title"] == "AI Trends in 2026"

    def test_format_includes_keywords(self, sample_news_item):
        """フォーマット内にキーワードが含まれる"""
        attachment = format_news_item_for_slack(sample_news_item)

        text = attachment["text"]
        assert "`Claude`" in text
        assert "`API`" in text

    def test_format_includes_author(self, sample_news_item):
        """フォーマット内に著者名が含まれる"""
        attachment = format_news_item_for_slack(sample_news_item)

        text = attachment["text"]
        assert "Anthropic" in text

    def test_format_without_author(self):
        """著者なしのニュースをフォーマット"""
        item = NewsItem(
            title="News Without Author",
            source="rss",
            url="https://example.com/article2",
            published_at=datetime(2026, 8, 15, 10, 0, 0),
            keywords=["news"],
            raw_text="Content",
        )

        attachment = format_news_item_for_slack(item)

        assert attachment is not None
        assert attachment["title"] == "News Without Author"


class TestSendToSlack:
    """Slack 通知送信関数のテスト"""

    @pytest.fixture
    def sample_items(self):
        """サンプル NewsItem リスト"""
        return [
            NewsItem(
                title="Article 1",
                source="twitter",
                url="https://twitter.com/test1",
                published_at=datetime.now(),
                keywords=["test"],
                raw_text="Test 1",
            ),
            NewsItem(
                title="Article 2",
                source="rss",
                url="https://example.com/test2",
                published_at=datetime.now(),
                keywords=["test"],
                raw_text="Test 2",
            ),
        ]

    @patch("services.notifier.slack_sender.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    @patch("services.notifier.slack_sender.urllib.request.urlopen")
    def test_send_to_slack_success(self, mock_urlopen, sample_items):
        """Slack 通知送信成功"""
        # モック レスポンス
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_urlopen.return_value = mock_response

        from services.notifier import slack_sender

        slack_sender.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"

        result = send_to_slack(sample_items)

        assert result is True
        mock_urlopen.assert_called_once()

    @patch("services.notifier.slack_sender.SLACK_WEBHOOK_URL", "")
    def test_send_to_slack_no_webhook_url(self, sample_items):
        """Webhook URL なしでの送信"""
        from services.notifier import slack_sender

        slack_sender.SLACK_WEBHOOK_URL = ""

        result = send_to_slack(sample_items)

        assert result is False

    def test_send_to_slack_empty_items(self):
        """空のアイテムリスト"""
        result = send_to_slack([])

        assert result is False

    @patch("services.notifier.slack_sender.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    @patch("services.notifier.slack_sender.urllib.request.urlopen")
    def test_send_to_slack_webhook_error(self, mock_urlopen, sample_items):
        """Webhook エラー"""
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_urlopen.return_value = mock_response

        from services.notifier import slack_sender

        slack_sender.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"

        result = send_to_slack(sample_items)

        assert result is False

    @patch("services.notifier.slack_sender.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    @patch("services.notifier.slack_sender.urllib.request.urlopen")
    def test_send_to_slack_network_error(self, mock_urlopen, sample_items):
        """ネットワーク エラー"""
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("Connection refused")

        from services.notifier import slack_sender

        slack_sender.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"

        result = send_to_slack(sample_items)

        assert result is False


class TestSendTestMessage:
    """テストメッセージ送信関数のテスト"""

    @patch("services.notifier.slack_sender.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    @patch("services.notifier.slack_sender.urllib.request.urlopen")
    def test_send_test_message_success(self, mock_urlopen):
        """テストメッセージ送信成功"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_urlopen.return_value = mock_response

        from services.notifier import slack_sender

        slack_sender.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"

        result = send_test_message()

        assert result is True

    @patch("services.notifier.slack_sender.SLACK_WEBHOOK_URL", "")
    def test_send_test_message_no_webhook(self):
        """Webhook URL なしでテストメッセージ"""
        from services.notifier import slack_sender

        slack_sender.SLACK_WEBHOOK_URL = ""

        result = send_test_message()

        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
