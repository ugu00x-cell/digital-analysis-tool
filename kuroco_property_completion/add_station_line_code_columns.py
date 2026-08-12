"""research_results に ekikoodo・ensenkoodo カラムを追加"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("research_results に ekikoodo・ensenkoodo カラムを追加")
logger.info("=" * 70)

alter_query = """
ALTER TABLE `dj-ga4.scd.research_results`
ADD COLUMN IF NOT EXISTS ekikoodo STRING,
ADD COLUMN IF NOT EXISTS ensenkoodo STRING
"""

try:
    job = bq.execute_query(alter_query)
    logger.info("✓ カラム追加完了")
except Exception as e:
    logger.error(f"✗ エラー: {e}")

# 確認
verify_query = """
SELECT column_name, data_type
FROM `dj-ga4.scd.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = 'research_results'
ORDER BY ordinal_position
"""
results = bq.fetch_results(verify_query)
logger.info("\n現在のカラム一覧:")
for row in results:
    logger.info(f"  {row.column_name} ({row.data_type})")
