"""
X（Twitter）API v2 スクレイピングモジュール

X API v2 を使用してキーワード検索 & アカウントタイムラインを取得。

注：X API v2 の使用には以下が必要です
  - Bearer Token（API key and secret から生成）
  - または API key, API secret, Access token, Access token secret
"""

import time
from datetime import datetime, timedelta
from typing import List, Optional

import requests

from shared.config import (
    X_ACCOUNTS,
    X_BEARER_TOKEN,
    X_KEYWORDS,
    X_REQUEST_DELAY_SEC,
)
from shared.logger import setup_logger
from shared.models import NewsItem

logger = setup_logger(__name__)

# X API v2 エンドポイント
SEARCH_ENDPOINT = "https://api.twitter.com/2/tweets/search/recent"
TIMELINE_ENDPOINT = "https://api.twitter.com/2/users/{user_id}/tweets"
USER_LOOKUP_ENDPOINT = "https://api.twitter.com/2/users/by/username/{username}"


def get_headers() -> Optional[dict]:
    """
    X API v2 のリクエストヘッダを構築

    Returns:
        ヘッダ辞書（または認証情報がない場合はNone）
    """
    if not X_BEARER_TOKEN:
        logger.warning("X_BEARER_TOKEN is not set. X API requests will fail.")
        return None

    return {
        "Authorization": f"Bearer {X_BEARER_TOKEN}",
        "User-Agent": "ai-news-monitor/1.0",
    }


def search_keywords(keywords: List[str] = None, lang: str = "ja") -> tuple[List[NewsItem], List[str]]:
    """
    X API でキーワード検索を実行

    Args:
        keywords: 検索キーワード（デフォルト: config.X_KEYWORDS）
        lang: 言語（デフォルト: "ja" 日本語）

    Returns:
        (NewsItem リスト, エラーメッセージリスト)
    """
    if keywords is None:
        keywords = X_KEYWORDS

    headers = get_headers()
    if not headers:
        return [], ["X_BEARER_TOKEN is not configured"]

    items = []
    errors = []

    # 検索パラメータ（X API v2）
    params = {
        "max_results": 100,  # 1リクエストあたり最大100件
        "tweet.fields": "created_at,author_id,public_metrics",
        "expansions": "author_id",
        "user.fields": "username,name",
    }

    # 過去7日間のツイートを検索
    start_time = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"
    params["start_time"] = start_time

    for keyword in keywords:
        try:
            # 検索クエリ
            # lang:ja で日本語フィルタリング
            query = f'"{keyword}" lang:ja -is:retweet'
            params["query"] = query

            logger.info(f"Searching X API for keyword: {keyword}")
            response = requests.get(SEARCH_ENDPOINT, headers=headers, params=params, timeout=10)

            # レート制限対策
            time.sleep(X_REQUEST_DELAY_SEC)

            # ステータスコード確認
            if response.status_code == 429:
                error_msg = "X API rate limit exceeded"
                logger.warning(error_msg)
                errors.append(error_msg)
                break  # レート制限に達したら終了

            if response.status_code != 200:
                error_msg = f"X API error: {response.status_code} - {response.text[:100]}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue

            # レスポンス解析
            data = response.json()
            tweets = data.get("data", [])
            includes = data.get("includes", {})
            users = {user["id"]: user for user in includes.get("users", [])}

            logger.debug(f"Found {len(tweets)} tweets for keyword: {keyword}")

            for tweet in tweets:
                try:
                    # ツイート情報
                    tweet_id = tweet.get("id", "")
                    text = tweet.get("text", "")
                    created_at = datetime.fromisoformat(
                        tweet.get("created_at", "").replace("Z", "+00:00")
                    )

                    # ユーザー情報
                    author_id = tweet.get("author_id", "")
                    user = users.get(author_id, {})
                    username = user.get("username", "unknown")
                    author_name = user.get("name", username)

                    # URL 構築
                    url = f"https://twitter.com/{username}/status/{tweet_id}"

                    # NewsItem を構築
                    item = NewsItem(
                        title=text[:100],  # 最初100文字をタイトルとする
                        source="twitter",
                        url=url,
                        published_at=created_at,
                        keywords=[keyword],
                        raw_text=text,
                        author=author_name,
                    )

                    items.append(item)

                except Exception as e:
                    logger.debug(f"Error parsing tweet: {e}")
                    continue

            logger.info(f"Successfully fetched {len(tweets)} tweets for keyword: {keyword}")

        except requests.Timeout:
            error_msg = f"X API request timeout for keyword: {keyword}"
            logger.error(error_msg)
            errors.append(error_msg)

        except Exception as e:
            error_msg = f"Error searching X API for keyword {keyword}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

    logger.info(f"X API search complete: {len(items)} items, {len(errors)} errors")
    return items, errors


