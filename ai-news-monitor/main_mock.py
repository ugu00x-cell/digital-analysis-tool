"""
AI News Monitor - モック版

API 認証情報なしでも動作確認できるバージョン。
サンプルニュースデータを使用してフロー全体をテスト。
"""

import argparse
import sys
from datetime import datetime, timedelta

from shared.database import get_database
from shared.logger import setup_logger
from shared.models import NewsItem

logger = setup_logger(__name__)


def generate_sample_news_items() -> list[NewsItem]:
    """
    サンプル ニュースアイテムを生成（モック用）

    Returns:
        NewsItem リスト
    """
    now = datetime.now()

    return [
        # Twitter ソース
        NewsItem(
            title="Claude 3.5 Sonnet API が全ユーザーに開放",
            source="twitter",
            url="https://twitter.com/anthropic/status/1234567890",
            published_at=now - timedelta(hours=2),
            keywords=["Claude", "API"],
            raw_text="Claude 3.5 Sonnet API is now available to all users with improved performance and lower latency.",
            author="Anthropic",
        ),
        NewsItem(
            title="RAG（検索拡張生成）の最新ベストプラクティス",
            source="twitter",
            url="https://twitter.com/huggingface/status/1234567891",
            published_at=now - timedelta(hours=3),
            keywords=["RAG", "LLM"],
            raw_text="New RAG patterns and best practices for building reliable AI systems with retrieval-augmented generation.",
            author="Hugging Face",
        ),
        NewsItem(
            title="OpenAI の GPT-5 トレーニングが加速",
            source="twitter",
            url="https://twitter.com/openai/status/1234567892",
            published_at=now - timedelta(hours=4),
            keywords=["AI", "LLM"],
            raw_text="Training of GPT-5 is progressing faster than expected with breakthrough improvements in efficiency.",
            author="OpenAI",
        ),
        # RSS ソース
        NewsItem(
            title="TechCrunch: AI スタートアップが 5 億ドルの資金調達",
            source="rss",
            url="https://techcrunch.com/article-ai-funding-500m/",
            published_at=now - timedelta(hours=1),
            keywords=["AI"],
            raw_text="Leading AI startup raises $500M Series C funding for enterprise applications and infrastructure development.",
            author="TechCrunch",
        ),
        NewsItem(
            title="Hacker News: LLM の推論速度を 10 倍高速化する新手法",
            source="rss",
            url="https://news.ycombinator.com/item?id=98765432",
            published_at=now - timedelta(hours=5),
            keywords=["LLM"],
            raw_text="Researchers discover new quantization technique that achieves 10x speedup in LLM inference without accuracy loss.",
            author="Hacker News",
        ),
        NewsItem(
            title="MIT: 次世代 AI チップが記録的なパフォーマンス達成",
            source="rss",
            url="https://news.mit.edu/ai-chip-breakthrough",
            published_at=now - timedelta(hours=6),
            keywords=["AI"],
            raw_text="New AI accelerator chip achieves record performance metrics for deep learning inference workloads.",
            author="MIT News",
        ),
        NewsItem(
            title="Data Science 最新トレンド：AutoML の実用化",
            source="rss",
            url="https://example.com/automl-trends",
            published_at=now - timedelta(hours=7),
            keywords=["Data Science"],
            raw_text="AutoML tools mature and enterprise adoption accelerates with improved explainability and governance features.",
            author="Data Science Weekly",
        ),
        NewsItem(
            title="Google の新しい Gemini Ultra モデル、複数モダリティに対応",
            source="twitter",
            url="https://twitter.com/google/status/1234567893",
            published_at=now - timedelta(hours=8),
            keywords=["Claude", "API"],  # キーワード検索でマッチさせるため
            raw_text="Gemini Ultra now supports text, images, audio, and video in unified multimodal processing pipeline.",
            author="Google DeepMind",
        ),
    ]


