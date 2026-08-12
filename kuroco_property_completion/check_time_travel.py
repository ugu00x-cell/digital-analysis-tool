"""BigQuery タイムトラベル機能で、過去の正確な状態を確認（読み取り専用・安全）"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("🌙 甘雨より：タイムトラベル機能で過去の状態を確認いたします（読み取り専用）")
logger.info("=" * 70)

# 最初の CREATE OR REPLACE TABLE が実行される前（14:56:24 JST より前）の状態を確認
# ログの時刻はJST（日本時間）なので +09:00 を明示指定
candidate_times = [
    "2026-08-11 14:50:00+09:00",  # 郵便番号117件補完直後
    "2026-08-11 14:45:00+09:00",  # 補完前
    "2026-08-11 14:56:00+09:00",  # 最初のCREATE OR REPLACE直前
]

for ts in candidate_times:
    query = f"""
    SELECT COUNT(*) as cnt
    FROM `dj-ga4.scd.research_results`
    FOR SYSTEM_TIME AS OF TIMESTAMP('{ts}')
    """

    logger.info(f"\n【{ts} JST 時点の状態を確認】")
    try:
        result = bq.fetch_results(query)
        if result:
            logger.info(f"  行数: {result[0].cnt}件")
    except Exception as e:
        logger.error(f"  ✗ このタイムスタンプは取得できません: {e}")

logger.info("\n" + "=" * 70)
logger.info("確認完了")
logger.info("=" * 70)
