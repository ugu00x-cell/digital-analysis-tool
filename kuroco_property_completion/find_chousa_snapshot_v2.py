"""本日さらに早い時間帯(午前〜午後早め)を確認"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("🌙 甘雨より：本日さらに早い時間帯を探索いたします")
logger.info("=" * 70)

candidate_times = [
    "2026-08-11 09:00:00+09:00",
    "2026-08-11 10:00:00+09:00",
    "2026-08-11 11:00:00+09:00",
    "2026-08-11 12:00:00+09:00",
    "2026-08-11 13:00:00+09:00",
    "2026-08-11 13:30:00+09:00",
    "2026-08-11 13:46:00+09:00",  # このセッション最初の全タスク完了直後
]

for ts in candidate_times:
    query = f"""
    SELECT
        COUNT(*) as total,
        COUNTIF(chousa_bukkenmei IS NOT NULL AND chousa_bukkenmei != '') as chousa_filled
    FROM `dj-ga4.scd.research_results`
    FOR SYSTEM_TIME AS OF TIMESTAMP('{ts}')
    """
    try:
        result = bq.fetch_results(query)
        if result:
            r = result[0]
            logger.info(f"{ts}: 総件数={r.total} chousa_bukkenmei={r.chousa_filled}")
    except Exception as e:
        logger.warning(f"{ts}: 取得できません（タイムトラベル範囲外の可能性） - {str(e)[:100]}")

logger.info("=" * 70)
