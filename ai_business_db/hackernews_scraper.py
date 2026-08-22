"""HackerNews APIからAI関連ビジネス情報を取得する。

HackerNews Top StoriesからAI・スタートアップ関連の記事を抽出し、
ビジネス情報として構造化する。
"""

import logging
import re
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# HackerNews APIのベースURL
HACKERNEWS_API_BASE = "https://hacker-news.firebaseio.com/v0"

# AI関連のキーワード（タイトルに含まれるかチェック）
AI_KEYWORDS = ("AI", "machine learning", "GPT", "LLM", "neural", "startup", "bot", "automation")


def fetch_top_stories(limit: int = 30) -> list[int]:
    """HackerNewsのトップストーリーIDを取得する。

    Args:
        limit: 取得するストーリーIDの件数。

    Returns:
        list[int]: ストーリーIDのリスト（最大limit件）。

    Raises:
        requests.RequestException: APIへの接続に失敗した場合。
    """
    try:
        url = f"{HACKERNEWS_API_BASE}/topstories.json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        story_ids = response.json()[:limit]
        logger.info(f"HackerNewsから{len(story_ids)}件のストーリーIDを取得しました")
        return story_ids
    except requests.RequestException as e:
        logger.error(f"HackerNews APIからの取得に失敗しました: {e}")
        raise


def fetch_story_details(story_id: int) -> Optional[dict]:
    """指定されたストーリーIDの詳細情報を取得する。

    Args:
        story_id: ストーリーID。

    Returns:
        dict: ストーリーの詳細情報（タイトル、URL、スコア等）。
              取得失敗時はNone。
    """
    try:
        url = f"{HACKERNEWS_API_BASE}/item/{story_id}.json"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.warning(f"ストーリーID {story_id} の取得に失敗しました: {e}")
        return None


def is_ai_related(title: str) -> bool:
    """タイトルがAI関連かどうかを判定する。

    Args:
        title: ストーリーのタイトル。

    Returns:
        bool: AI関連と判定されればTrue。
    """
    title_lower = title.lower()
    return any(keyword.lower() in title_lower for keyword in AI_KEYWORDS)


def extract_ai_businesses(limit: int = 30) -> list[dict]:
    """HackerNewsからAI関連ビジネス情報を抽出する。

    AI関連のキーワードを含むストーリーから、ビジネス情報として
    構造化データを抽出する。

    Args:
        limit: 取得するストーリーの件数。

    Returns:
        list[dict]: 抽出されたビジネス情報の辞書リスト。
    """
    story_ids = fetch_top_stories(limit=limit)
    businesses = []

    for story_id in story_ids:
        story = fetch_story_details(story_id)
        if story is None:
            continue

        title = story.get("title", "")
        if not is_ai_related(title):
            continue

        # ビジネス情報として構造化
        business = {
            "id": len(businesses) + 1,
            "name": title[:50],  # 最初の50文字を名前とする
            "model": title,  # フルタイトルをモデル説明とする
            "source": f"HackerNews (Score: {story.get('score', 0)})",
            "date": datetime.fromtimestamp(story.get("time", 0)).strftime("%Y-%m-%d"),
            "url": story.get("url", ""),
        }
        businesses.append(business)
        logger.info(f"AI関連ビジネスを抽出: {business['name']}")

        # 十分な件数を取得したら終了
        if len(businesses) >= 5:
            break

    logger.info(f"合計{len(businesses)}件のAI関連ビジネスを抽出しました")
    return businesses


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("app.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    businesses = extract_ai_businesses()
    for b in businesses:
        print(f"- {b['name']} ({b['date']})")
