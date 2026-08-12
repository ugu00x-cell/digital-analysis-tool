"""project_info全体のグローバルマスタから駅コード・沿線コードを埋める"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("グローバルマスタから駅コード・沿線コードを補完")
logger.info("=" * 70)

# 補完前の状態確認
before_query = """
SELECT
    COUNT(*) as total,
    COUNTIF(ekimei IS NOT NULL AND ekimei != '') as ekimei_filled,
    COUNTIF(ekikoodo IS NOT NULL AND ekikoodo != '') as ekikoodo_filled,
    COUNTIF(ensenmei IS NOT NULL AND ensenmei != '') as ensenmei_filled,
    COUNTIF(ensenkoodo IS NOT NULL AND ensenkoodo != '') as ensenkoodo_filled
FROM `dj-ga4.scd.research_results`
"""
before = bq.fetch_results(before_query)[0]
logger.info(f"\n【補完前】")
logger.info(f"ekimei入力済み: {before.ekimei_filled}件 / ekikoodo入力済み: {before.ekikoodo_filled}件")
logger.info(f"ensenmei入力済み: {before.ensenmei_filled}件 / ensenkoodo入力済み: {before.ensenkoodo_filled}件")

# 駅名マスタ：同名駅で複数コードがある場合は出現件数の多い方を代表値として採用
# MERGE文（JOIN形式）で書き直し（相関サブクエリ制限を回避）
ekikoodo_update_query = """
MERGE INTO `dj-ga4.scd.research_results` r
USING (
    SELECT ekimei, ekikoodo
    FROM (
        SELECT
            ekimei,
            ekikoodo,
            COUNT(*) as cnt,
            ROW_NUMBER() OVER (PARTITION BY ekimei ORDER BY COUNT(*) DESC) as rn
        FROM `dj-ga4.scd.project_info`
        WHERE ekimei IS NOT NULL AND ekimei != '' AND ekikoodo IS NOT NULL AND ekikoodo != ''
        GROUP BY ekimei, ekikoodo
    )
    WHERE rn = 1
) m
ON r.ekimei = m.ekimei
    AND r.ekimei IS NOT NULL AND r.ekimei != ''
    AND (r.ekikoodo IS NULL OR r.ekikoodo = '')
WHEN MATCHED THEN
    UPDATE SET r.ekikoodo = m.ekikoodo
"""

logger.info(f"\n【駅コード補完を実行中】")
job = bq.execute_query(ekikoodo_update_query)
logger.info(f"✓ 完了 (affected: {job.num_dml_affected_rows})")

# 沿線名マスタも同様に補完
ensenkoodo_update_query = """
MERGE INTO `dj-ga4.scd.research_results` r
USING (
    SELECT ensenmei, ensenkoodo
    FROM (
        SELECT
            ensenmei,
            ensenkoodo,
            COUNT(*) as cnt,
            ROW_NUMBER() OVER (PARTITION BY ensenmei ORDER BY COUNT(*) DESC) as rn
        FROM `dj-ga4.scd.project_info`
        WHERE ensenmei IS NOT NULL AND ensenmei != '' AND ensenkoodo IS NOT NULL AND ensenkoodo != ''
        GROUP BY ensenmei, ensenkoodo
    )
    WHERE rn = 1
) m
ON r.ensenmei = m.ensenmei
    AND r.ensenmei IS NOT NULL AND r.ensenmei != ''
    AND (r.ensenkoodo IS NULL OR r.ensenkoodo = '')
WHEN MATCHED THEN
    UPDATE SET r.ensenkoodo = m.ensenkoodo
"""

logger.info(f"\n【沿線コード補完を実行中】")
job2 = bq.execute_query(ensenkoodo_update_query)
logger.info(f"✓ 完了 (affected: {job2.num_dml_affected_rows})")

# 補完後の状態確認
after = bq.fetch_results(before_query)[0]
logger.info(f"\n【補完後】")
logger.info(f"ekikoodo入力済み: {after.ekikoodo_filled}件（ekimei有り{after.ekimei_filled}件中）")
logger.info(f"ensenkoodo入力済み: {after.ensenkoodo_filled}件（ensenmei有り{after.ensenmei_filled}件中）")

if after.ekimei_filled > 0:
    logger.info(f"駅コード補完率: {after.ekikoodo_filled / after.ekimei_filled * 100:.1f}%")
if after.ensenmei_filled > 0:
    logger.info(f"沿線コード補完率: {after.ensenkoodo_filled / after.ensenmei_filled * 100:.1f}%")

logger.info("\n" + "=" * 70)
