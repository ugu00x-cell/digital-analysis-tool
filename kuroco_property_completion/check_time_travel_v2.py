"""より古い時刻でタイムトラベル確認（読み取り専用・安全）"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("🌙 甘雨より：より古い時刻でタイムトラベル確認いたします（読み取り専用）")
logger.info("=" * 70)

# 本日の作業タイムライン全体をカバーする候補時刻
candidate_times = [
    "2026-08-11 13:47:00+09:00",  # 最初の全タスク完了直後
    "2026-08-11 13:50:00+09:00",
    "2026-08-11 14:00:00+09:00",
    "2026-08-11 14:20:00+09:00",
    "2026-08-11 14:30:00+09:00",
    "2026-08-11 14:40:00+09:00",
    "2026-08-11 14:44:00+09:00",  # 郵便番号補完スクリプト実行直前
    "2026-08-11 14:43:00+09:00",  # run_full_sync.py 実行時点
]

results_summary = []

for ts in candidate_times:
    query = f"""
    SELECT
        COUNT(*) as total,
        COUNTIF(yubinkodo1 IS NOT NULL AND yubinkodo1 != '') as zip_filled,
        COUNTIF(LENGTH(yubinkodo1) = 3 AND LENGTH(yubinkodo2) = 4) as correct_zip_format
    FROM `dj-ga4.scd.research_results`
    FOR SYSTEM_TIME AS OF TIMESTAMP('{ts}')
    """

    logger.info(f"\n【{ts} 時点】")
    try:
        result = bq.fetch_results(query)
        if result:
            r = result[0]
            logger.info(f"  総行数: {r.total}件 | 郵便番号入力: {r.zip_filled}件 | 正常形式: {r.correct_zip_format}件")
            results_summary.append((ts, r.total, r.zip_filled, r.correct_zip_format))
    except Exception as e:
        logger.error(f"  ✗ 取得できません: {e}")

logger.info(f"\n\n{'=' * 70}")
logger.info("【サマリー一覧】")
logger.info(f"{'時刻':<30} {'総行数':<10} {'郵便番号':<10} {'正常形式':<10}")
for ts, total, zip_filled, correct in results_summary:
    logger.info(f"{ts:<30} {total:<10} {zip_filled:<10} {correct:<10}")

logger.info("\n" + "=" * 70)
logger.info("確認完了")
logger.info("=" * 70)
