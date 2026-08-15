"""research_resultsの補完データをproject_infoへ反映（project_info側が空欄の項目のみ上書き）"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("project_info への反映を開始")
logger.info("=" * 70)

# 通常カラム（空欄のみ上書き）
columns = [
    ('yubinkodo1', 'yuubinbangou1_ue3keta'),
    ('yubinkodo2', 'yuubinbangou2_shita4keta'),
    ('ekimei', 'ekimei'),
    ('ensenmei', 'ensenmei'),
    ('soukosuujuukyo', 'soukosuujuukyo'),
    ('ekikoodo', 'ekikoodo'),
    ('ensenkoodo', 'ensenkoodo'),
]

total_affected = 0

for r_col, p_col in columns:
    query = f"""
    MERGE INTO `dj-ga4.scd.project_info` p
    USING `dj-ga4.scd.research_results` r
    ON r.purojiekutokoodo = p.purojiekutokoodo
        AND r.purojiekutoedaban = p.purojiekutoedaban
    WHEN MATCHED AND r.{r_col} IS NOT NULL AND r.{r_col} != ''
        AND (p.{p_col} IS NULL OR p.{p_col} = '') THEN
        UPDATE SET p.{p_col} = r.{r_col}
    """
    job = bq.execute_query(query)
    affected = job.num_dml_affected_rows or 0
    total_affected += affected
    logger.info(f"✓ {r_col} → {p_col}: {affected}件 反映")

# tochinokenrikubun（「空欄 or 不明」の場合のみ上書き）
rights_query = """
MERGE INTO `dj-ga4.scd.project_info` p
USING `dj-ga4.scd.research_results` r
ON r.purojiekutokoodo = p.purojiekutokoodo
    AND r.purojiekutoedaban = p.purojiekutoedaban
WHEN MATCHED AND r.tochinokenrikubun IS NOT NULL AND r.tochinokenrikubun != '' AND r.tochinokenrikubun != '不明'
    AND (p.tochinokenrikubun IS NULL OR p.tochinokenrikubun = '' OR p.tochinokenrikubun = '不明') THEN
    UPDATE SET p.tochinokenrikubun = r.tochinokenrikubun
"""
job_rights = bq.execute_query(rights_query)
affected_rights = job_rights.num_dml_affected_rows or 0
total_affected += affected_rights
logger.info(f"✓ tochinokenrikubun → tochinokenrikubun: {affected_rights}件 反映")

logger.info(f"\n合計反映件数: {total_affected}件")

# 最終確認
verify_query = """
SELECT
    COUNTIF(yuubinbangou1_ue3keta IS NOT NULL AND yuubinbangou1_ue3keta != '') as zip_filled,
    COUNTIF(ekimei IS NOT NULL AND ekimei != '') as ekimei_filled,
    COUNTIF(ensenmei IS NOT NULL AND ensenmei != '') as ensenmei_filled,
    COUNTIF(soukosuujuukyo IS NOT NULL AND soukosuujuukyo != '') as units_filled,
    COUNTIF(ekikoodo IS NOT NULL AND ekikoodo != '') as ekikoodo_filled,
    COUNTIF(ensenkoodo IS NOT NULL AND ensenkoodo != '') as ensenkoodo_filled,
    COUNTIF(tochinokenrikubun IS NOT NULL AND tochinokenrikubun != '' AND tochinokenrikubun != '不明') as rights_filled
FROM `dj-ga4.scd.project_info`
"""
v = bq.fetch_results(verify_query)[0]
logger.info(f"\n=== project_info 反映後の状態(全7702件中) ===")
logger.info(f"郵便番号: {v.zip_filled}件")
logger.info(f"駅名: {v.ekimei_filled}件 / 沿線名: {v.ensenmei_filled}件")
logger.info(f"総戸数: {v.units_filled}件")
logger.info(f"駅コード: {v.ekikoodo_filled}件 / 沿線コード: {v.ensenkoodo_filled}件")
logger.info(f"土地権利確定: {v.rights_filled}件")

logger.info("\n" + "=" * 70)
logger.info("✅ project_info への反映完了")
logger.info("=" * 70)
