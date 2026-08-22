"""HackerNewsから取得したAI関連情報をHTMLで保存する統合スクリプト。

実データソース（世界中のHackerNews）から取得した情報を、
既存のHTML生成エンジンを使用して保存する。
"""

import logging

from hackernews_scraper import extract_ai_businesses
from business_generator import save_business_html, generate_index_html, ensure_db_dir, DB_DIR

logger = logging.getLogger(__name__)


def export_hackernews_to_html() -> None:
    """HackerNewsから取得したAI関連ビジネス情報をHTMLで保存する。

    1. HackerNews APIからAI関連情報を取得
    2. 各ビジネス情報を個別HTMLとして保存
    3. インデックスページを生成
    """
    ensure_db_dir()

    # HackerNewsから実データを取得
    logger.info("HackerNewsからAI関連ビジネス情報を取得中...")
    businesses = extract_ai_businesses(limit=30)

    if not businesses:
        logger.warning("AI関連ビジネス情報を取得できませんでした")
        return

    logger.info(f"{len(businesses)}件のビジネス情報を取得しました")

    # 各ビジネス情報をHTML個別ファイルとして保存
    for business in businesses:
        save_business_html(business)

    # インデックスページを生成・保存
    index_html = generate_index_html(businesses)
    index_path = DB_DIR / "index.html"

    try:
        index_path.write_text(index_html, encoding="utf-8")
        logger.info(f"インデックスページを保存しました: {index_path}")
        logger.info(f"全{len(businesses)}件のビジネス情報をHTMLで保存完了")
    except OSError as e:
        logger.error(f"インデックスページの保存に失敗しました: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("app.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    export_hackernews_to_html()
