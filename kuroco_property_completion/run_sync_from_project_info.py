"""project_info から research_results へデータを同期するスクリプト"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

# project_info の住所・郵便番号・駅・沿線データを確認
query = """
SELECT
    COUNT(*) as total,
    COUNTIF(yuubinbangou1_ue3keta IS NOT NULL AND yuubinbangou1_ue3keta != '') as zip_count,
    COUNTIF(ensenkoodo IS NOT NULL AND ensenkoodo != '') as line_count,
    COUNTIF(ekikoodo IS NOT NULL AND ekikoodo != '') as station_count
FROM `dj-ga4.scd.project_info`
"""

results = bq.fetch_results(query)
row = results[0]

logger.info(f"=== project_info の入力状況 ===")
logger.info(f"総件数: {row.total}件")
logger.info(f"郵便番号: {row.zip_count}件入力済み")
logger.info(f"沿線コード: {row.line_count}件入力済み")
logger.info(f"駅コード: {row.station_count}件入力済み")

# research_results と project_info を JOIN して、郵便番号を取得
sync_query = """
UPDATE `dj-ga4.scd.research_results` r
SET
    r.yubinkodo1 = p.yuubinbangou1_ue3keta,
    r.yubinkodo2 = p.yuubinbangou2_shita4keta
FROM `dj-ga4.scd.project_info` p
WHERE r.purojiekutokoodo = p.purojiekutokoodo
    AND p.yuubinbangou1_ue3keta IS NOT NULL
    AND p.yuubinbangou1_ue3keta != ''
    AND (r.yubinkodo1 IS NULL OR r.yubinkodo1 = '')
"""

logger.info(f"\n実行SQL:\n{sync_query}")

try:
    bq.execute_query(sync_query)
    logger.info("✓ 郵便番号の同期が完了しました")
except Exception as e:
    logger.error(f"✗ 同期エラー: {e}")

# 同期後の状態確認
check_query = """
SELECT
    COUNT(*) as total,
    COUNTIF(yubinkodo1 IS NOT NULL AND yubinkodo1 != '') as zip_filled
FROM `dj-ga4.scd.research_results`
"""

results = bq.fetch_results(check_query)
row = results[0]
logger.info(f"\n=== 同期後の research_results ===")
logger.info(f"総件数: {row.total}件")
logger.info(f"郵便番号入力済み: {row.zip_filled}件")
logger.info(f"補完率: {row.zip_filled / row.total * 100:.1f}%")
