"""research_results テーブルを重複排除して復元"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("research_results テーブルを復元（重複排除）")
logger.info("=" * 70)

# 現在の行数
current = bq.fetch_results('SELECT COUNT(*) as cnt FROM `dj-ga4.scd.research_results`')[0]
logger.info(f"\n現在の行数: {current.cnt}件")

# 重複排除して復元
restore_query = """
CREATE OR REPLACE TABLE `dj-ga4.scd.research_results` AS
SELECT DISTINCT *
FROM `dj-ga4.scd.research_results`
"""

logger.info(f"重複排除を実行中...")
try:
    bq.execute_query(restore_query)
    logger.info(f"✓ 復元完了")
except Exception as e:
    logger.error(f"✗ エラー: {e}")

# 復元後の行数
after = bq.fetch_results('SELECT COUNT(*) as cnt FROM `dj-ga4.scd.research_results`')[0]
logger.info(f"\n復元後の行数: {after.cnt}件")
logger.info(f"削除された重複行: {current.cnt - after.cnt}件")

logger.info("\n" + "=" * 70)
logger.info("✅ テーブル復元完了")
logger.info("=" * 70)
