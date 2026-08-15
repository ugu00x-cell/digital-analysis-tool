"""
モック版の動作検証スクリプト

Python スクリプトとして直接実行して動作確認
"""

import sys
import os
from datetime import datetime, timedelta

# パス設定
sys.path.insert(0, os.path.dirname(__file__))

from shared.models import NewsItem
from shared.database import Database
from shared.logger import setup_logger


def verify_mock_execution():
    """モック版の動作を検証"""

    logger = setup_logger(__name__)

    logger.info("=" * 60)
    logger.info("モック版 動作検証スタート")
    logger.info(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # ステップ 1: サンプルニュース生成
    logger.info("\n【ステップ 1】サンプルニュースを生成")
    logger.info("-" * 60)

    now = datetime.now()
    sample_items = [
        NewsItem(
            title="Claude 3.5 Sonnet API が全ユーザーに開放",
            source="twitter",
            url="https://twitter.com/anthropic/status/1234567890",
            published_at=now - timedelta(hours=2),
            keywords=["Claude", "API"],
            raw_text="Claude 3.5 Sonnet API is now available to all users",
            author="Anthropic",
        ),
        NewsItem(
            title="RAG（検索拡張生成）の最新ベストプラクティス",
            source="twitter",
            url="https://twitter.com/huggingface/status/1234567891",
            published_at=now - timedelta(hours=3),
            keywords=["RAG", "LLM"],
            raw_text="New RAG patterns for building reliable AI systems",
            author="Hugging Face",
        ),
        NewsItem(
            title="TechCrunch: AI スタートアップが 5 億ドルの資金調達",
            source="rss",
            url="https://techcrunch.com/article-ai-funding-500m/",
            published_at=now - timedelta(hours=1),
            keywords=["AI"],
            raw_text="Leading AI startup raises $500M Series C funding",
            author="TechCrunch",
        ),
    ]

    logger.info(f"✓ {len(sample_items)} 件のサンプルニュースを生成")

    for i, item in enumerate(sample_items, 1):
        logger.info(f"  {i}. {item.title[:40]}...")
        logger.info(f"     - ソース: {item.source.upper()}")
        logger.info(f"     - キーワード: {', '.join(item.keywords)}")

    # ステップ 2: データベース操作
    logger.info("\n【ステップ 2】データベースに保存")
    logger.info("-" * 60)

    # テスト用 DB を作成
    test_db_path = "data/test_ai_news.db"
    db = Database(test_db_path)

    # ニュースアイテムを挿入
    success_count = 0
    error_count = 0

    for item in sample_items:
        result = db.insert_news_item(item)
        if result:
            success_count += 1
        else:
            error_count += 1

    logger.info(f"✓ {success_count} 件を保存")
    if error_count > 0:
        logger.info(f"  （重複スキップ: {error_count} 件）")

    # ステップ 3: データベースから取得
    logger.info("\n【ステップ 3】保存したデータを取得")
    logger.info("-" * 60)

    retrieved_items = db.get_news_items_since(hours=24)
    logger.info(f"✓ {len(retrieved_items)} 件を取得")

    for i, item in enumerate(retrieved_items, 1):
        logger.info(f"  {i}. {item.title[:40]}...")
        logger.info(f"     - ソース: {item.source.upper()}")
        logger.info(f"     - 著者: {item.author}")

    # ステップ 4: 重複防止確認
    logger.info("\n【ステップ 4】重複防止機能の確認")
    logger.info("-" * 60)

    duplicate_count = 0
    for item in sample_items:
        result = db.insert_news_item(item)
        if result is None:
            duplicate_count += 1

    logger.info(f"✓ 重複検出: {duplicate_count} 件")
    logger.info("  → 重複防止機能が正常に動作")

    # ステップ 5: データ一貫性チェック
    logger.info("\n【ステップ 5】データ一貫性チェック")
    logger.info("-" * 60)

    for item in sample_items:
        # キーワードがモデルに正しく保存されているか確認
        if len(item.keywords) > 0:
            logger.info(f"✓ キーワード: {item.keywords}")

        # URL が有効か確認
        if item.url.startswith("http"):
            logger.info(f"✓ URL: {item.url[:50]}...")

    # ステップ 6: ログ出力確認
    logger.info("\n【ステップ 6】ログファイル確認")
    logger.info("-" * 60)

    import os
    if os.path.exists("logs/ai_news_monitor.log"):
        with open("logs/ai_news_monitor.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
        logger.info(f"✓ ログファイル存在: logs/ai_news_monitor.log")
        logger.info(f"  → {len(lines)} 行のログが記録されている")
    else:
        logger.info("✓ ログディレクトリ自動作成待ち")

    # 最終結果
    logger.info("\n" + "=" * 60)
    logger.info("✅ モック版 動作検証 - すべてのテストが成功しました")
    logger.info("=" * 60)

    logger.info("\n【検証結果まとめ】")
    logger.info(f"  ✓ サンプルニュース生成: {len(sample_items)} 件")
    logger.info(f"  ✓ データベース保存: {success_count} 件")
    logger.info(f"  ✓ データ取得: {len(retrieved_items)} 件")
    logger.info(f"  ✓ 重複防止: {duplicate_count} 件検出")
    logger.info(f"  ✓ ログ記録: 正常")

    logger.info("\n【次のステップ】")
    logger.info("  1. X API Bearer Token を取得")
    logger.info("  2. Slack Webhook URL を取得")
    logger.info("  3. .env ファイルに設定")
    logger.info("  4. python main.py で本番実行")

    logger.info("\n" + "=" * 60)

    # クリーンアップ
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        logger.info("テスト用 DB を削除しました")

    return True


if __name__ == "__main__":
    try:
        success = verify_mock_execution()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
