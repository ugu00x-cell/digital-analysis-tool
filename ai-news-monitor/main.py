"""
AI News Monitor - メインスクリプト

X API + RSS フィードから AI ニュースを自動収集して Slack 通知。
"""

import argparse
import sys
from datetime import datetime

from services.collector.rss_scraper import fetch_rss_feeds
from services.collector.x_scraper import fetch_account_timeline, search_keywords
from services.notifier.slack_sender import send_test_message, send_to_slack
from shared.config import validate_config
from shared.database import get_database
from shared.logger import setup_logger
from shared.models import NewsItem

logger = setup_logger(__name__)


def collect_news() -> list[NewsItem]:
    """
    複数のソースから AI ニュースを収集

    Returns:
        NewsItem リスト
    """
    all_items = []
    errors = []

    # RSS フィード取得
    logger.info("=" * 60)
    logger.info("Fetching RSS feeds...")
    logger.info("=" * 60)

    rss_items, rss_errors = fetch_rss_feeds()
    all_items.extend(rss_items)
    errors.extend(rss_errors)

    logger.info(f"RSS: {len(rss_items)} items collected, {len(rss_errors)} errors")

    # X API キーワード検索
    logger.info("=" * 60)
    logger.info("Searching X API for keywords...")
    logger.info("=" * 60)

    x_search_items, x_search_errors = search_keywords()
    all_items.extend(x_search_items)
    errors.extend(x_search_errors)

    logger.info(f"X Search: {len(x_search_items)} items collected, {len(x_search_errors)} errors")

    # X API アカウントタイムライン
    logger.info("=" * 60)
    logger.info("Fetching X account timelines...")
    logger.info("=" * 60)

    x_timeline_items, x_timeline_errors = fetch_account_timeline()
    all_items.extend(x_timeline_items)
    errors.extend(x_timeline_errors)

    logger.info(f"X Timeline: {len(x_timeline_items)} items collected, {len(x_timeline_errors)} errors")

    # 結果サマリ
    logger.info("=" * 60)
    logger.info(f"Total collected: {len(all_items)} items, {len(errors)} errors")
    logger.info("=" * 60)

    if errors:
        logger.warning("Errors occurred during collection:")
        for error in errors:
            logger.warning(f"  - {error}")

    return all_items


def process_and_notify(items: list[NewsItem], dry_run: bool = False) -> bool:
    """
    ニュースをデータベースに保存して Slack 通知

    Args:
        items: NewsItem リスト
        dry_run: True の場合、Slack 通知をスキップ（テスト用）

    Returns:
        成功したかどうか
    """
    if not items:
        logger.warning("No items to process")
        return False

    # データベースに保存
    logger.info("=" * 60)
    logger.info("Saving to database...")
    logger.info("=" * 60)

    db = get_database()
    success_count, error_count = db.insert_news_items_batch(items)

    logger.info(f"Database: {success_count} items saved, {error_count} duplicates/errors")

    # Slack に通知
    logger.info("=" * 60)
    logger.info("Sending to Slack...")
    logger.info("=" * 60)

    # 重複チェック済みの新規アイテムのみを通知対象にする
    # （実装簡略化のため、全アイテムを通知対象にする。本番ではフィルタリング推奨）
    if dry_run:
        logger.info("DRY RUN: Skipping Slack notification")
        logger.info(f"Would send {len(items)} items to Slack")
        return True
    else:
        success = send_to_slack(items)
        if success:
            # DB に通知履歴を記録
            item_ids = list(range(1, len(items) + 1))  # 簡略化
            db.log_notification(item_ids, status="sent")
            logger.info("Notification sent to Slack")
            return True
        else:
            logger.error("Failed to send notification to Slack")
            return False


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description="AI News Monitor - AI ニュースを自動収集して Slack 通知"
    )
    parser.add_argument(
        "--test-slack",
        action="store_true",
        help="Slack Webhook テストメッセージを送信",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Slack 通知をスキップ（テスト用）",
    )
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="設定をバリデート",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("AI News Monitor started")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    try:
        # 設定をバリデート
        if args.validate_config:
            logger.info("Validating configuration...")
            validate_config()
            logger.info("Configuration is valid!")
            return 0

        # Slack テストメッセージ
        if args.test_slack:
            logger.info("Sending test message to Slack...")
            success = send_test_message()
            return 0 if success else 1

        # 通常実行：収集 → 保存 → 通知
        items = collect_news()

        if items:
            success = process_and_notify(items, dry_run=args.dry_run)
            return 0 if success else 1
        else:
            logger.warning("No news items collected")
            return 1

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.info("Please set required environment variables (see .env.example)")
        return 1

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1

    finally:
        logger.info("=" * 60)
        logger.info("AI News Monitor finished")
        logger.info("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
