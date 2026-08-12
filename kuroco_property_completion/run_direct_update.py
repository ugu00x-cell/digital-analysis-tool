"""project_info のデータを research_results に直接反映"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 60)
logger.info("直接 UPDATE で project_info のデータを research_results に反映")
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

# 駅名・沿線・総戸数を更新（NULL の場合のみ）
updates = [
    ("ekimei", "駅名"),
    ("ensenmei", "沿線"),
    ("soukosuujuukyo", "総戸数"),
]

for col, label in updates:
    update_query = f"""
    UPDATE `dj-ga4.scd.research_results` r
    SET r.{col} = p.{col}
    FROM `dj-ga4.scd.project_info` p
    WHERE r.purojiekutokoodo = p.purojiekutokoodo
        AND (r.{col} IS NULL OR r.{col} = '')
        AND p.{col} IS NOT NULL
        AND p.{col} != ''
    """

    logger.info(f"\n[{label}] を更新中...")
    try:
        bq.execute_query(update_query)
        logger.info(f"✓ {label} の更新完了")
    except Exception as e:
        logger.error(f"✗ {label} の更新エラー: {e}")

# 更新後の状態確認
logger.info(f"\n=== 更新後 ===")
after = bq.fetch_results(before_query)[0]
logger.info(f"駅名: {after.station_filled}件（増加分: +{after.station_filled - before.station_filled}件）")
logger.info(f"沿線: {after.line_filled}件（増加分: +{after.line_filled - before.line_filled}件）")
logger.info(f"総戸数: {after.units_filled}件（増加分: +{after.units_filled - before.units_filled}件）")

logger.info("\n" + "=" * 60)
logger.info("✅ 更新完了")
logger.info("=" * 60)
