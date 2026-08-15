"""
APScheduler ジョブ定義モジュール

朝8時・夜20時に自動実行するジョブをスケジューリング。
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from shared.config import (
    SCHEDULER_EVENING_HOUR,
    SCHEDULER_EVENING_MINUTE,
    SCHEDULER_MORNING_HOUR,
    SCHEDULER_MORNING_MINUTE,
)
from shared.database import get_database
from shared.logger import setup_logger
from services.collector.rss_scraper import fetch_rss_feeds
from services.collector.x_scraper import fetch_account_timeline, search_keywords
from services.notifier.slack_sender import send_to_slack

logger = setup_logger(__name__)


def collect_and_notify_job():
    """
    メイン ジョブ：情報収集 → Slack 通知

    RSS + X API から最新ニュースを収集し、Slack に通知する。
    エラーが発生しても続行（ロギングのみ）。
    """
    logger.info("=" * 60)
    logger.info("Scheduled job started")
    logger.info("=" * 60)

    try:
        # 情報収集
        all_items = []
        all_errors = []

        # RSS フィード取得
        logger.info("Fetching RSS feeds...")
        rss_items, rss_errors = fetch_rss_feeds()
        all_items.extend(rss_items)
        all_errors.extend(rss_errors)
        logger.info(f"RSS: {len(rss_items)} items collected")

        # X API キーワード検索
        logger.info("Searching X API for keywords...")
        x_search_items, x_search_errors = search_keywords()
        all_items.extend(x_search_items)
        all_errors.extend(x_search_errors)
        logger.info(f"X Search: {len(x_search_items)} items collected")

        # X API アカウントタイムライン
        logger.info("Fetching X account timelines...")
        x_timeline_items, x_timeline_errors = fetch_account_timeline()
        all_items.extend(x_timeline_items)
        all_errors.extend(x_timeline_errors)
        logger.info(f"X Timeline: {len(x_timeline_items)} items collected")

        # ログ
        logger.info(f"Total: {len(all_items)} items collected, {len(all_errors)} errors")

        if all_errors:
            logger.warning("Errors occurred during collection:")
            for error in all_errors:
                logger.warning(f"  - {error}")

        # DB に保存して Slack に通知
        if all_items:
            logger.info("Saving to database and notifying Slack...")
            db = get_database()
            success_count, error_count = db.insert_news_items_batch(all_items)

            # 新規アイテムのみを通知
            if success_count > 0:
                # 簡略化のため、全アイテムを通知（本番では新規のみにフィルタリング推奨）
                success = send_to_slack(all_items[:success_count])
                if success:
                    logger.info(f"Successfully notified {success_count} items to Slack")
                else:
                    logger.error("Failed to notify Slack")
            else:
                logger.info("No new items (all duplicates)")
        else:
            logger.warning("No items to process")

    except Exception as e:
        logger.error(f"Unexpected error in scheduled job: {e}", exc_info=True)

    finally:
        logger.info("=" * 60)
        logger.info("Scheduled job finished")
        logger.info("=" * 60)


class SchedulerManager:
    """APScheduler スケジューラー管理クラス"""

    def __init__(self):
        """初期化"""
        self.scheduler = BackgroundScheduler()
        self._configured = False

    def configure(self):
        """スケジューラーを設定（朝8時・夜20時）"""
        if self._configured:
            logger.warning("Scheduler is already configured")
            return

        try:
            # 朝の実行時刻
            morning_trigger = CronTrigger(
                hour=SCHEDULER_MORNING_HOUR,
                minute=SCHEDULER_MORNING_MINUTE,
            )
            self.scheduler.add_job(
                collect_and_notify_job,
                trigger=morning_trigger,
                id="morning_job",
                name="Morning AI News Collection",
                replace_existing=True,
            )
            logger.info(
                f"Registered morning job at {SCHEDULER_MORNING_HOUR}:{SCHEDULER_MORNING_MINUTE:02d}"
            )

            # 夜の実行時刻
            evening_trigger = CronTrigger(
                hour=SCHEDULER_EVENING_HOUR,
                minute=SCHEDULER_EVENING_MINUTE,
            )
            self.scheduler.add_job(
                collect_and_notify_job,
                trigger=evening_trigger,
                id="evening_job",
                name="Evening AI News Collection",
                replace_existing=True,
            )
            logger.info(
                f"Registered evening job at {SCHEDULER_EVENING_HOUR}:{SCHEDULER_EVENING_MINUTE:02d}"
            )

            self._configured = True
            logger.info("Scheduler configured successfully")

        except Exception as e:
            logger.error(f"Failed to configure scheduler: {e}", exc_info=True)
            raise

    def start(self):
        """スケジューラーを開始"""
        if not self._configured:
            self.configure()

        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")
        else:
            logger.warning("Scheduler is already running")

    def stop(self):
        """スケジューラーを停止"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
        else:
            logger.warning("Scheduler is not running")

    def get_jobs(self):
        """登録されているジョブを取得"""
        return self.scheduler.get_jobs()

    def list_jobs(self):
        """登録されているジョブを表示"""
        jobs = self.get_jobs()
        if not jobs:
            logger.info("No jobs registered")
            return

        logger.info("Registered jobs:")
        for job in jobs:
            logger.info(f"  - {job.name} (ID: {job.id}, Trigger: {job.trigger})")


# グローバル インスタンス
_scheduler_instance = None


def get_scheduler() -> SchedulerManager:
    """スケジューラー インスタンスを取得（シングルトン）"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SchedulerManager()
    return _scheduler_instance


if __name__ == "__main__":
    # テスト用：直接実行時
    import time

    logger.info("Starting scheduler test...")

    scheduler_mgr = get_scheduler()
    scheduler_mgr.configure()
    scheduler_mgr.list_jobs()

    # 10秒実行してから停止（テスト用）
    scheduler_mgr.start()
    logger.info("Scheduler running. Press Ctrl+C to stop...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping scheduler...")
        scheduler_mgr.stop()
        logger.info("Scheduler stopped")
