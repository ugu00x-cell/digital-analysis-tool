"""
RSS スクレイパーのユニットテスト

feedparser の動作確認とキーワード抽出ロジックのテストを実装。
"""

from datetime import datetime

import pytest

from services.collector.rss_scraper import (
    extract_keywords_from_text,
    parse_feed_entry,
)
from shared.models import NewsItem


class TestExtractKeywordsFromText:
    """キーワード抽出関数のテスト"""

    def test_extract_single_keyword(self):
        """単一キーワード抽出テスト"""
        text = "This is about AI and machine learning"
        keywords = ["AI", "ML", "Python"]

        result = extract_keywords_from_text(text, keywords)

        assert "AI" in result
        assert len(result) >= 1

    def test_extract_multiple_keywords(self):
        """複数キーワード抽出テスト"""
        text = "Claude API and RAG implementation for LLM"
        keywords = ["Claude", "RAG", "LLM", "API"]

        result = extract_keywords_from_text(text, keywords)

        assert "Claude" in result
        assert "RAG" in result
        assert "LLM" in result
        assert "API" in result

    def test_case_insensitive_matching(self):
        """大文字小文字を区別しないマッチング"""
        text = "CLAUDE is a great LLM"
        keywords = ["claude", "llm"]

        result = extract_keywords_from_text(text, keywords)

        assert "claude" in result
        assert "llm" in result

    def test_no_keywords_match(self):
        """キーワード不一致テスト"""
        text = "This is about cooking recipes"
        keywords = ["AI", "LLM", "Claude"]

        result = extract_keywords_from_text(text, keywords)

        assert len(result) == 0

    def test_no_duplicate_keywords(self):
        """キーワード重複排除テスト"""
        text = "AI is about AI and AI"
        keywords = ["AI"]

        result = extract_keywords_from_text(text, keywords)

        assert result.count("AI") == 1 or len([k for k in result if k == "AI"]) == 1


class TestParseFeedEntry:
    """フィード エントリ パース関数のテスト"""

    @pytest.fixture
    def valid_entry(self):
        """有効なフィード エントリのフィクスチャ"""
        return {
            "title": "Claude 3.5 Sonnet Released",
            "link": "https://example.com/article1",
            "summary": "New Claude API with RAG capabilities",
            "author": "John Doe",
            "published_parsed": (2026, 8, 15, 10, 30, 0, 4, 227, 0),
        }

    def test_parse_valid_entry(self, valid_entry):
        """有効なエントリをパース"""
        keywords = ["Claude", "API", "RAG"]

        result = parse_feed_entry(valid_entry, keywords)

        assert result is not None
        assert isinstance(result, NewsItem)
        assert result.title == "Claude 3.5 Sonnet Released"
        assert result.source == "rss"
        assert result.url == "https://example.com/article1"
        assert result.author == "John Doe"

    def test_parse_entry_with_matching_keywords(self, valid_entry):
        """キーワードマッチ テスト"""
        keywords = ["Claude", "API"]

        result = parse_feed_entry(valid_entry, keywords)

        assert result is not None
        assert len(result.keywords) > 0
        assert "Claude" in result.keywords

    def test_parse_entry_no_keywords_returns_none(self, valid_entry):
        """キーワード不一致でNoneを返す"""
        keywords = ["Kubernetes", "Docker", "Terraform"]

        result = parse_feed_entry(valid_entry, keywords)

        # キーワードがマッチしないはずなので None を返す
        assert result is None

    def test_parse_entry_without_author(self):
        """著者なしエントリをパース"""
        entry = {
            "title": "AI News",
            "link": "https://example.com/article2",
            "summary": "Latest AI updates",
            "published_parsed": (2026, 8, 15, 10, 30, 0, 4, 227, 0),
        }
        keywords = ["AI"]

        result = parse_feed_entry(entry, keywords)

        assert result is not None
        assert result.author is None

    def test_parse_entry_invalid_url_returns_none(self):
        """無効なURLはNoneを返す"""
        entry = {
            "title": "Test",
            "link": "not-a-url",  # 無効なURL
            "summary": "Test AI content",
            "published_parsed": (2026, 8, 15, 10, 30, 0, 4, 227, 0),
        }
        keywords = ["AI"]

        result = parse_feed_entry(entry, keywords)

        assert result is None

    def test_parse_entry_summary_truncated(self, valid_entry):
        """要約が500文字に切り詰められる"""
        long_summary = "X" * 1000
        valid_entry["summary"] = long_summary
        keywords = ["X"]

        result = parse_feed_entry(valid_entry, keywords)

        assert result is not None
        assert len(result.raw_text) <= 500


class TestNewsItemModel:
    """NewsItem データモデルのテスト"""

    def test_create_news_item(self):
        """NewsItem を作成"""
        item = NewsItem(
            title="Test Article",
            source="rss",
            url="https://example.com/test",
            published_at=datetime.now(),
            keywords=["test", "article"],
            raw_text="This is test content",
            author="Test Author",
        )

        assert item.title == "Test Article"
        assert item.source == "rss"
        assert item.keywords == ["test", "article"]

    def test_news_item_to_dict(self):
        """NewsItem を辞書に変換"""
        item = NewsItem(
            title="Test",
            source="twitter",
            url="https://twitter.com/test",
            published_at=datetime(2026, 8, 15, 10, 0, 0),
            keywords=["test"],
            raw_text="Test",
        )

        data = item.model_dump()

        assert "title" in data
        assert "source" in data
        assert data["source"] == "twitter"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
