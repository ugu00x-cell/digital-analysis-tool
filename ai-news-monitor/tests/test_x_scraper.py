"""
X API スクレイパーのユニットテスト

X API v2 連携ロジックのテスト（モック使用）。
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from services.collector.x_scraper import (
    get_headers,
    search_keywords,
)
from shared.models import NewsItem


class TestGetHeaders:
    """X API リクエストヘッダ生成関数のテスト"""

    @patch("services.collector.x_scraper.X_BEARER_TOKEN", "test_token_123")
    def test_get_headers_with_valid_token(self):
        """有効な Bearer Token でヘッダ生成"""
        from services.collector import x_scraper

        # モジュール内の X_BEARER_TOKEN をモック
        x_scraper.X_BEARER_TOKEN = "test_token_123"
        headers = get_headers()

        assert headers is not None
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test_token_123"
        assert headers["User-Agent"] == "ai-news-monitor/1.0"

    @patch("services.collector.x_scraper.X_BEARER_TOKEN", "")
    def test_get_headers_without_token(self):
        """Token なしでヘッダ生成"""
        from services.collector import x_scraper

        x_scraper.X_BEARER_TOKEN = ""
        headers = get_headers()

        assert headers is None


class TestSearchKeywords:
    """キーワード検索関数のテスト（モック使用）"""

    @pytest.fixture
    def mock_response(self):
        """モック レスポンス"""
        return {
            "data": [
                {
                    "id": "12345",
                    "text": "Claude 3.5 Sonnet is amazing!",
                    "created_at": "2026-08-15T10:30:00Z",
                    "author_id": "user123",
                },
                {
                    "id": "12346",
                    "text": "RAG implementations with Claude API",
                    "created_at": "2026-08-15T09:30:00Z",
                    "author_id": "user124",
                },
            ],
            "includes": {
                "users": [
                    {
                        "id": "user123",
                        "username": "anthropic",
                        "name": "Anthropic",
                    },
                    {
                        "id": "user124",
                        "username": "devuser",
                        "name": "Dev User",
                    },
                ]
            },
        }

    @patch("services.collector.x_scraper.X_BEARER_TOKEN", "test_token")
    @patch("services.collector.x_scraper.requests.get")
    def test_search_keywords_success(self, mock_get, mock_response):
        """キーワード検索成功テスト"""
        from services.collector import x_scraper

        x_scraper.X_BEARER_TOKEN = "test_token"

        # モック レスポンスをセット
        mock_response_obj = MagicMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json.return_value = mock_response
        mock_get.return_value = mock_response_obj

        items, errors = search_keywords(keywords=["Claude"])

        assert len(items) > 0
        assert len(errors) == 0
        assert all(isinstance(item, NewsItem) for item in items)

    @patch("services.collector.x_scraper.X_BEARER_TOKEN", "")
    def test_search_keywords_without_auth(self):
        """認証情報なしでキーワード検索"""
        from services.collector import x_scraper

        x_scraper.X_BEARER_TOKEN = ""
        items, errors = search_keywords(keywords=["Claude"])

        assert len(items) == 0
        assert len(errors) > 0

    @patch("services.collector.x_scraper.X_BEARER_TOKEN", "test_token")
    @patch("services.collector.x_scraper.requests.get")
    def test_search_keywords_rate_limit(self, mock_get):
        """レート制限エラー テスト"""
        from services.collector import x_scraper

        x_scraper.X_BEARER_TOKEN = "test_token"

        # レート制限レスポンス（429）
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        items, errors = search_keywords(keywords=["Claude"])

        assert len(items) == 0
        assert len(errors) > 0
        assert any("rate limit" in e.lower() for e in errors)

    @patch("services.collector.x_scraper.X_BEARER_TOKEN", "test_token")
    @patch("services.collector.x_scraper.requests.get")
    def test_search_keywords_api_error(self, mock_get):
        """API エラー テスト"""
        from services.collector import x_scraper

        x_scraper.X_BEARER_TOKEN = "test_token"

        # エラーレスポンス（400）
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_get.return_value = mock_response

        items, errors = search_keywords(keywords=["Claude"])

        assert len(items) == 0
        assert len(errors) > 0

    @patch("services.collector.x_scraper.X_BEARER_TOKEN", "test_token")
    @patch("services.collector.x_scraper.requests.get")
    def test_search_keywords_connection_timeout(self, mock_get):
        """接続タイムアウト テスト"""
        from services.collector import x_scraper
        import requests

        x_scraper.X_BEARER_TOKEN = "test_token"

        # タイムアウト例外をシミュレート
        mock_get.side_effect = requests.Timeout("Connection timed out")

        items, errors = search_keywords(keywords=["Claude"])

        assert len(items) == 0
        assert len(errors) > 0


class TestNewsItemCreation:
    """NewsItem オブジェクト生成テスト"""

    def test_create_news_item_from_x_api(self):
        """X API レスポンスから NewsItem を作成"""
        item = NewsItem(
            title="Claude 3.5 Sonnet released",
            source="twitter",
            url="https://twitter.com/anthropic/status/12345",
            published_at=datetime.fromisoformat("2026-08-15T10:30:00+00:00"),
            keywords=["Claude", "API"],
            raw_text="Claude 3.5 Sonnet is now available",
            author="Anthropic",
        )

        assert item.title == "Claude 3.5 Sonnet released"
        assert item.source == "twitter"
        assert item.author == "Anthropic"
        assert len(item.keywords) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
