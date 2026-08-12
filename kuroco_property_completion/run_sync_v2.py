"""project_info から research_results へデータを同期するスクリプト（改良版）"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=== 郵便番号の同期を開始 ===")

# MERGE を使用した同期（BigQuery推奨方式）
merge_query = """
MERGE INTO `dj-ga4.scd.research_results` r
USING (
    SELECT DISTINCT
        purojiekutokoodo,
        yuubinbangou1_ue3keta as zip1,
        yuubinbangou2_shita4keta as zip2
    FROM `dj-ga4.scd.project_info`
    WHERE yuubinbangou1_ue3keta IS NOT NULL AND yuubinbangou1_ue3keta != ''
) p
ON r.purojiekutokoodo = p.purojiekutokoodo
WHEN MATCHED AND (r.yubinkodo1 IS NULL OR r.yubinkodo1 = '') THEN
    UPDATE SET
        r.yubinkodo1 = p.zip1,
        r.yubinkodo2 = p.zip2
"""

logger.info("MERGE クエリを実行中...")
try:
    bq.execute_query(merge_query)
    logger.info("✓ 郵便番号の同期が完了しました")
except Exception as e:
    logger.error(f"✗ MERGE エラー: {e}")

# 同期後の状態確認
logger.info("\n=== 同期後の状態を確認 ===")
check_query = """
SELECT
    COUNT(*) as total,
    COUNTIF(yubinkodo1 IS NOT NULL AND yubinkodo1 != '') as zip_filled,
    COUNTIF(yubinkodo1 IS NULL OR yubinkodo1 = '') as zip_empty
FROM `dj-ga4.scd.research_results`
"""

results = bq.fetch_results(check_query)
if results:
    row = results[0]
    logger.info(f"総件数: {row.total}件")
    logger.info(f"郵便番号入力済み: {row.zip_filled}件")
    logger.info(f"郵便番号未入力: {row.zip_empty}件")
    if row.total > 0:
        logger.info(f"補完率: {row.zip_filled / row.total * 100:.1f}%")

# 実際のサンプルデータを確認
logger.info("\n=== サンプルデータ確認 ===")
sample_query = """
SELECT purojiekutokoodo, bukkenmei, yubinkodo1, yubinkodo2
FROM `dj-ga4.scd.research_results`
WHERE yubinkodo1 IS NOT NULL AND yubinkodo1 != ''
LIMIT 3
"""

samples = bq.fetch_results(sample_query)
for row in samples:
    logger.info(f"{row.purojiekutokoodo} | {row.bukkenmei} | {row.yubinkodo1}-{row.yubinkodo2}")
