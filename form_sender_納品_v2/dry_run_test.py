"""ドライランテスト - 10社に対してフォーム解析・入力まで実行（送信しない）"""

import logging
import sys
import time
from pathlib import Path

import pandas as pd

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from utils.db import init_db
from utils.db_cache import get_cache_stats, get_form_cache
from utils.form_sender import send_to_company, random_wait

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("dry_run.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def main() -> None:
    """ドライランテストのメイン処理"""
    init_db()

    # CSV読み込み
    csv_path = Path(__file__).parent / "data" / "input" / "dry_run_10.csv"
    df = pd.read_csv(csv_path)
    logger.info("=== ドライランテスト開始: %d社 ===", len(df))

    # ダミー差出人情報
    sender = {
        "company": "テスト株式会社",
        "last_name": "山田",
        "first_name": "太郎",
        "name": "山田 太郎",
        "last_kana": "ヤマダ",
        "first_kana": "タロウ",
        "kana": "ヤマダ タロウ",
        "email": "test@example.com",
        "phone": "03-0000-0000",
        "postal": "100-0001",
        "address": "東京都千代田区千代田1-1",
    }

    message = "テスト株式会社の山田と申します。ドライランテストです。"
    results = []

    for i, row in df.iterrows():
        company = row["企業名"]
        url = row["URL"]
        logger.info("[%d/%d] %s", i + 1, len(df), company)

        result = send_to_company(
            url=url,
            company_name=company,
            message=message,
            sender=sender,
            headless=True,
            dry_run=True,
        )

        results.append({
            "企業名": company,
            "URL": url,
            "ステータス": result["status"],
            "詳細": result["detail"],
            "AI使用": result.get("ai_used", False),
            "キャッシュ使用": result.get("cache_used", False),
        })

        logger.info("  → %s: %s", result["status"], result["detail"])

        # ウェイト（最後以外、短縮版: 3〜5秒）
        if i < len(df) - 1:
            wait = 3 + (i % 3)
            logger.info("  → %d秒待機", wait)
            time.sleep(wait)

    # 結果サマリー
    logger.info("=== ドライラン結果サマリー ===")
    status_counts = {}
    for r in results:
        s = r["ステータス"]
        status_counts[s] = status_counts.get(s, 0) + 1

    for status, count in status_counts.items():
        logger.info("  %s: %d件", status, count)

    # 結果CSV出力
    result_df = pd.DataFrame(results)
    out_path = Path(__file__).parent / "data" / "logs" / "dry_run_results.csv"
    result_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info("結果CSV: %s", out_path)

    # キャッシュ統計を表示
    cache_stats = get_cache_stats()
    logger.info("キャッシュ統計: 総数=%d, 信頼=%d",
                cache_stats["total_cached"], cache_stats["reliable_count"])

    print("\n" + "=" * 50)
    print("ドライラン完了！")
    print("=" * 50)
    print(result_df.to_string(index=False))


if __name__ == "__main__":
    main()
