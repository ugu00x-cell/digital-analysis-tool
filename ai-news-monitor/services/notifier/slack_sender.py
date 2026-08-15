"""
Slack Webhook 通知送信モジュール

NewsItem をフォーマットして Slack に送信。
参考実装: predictive-maintenance-api/services/notifier/main.py
"""

import json
import urllib.request
from datetime import datetime
from typing import List
from urllib.error import URLError

from shared.config import SLACK_TIMEOUT_SEC, SLACK_WEBHOOK_URL
from shared.logger import setup_logger
from shared.models import NewsItem

logger = setup_logger(__name__)


def format_news_item_for_slack(item: NewsItem) -> dict:
    """
    NewsItem を Slack のアタッチメント形式にフォーマット

    Args:
        item: NewsItem インスタンス

    Returns:
        Slack アタッチメント形式の辞書
    """
    # ソースに応じた色分け
    color_map = {
        "twitter": "#1DA1F2",  # Twitter Blue
        "rss": "#FF6600",  # Orange
    }
    color = color_map.get(item.source, "#808080")

    # テキスト本文（マークダウン対応）
    text_parts = [
        f"*{item.title}*",
        f"_From: {item.source.upper()}_",
    ]

    if item.author:
        text_parts.append(f"By {item.author}")

    if item.keywords:
        keyword_str = " ".join(f"`{k}`" for k in item.keywords)
        text_parts.append(f"Keywords: {keyword_str}")

    text = "\n".join(text_parts)

    # アタッチメント（Slack mrkdwn形式）
    attachment = {
        "fallback": item.title,
        "color": color,
        "title": item.title,
        "title_link": item.url,
        "text": text,
        "fields": [
            {
                "title": "Source",
                "value": item.source.upper(),
                "short": True,
            },
            {
                "title": "Published",
                "value": item.published_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "short": True,
            },
        ],
        "ts": int(item.published_at.timestamp()),
        "mrkdwn_in": ["text", "pretext"],
    }

    return attachment


def send_to_slack(items: List[NewsItem], webhook_url: str = None) -> bool:
    """
    複数のニュース記事を Slack に通知

    Args:
        items: NewsItem リスト
        webhook_url: Slack Webhook URL（デフォルト: config.SLACK_WEBHOOK_URL）

    Returns:
        成功したかどうか
    """
    if webhook_url is None:
        webhook_url = SLACK_WEBHOOK_URL

    if not webhook_url:
        logger.error("SLACK_WEBHOOK_URL is not configured")
        return False

    if not items:
        logger.warning("No items to send to Slack")
        return False

    try:
        # Slack ペイロード
        attachments = [format_news_item_for_slack(item) for item in items]

        payload = {
            "text": f":newspaper: AI News Update - {len(items)} new items",
            "attachments": attachments,
            "ts": int(datetime.now().timestamp()),
        }

        # JSON にエンコード
        payload_json = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        # リクエストを構築
        request = urllib.request.Request(
            webhook_url,
            data=payload_json,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "ai-news-monitor/1.0",
            },
            method="POST",
        )

        # Webhook にポスト
        logger.info(f"Sending {len(items)} items to Slack...")
        with urllib.request.urlopen(request, timeout=SLACK_TIMEOUT_SEC) as response:
            status_code = response.status

            if status_code == 200:
                logger.info(f"Successfully sent {len(items)} items to Slack")
                return True
            else:
                logger.warning(f"Slack returned status code: {status_code}")
                return False

    except URLError as e:
        logger.error(f"Slack Webhook request failed: {e.reason}")
        return False

    except json.JSONDecodeError as e:
        logger.error(f"JSON encoding error: {e}")
        return False

    except Exception as e:
        logger.error(f"Unexpected error sending to Slack: {e}")
        return False


def send_test_message(webhook_url: str = None) -> bool:
    """
    テスト用メッセージを Slack に送信

    Args:
        webhook_url: Slack Webhook URL

    Returns:
        成功したかどうか
    """
    if webhook_url is None:
        webhook_url = SLACK_WEBHOOK_URL

    if not webhook_url:
        logger.error("SLACK_WEBHOOK_URL is not configured")
        return False

    try:
        payload = {
            "text": ":rocket: AI News Monitor is working!",
            "attachments": [
                {
                    "color": "good",
                    "title": "Test Message",
                    "text": "This is a test message from ai-news-monitor.",
                    "ts": int(datetime.now().timestamp()),
                }
            ],
        }

        payload_json = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        request = urllib.request.Request(
            webhook_url,
            data=payload_json,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "ai-news-monitor/1.0",
            },
            method="POST",
        )

        logger.info("Sending test message to Slack...")
        with urllib.request.urlopen(request, timeout=SLACK_TIMEOUT_SEC) as response:
            if response.status == 200:
                logger.info("Test message sent successfully!")
                return True
            else:
                logger.warning(f"Slack returned status code: {response.status}")
                return False

    except URLError as e:
        logger.error(f"Slack test message failed: {e.reason}")
        return False

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False


if __name__ == "__main__":
    # テスト用：直接実行時
    print("Sending test message to Slack...")
    success = send_test_message()
    print(f"Result: {'Success' if success else 'Failed'}")
