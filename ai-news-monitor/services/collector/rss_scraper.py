"""
RSS フィード解析モジュール

複数の RSS フィードから AI 関連ニュースを取得。
"""

import re
from datetime import datetime
from typing import List, Optional

import feedparser

from shared.config import FEED_URLS, X_KEYWORDS
from shared.logger import setup_logger
from shared.models import NewsItem

logger = setup_logger(__name__)


def extract_keywords_from_text(text: str, keywords: List[str]) -> List[str]:
    """
    テキストから指定キーワードを抽出

    Args:
        text: 検索対象テキスト
        keywords: キーワードリスト

    Returns:
        マッチしたキーワードリスト（重複なし）
    """
    matched = []
    text_lower = text.lower()

    for keyword in keywords:
        # キーワードを大文字小文字を区別せずに検索
        if keyword.lower() in text_lower:
            matched.append(keyword)

    return list(set(matched))  # 重複を削除


def parse_feed_entry(entry: dict, keywords: List[str]) -> Optional[NewsItem]:
    """
    feedparser のエントリを NewsItem に変換

    Args:
        entry: feedparser のエントリ辞書
        keywords: 検索キーワード一覧

    Returns:
        NewsItem インスタンス（またはNoneに該当しない場合）
    """
    try:
        # 必須フィールドを取得
        title = entry.get("title", "")
        url = entry.get("link", entry.get("id", ""))
        summary = entry.get("summary", "")
        author = entry.get("author", None)

        # 公開日時を取得
        published_str = None
        if "published_parsed" in entry and entry["published_parsed"]:
            published = datetime(*entry["published_parsed"][:6])
        elif "updated_parsed" in entry and entry["updated_parsed"]:
            published = datetime(*entry["updated_parsed"][:6])
        else:
            published = datetime.now()

        # キーワード抽出（タイトル + 説明文）
        combined_text = f"{title} {summary}"
        matched_keywords = extract_keywords_from_text(combined_text, keywords)

        # キーワードがマッチしなかった場合はスキップ
        if not matched_keywords:
            return None

        # URL の正規化
        if not url.startswith("http"):
            return None

        # NewsItem を構築
        item = NewsItem(
            title=title,
            source="rss",
            url=url,
            published_at=published,
            keywords=matched_keywords,
            raw_text=summary[:500],  # 最初500文字
            author=author,
        )

        return item

    except Exception as e:
        logger.warning(f"Error parsing feed entry: {e}")
        return None


def fetch_rss_feeds(feed_urls: List[str] = None, keywords: List[str] = None) -> tuple[List[NewsItem], List[str]]:
    """
    複数の RSS フィードを取得してパース

    Args:
        feed_urls: RSS フィード URL のリスト（デフォルト: config.FEED_URLS）
        keywords: 検索キーワード（デフォルト: config.X_KEYWORDS）

    Returns:
        (NewsItem リスト, エラーメッセージリスト)
    """
    if feed_urls is None:
        feed_urls = FEED_URLS
    if keywords is None:
        keywords = X_KEYWORDS

    items = []
    errors = []

    for feed_url in feed_urls:
        try:
            logger.info(f"Fetching RSS feed: {feed_url}")
            feed = feedparser.parse(feed_url)

            # feedparser のステータスチェック
            if feed.get("status") == 404:
                error_msg = f"Feed not found (404): {feed_url}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue

            if feed.get("bozo_exception"):
                logger.warning(f"Feed parsing error for {feed_url}: {feed.bozo_exception}")
                # エラーがあっても続行（部分的にパースされたデータを使用）

            # エントリをパース
            entries = feed.get("entries", [])
            logger.debug(f"Found {len(entries)} entries in {feed_url}")

            for entry in entries:
                news_item = parse_feed_entry(entry, keywords)
                if news_item:
                    items.append(news_item)

            logger.info(f"Successfully fetched {len(items)} matching items from {feed_url}")

        except Exception as e:
            error_msg = f"Error fetching RSS feed {feed_url}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

    logger.info(f"RSS collection complete: {len(items)} items, {len(errors)} errors")
    return items, errors


if __name__ == "__main__":
    # テスト用：直接実行時
    items, errors = fetch_rss_feeds()
    print(f"\n=== RSS Collection Results ===")
    print(f"Items: {len(items)}")
    print(f"Errors: {len(errors)}")

    if items:
        print(f"\nFirst 3 items:")
        for item in items[:3]:
            print(f"  - {item.title[:60]}")
            print(f"    Keywords: {item.keywords}")
            print(f"    URL: {item.url}\n")

    if errors:
        print(f"Errors:")
        for error in errors:
            print(f"  - {error}")
