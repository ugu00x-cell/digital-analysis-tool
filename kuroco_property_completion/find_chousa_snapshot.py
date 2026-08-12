"""chousa_bukkenmeiが入っているタイムトラベルスナップショットを探す（読み取り専用・安全）"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("🌙 甘雨より：chousa_bukkenmei が入っている時刻を探索いたします")
logger.info("=" * 70)

# 14:44以降、本日中の広範囲を候補にする（BigQueryのタイムトラベルは過去7日まで対応）
candidate_times = [
    "2026-08-11 15:00:00+09:00",
    "2026-08-11 15:15:00+09:00",
    "2026-08-11 15:20:00+09:00",
    "2026-08-11 15:30:00+09:00",
    "2026-08-11 15:35:00+09:00",
    "2026-08-11 15:40:00+09:00",
    "2026-08-11 15:43:00+09:00",  # このセッションが最後に巻き戻した時刻
    "2026-08-11 16:00:00+09:00",
    "2026-08-11 16:30:00+09:00",
    "2026-08-11 17:00:00+09:00",
    "2026-08-11 17:30:00+09:00",
    "2026-08-11 18:00:00+09:00",
    "2026-08-11 18:15:00+09:00",  # 現在に近い時刻
]

results_summary = []

for ts in candidate_times:
    query = f"""
    SELECT
        COUNT(*) as total,
        COUNTIF(chousa_bukkenmei IS NOT NULL AND chousa_bukkenmei != '') as chousa_filled,
        COUNTIF(yubinkodo1 IS NOT NULL AND yubinkodo1 != '') as zip_filled
    FROM `dj-ga4.scd.research_results`
    FOR SYSTEM_TIME AS OF TIMESTAMP('{ts}')
    """

    try:
        result = bq.fetch_results(query)
        if result:
            r = result[0]
            logger.info(f"{ts}: 総件数={r.total} chousa_bukkenmei={r.chousa_filled} 郵便番号={r.zip_filled}")
            results_summary.append((ts, r.total, r.chousa_filled, r.zip_filled))
    except Exception as e:
        logger.warning(f"{ts}: 取得できません ({str(e)[:80]})")

logger.info(f"\n{'=' * 70}")
logger.info("【サマリー】chousa_bukkenmeiが1件以上入っている時刻:")
found_any = False
for ts, total, chousa, zip_f in results_summary:
    if chousa > 0:
        logger.info(f"  ✓ {ts}: 総件数={total} chousa_bukkenmei={chousa}件 郵便番号={zip_f}件")
        found_any = True

if not found_any:
    logger.warning("  該当する時刻が見つかりませんでした（探索範囲を広げる必要があります）")

logger.info("=" * 70)
