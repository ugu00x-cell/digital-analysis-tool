"""サブクエリを使った UPDATE で反映"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 60)
logger.info("サブクエリを使った UPDATE で project_info のデータを反映")
logger.info("=" * 60)

# 更新前の状態確認
before_query = """
SELECT
    COUNT(*) as total,
    COUNTIF(ekimei IS NOT NULL AND ekimei != '') as station_filled,
    COUNTIF(ensenmei IS NOT NULL AND ensenmei != '') as line_filled,
    COUNTIF(soukosuujuukyo IS NOT NULL AND soukosuujuukyo != '') as units_filled
FROM `dj-ga4.scd.research_results`
"""

before = bq.fetch_results(before_query)[0]
logger.info(f"\n=== 更新前 ===")
logger.info(f"駅名: {before.station_filled}件")
logger.info(f"沿線: {before.line_filled}件")
logger.info(f"総戸数: {before.units_filled}件")

# サブクエリを使った UPDATE
update_query = """
UPDATE `dj-ga4.scd.research_results` r
SET
    r.ekimei = p.ekimei,
    r.ensenmei = p.ensenmei,
    r.soukosuujuukyo = p.soukosuujuukyo
FROM (
    SELECT
        purojiekutokoodo,
        ekimei,
        ensenmei,
        soukosuujuukyo
    FROM `dj-ga4.scd.project_info`
    WHERE ekimei IS NOT NULL OR ensenmei IS NOT NULL OR soukosuujuukyo IS NOT NULL
) p
WHERE r.purojiekutokoodo = p.purojiekutokoodo
    AND (r.ekimei IS NULL OR r.ekimei = '')
"""

logger.info(f"\n[データ反映] を実行中...")
try:
    bq.execute_query(update_query)
    logger.info(f"✓ データ反映完了")
except Exception as e:
    logger.error(f"✗ エラー: {e}")

# 更新後の状態確認
logger.info(f"\n=== 更新後 ===")
after = bq.fetch_results(before_query)[0]
logger.info(f"駅名: {after.station_filled}件（増加分: +{after.station_filled - before.station_filled}件）")
logger.info(f"沿線: {after.line_filled}件（増加分: +{after.line_filled - before.line_filled}件）")
logger.info(f"総戸数: {after.units_filled}件（増加分: +{after.units_filled - before.units_filled}件）")

# 実際のデータ確認
logger.info(f"\n=== 実際のデータ確認（36210004） ===")
sample_query = """
SELECT purojiekutokoodo, bukkenmei, ekimei, ensenmei, soukosuujuukyo
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo = '36210004'
"""

sample = bq.fetch_results(sample_query)
if sample:
    row = sample[0]
    logger.info(f"{row.purojiekutokoodo}: {row.bukkenmei}")
    logger.info(f"  駅名: {row.ekimei}")
    logger.info(f"  沿線: {row.ensenmei}")
    logger.info(f"  総戸数: {row.soukosuujuukyo}")

logger.info("\n" + "=" * 60)
logger.info("✅ 完了")
logger.info("=" * 60)