def collect_news_mock() -> list[NewsItem]:
    """
    モック版：情報収集

    API を使わずにサンプルデータを返す

    Returns:
        NewsItem リスト
    """
    logger.info("=" * 60)
    logger.info("【モック版】情報収集を開始")
    logger.info("=" * 60)

    # サンプルデータを生成
    items = generate_sample_news_items()

    logger.info(f"✓ サンプル ニュース {len(items)} 件を生成")
    logger.info("  - Twitter: 4件")
    logger.info("  - RSS: 4件")
    logger.info("=" * 60)

    return items


def process_and_notify_mock(items: list[NewsItem], dry_run: bool = False) -> bool:
    """
    モック版：DB保存と Slack 通知

    Args:
        items: NewsItem リスト
        dry_run: True の場合、Slack 通知をスキップ

    Returns:
        成功したかどうか
    """
    if not items:
        logger.warning("処理するアイテムがありません")
        return False

    # DB に保存
    logger.info("=" * 60)
    logger.info("データベースに保存中...")
    logger.info("=" * 60)

    db = get_database()
    success_count, error_count = db.insert_news_items_batch(items)

    logger.info(f"✓ {success_count} 件を保存")
    if error_count > 0:
        logger.info(f"  （重複スキップ: {error_count} 件）")

    # Slack 通知
    logger.info("=" * 60)
    logger.info("Slack 通知を送信中...")
    logger.info("=" * 60)

    if dry_run:
        logger.info("🔵 ドライラン：Slack 通知をスキップします")
        logger.info(f"   → 実際には {success_count} 件の記事が通知されます")
        return True
    else:
        # 実際の Slack 通知
        from services.notifier.slack_sender import send_to_slack

        success = send_to_slack(items[:success_count])
        if success:
            logger.info(f"✓ Slack に {success_count} 件を通知しました")
            return True
        else:
            logger.error("✗ Slack 通知に失敗しました")
            logger.info("  → SLACK_WEBHOOK_URL が設定されているか確認してください")
            return False


def print_sample_news(items: list[NewsItem]) -> None:
    """サンプルニュースを表示"""
    logger.info("=" * 60)
    logger.info("生成されたサンプルニュース")
    logger.info("=" * 60)

    for i, item in enumerate(items, 1):
        logger.info(f"\n【{i}】{item.title[:50]}")
        logger.info(f"    ソース: {item.source.upper()}")
        logger.info(f"    キーワード: {', '.join(item.keywords)}")
        logger.info(f"    著者: {item.author or '不明'}")
        logger.info(f"    公開日: {item.published_at.strftime('%Y-%m-%d %H:%M')}")

    logger.info("\n" + "=" * 60)


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description="AI News Monitor - モック版（API なし動作確認）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Slack 通知をスキップ（テスト用）",
    )
    parser.add_argument(
        "--show-samples",
        action="store_true",
        help="生成されたサンプルニュースを表示",
    )
    parser.add_argument(
        "--with-slack",
        action="store_true",
        help="Slack 通知を有効化（SLACK_WEBHOOK_URL 必須）",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("AI News Monitor - モック版")
    logger.info(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    try:
        # サンプルニュースを収集
        items = collect_news_mock()

        # サンプルニュースを表示
        if args.show_samples:
            print_sample_news(items)

        # DB 保存 & Slack 通知
        dry_run = args.dry_run and not args.with_slack
        success = process_and_notify_mock(items, dry_run=dry_run)

        if success:
            logger.info("\n✅ モック版の動作確認が完了しました")
            logger.info("\n次のステップ:")
            logger.info("  1. X API Bearer Token を取得")
            logger.info("  2. Slack Webhook URL を取得")
            logger.info("  3. .env ファイルに認証情報を設定")
            logger.info("  4. python main.py --dry-run で実行")
            logger.info("  5. python main.py で本番実行")
            return 0
        else:
            logger.error("\n❌ 処理に失敗しました")
            return 1

    except Exception as e:
        logger.error(f"予期しないエラー: {e}", exc_info=True)
        return 1

    finally:
        logger.info("=" * 60)
        logger.info("モック版を終了します")
        logger.info("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