def fetch_account_timeline(accounts: List[str] = None) -> tuple[List[NewsItem], List[str]]:
    """
    特定アカウントのタイムラインを取得（オプション機能）

    Args:
        accounts: フォロー対象アカウント（@username 形式）

    Returns:
        (NewsItem リスト, エラーメッセージリスト)
    """
    if accounts is None:
        accounts = X_ACCOUNTS

    headers = get_headers()
    if not headers:
        return [], ["X_BEARER_TOKEN is not configured"]

    items = []
    errors = []

    for account in accounts:
        try:
            # @username から username を抽出
            username = account.lstrip("@")

            logger.info(f"Fetching timeline for account: {username}")

            # ユーザーIDを取得
            user_response = requests.get(
                USER_LOOKUP_ENDPOINT.format(username=username),
                headers=headers,
                timeout=10,
            )
            time.sleep(X_REQUEST_DELAY_SEC)

            if user_response.status_code != 200:
                error_msg = f"Could not fetch user {username}: {user_response.status_code}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue

            user_id = user_response.json()["data"]["id"]

            # タイムラインを取得
            timeline_params = {
                "max_results": 100,
                "tweet.fields": "created_at,public_metrics",
            }

            timeline_response = requests.get(
                TIMELINE_ENDPOINT.format(user_id=user_id),
                headers=headers,
                params=timeline_params,
                timeout=10,
            )
            time.sleep(X_REQUEST_DELAY_SEC)

            if timeline_response.status_code != 200:
                error_msg = f"Could not fetch timeline for {username}: {timeline_response.status_code}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue

            tweets = timeline_response.json().get("data", [])

            # NewsItem を構築
            for tweet in tweets:
                item = NewsItem(
                    title=tweet.get("text", "")[:100],
                    source="twitter",
                    url=f"https://twitter.com/{username}/status/{tweet.get('id', '')}",
                    published_at=datetime.fromisoformat(
                        tweet.get("created_at", "").replace("Z", "+00:00")
                    ),
                    keywords=[],  # アカウント監視なのでキーワード指定なし
                    raw_text=tweet.get("text", ""),
                    author=username,
                )
                items.append(item)

            logger.info(f"Fetched {len(tweets)} tweets for account: {username}")

        except Exception as e:
            error_msg = f"Error fetching timeline for {account}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

    logger.info(f"Timeline fetch complete: {len(items)} items, {len(errors)} errors")
    return items, errors


if __name__ == "__main__":
    # テスト用：直接実行時
    print("\n=== X API Search ===")
    items, errors = search_keywords()
    print(f"Items: {len(items)}")
    print(f"Errors: {len(errors)}")

    if items:
        print(f"\nFirst 3 items:")
        for item in items[:3]:
            print(f"  - {item.title[:60]}")
            print(f"    Author: {item.author}")
            print(f"    URL: {item.url}\n")

    print("\n=== X API Timeline ===")
    items, errors = fetch_account_timeline()
    print(f"Items: {len(items)}")
    print(f"Errors: {len(errors)}")
