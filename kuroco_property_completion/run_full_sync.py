"""project_info から全データを research_results へ一括同期"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 60)
logger.info("PHASE 1-5: project_info から全データを一括同期")
logger.info("=" * 60)

# 1. 同期対象のカラムマッピング確認
query_check = """
SELECT
    COUNT(*) as total,
    COUNTIF(yuubinbangou1_ue3keta IS NOT NULL AND yuubinbangou1_ue3keta != '') as zip_count,
    COUNTIF(ekimei IS NOT NULL AND ekimei != '') as station_name_count,
    COUNTIF(ensenmei IS NOT NULL AND ensenmei != '') as line_name_count,
    COUNTIF(tochinokenrikubun IS NOT NULL AND tochinokenrikubun != '') as land_rights_count,
    COUNTIF(soukosuujuukyo IS NOT NULL AND soukosuujuukyo != '') as total_units_count
FROM `dj-ga4.scd.project_info`
"""

results = bq.fetch_results(query_check)
row = results[0]

logger.info("\n=== project_info の入力状況 ===")
logger.info(f"総件数: {row.total}件")
logger.info(f"郵便番号: {row.zip_count}件")
logger.info(f"駅名: {row.station_name_count}件")
logger.info(f"沿線名: {row.line_name_count}件")
logger.info(f"土地権利区分: {row.land_rights_count}件")
logger.info(f"総戸数: {row.total_units_count}件")

# 2. research_results の現状確認
logger.info("\n=== research_results の現状 ===")
query_research = """
SELECT
    COUNT(*) as total,
    COUNTIF(yubinkodo1 IS NOT NULL AND yubinkodo1 != '') as zip_filled,
    COUNTIF(ekimei IS NOT NULL AND ekimei != '') as station_name_filled,
    COUNTIF(ensenmei IS NOT NULL AND ensenmei != '') as line_name_filled,
    COUNTIF(tochinokenrikubun IS NOT NULL AND tochinokenrikubun != '') as land_rights_filled,
    COUNTIF(soukosuujuukyo IS NOT NULL AND soukosuujuukyo != '') as total_units_filled
FROM `dj-ga4.scd.research_results`
"""

results_research = bq.fetch_results(query_research)
r = results_research[0]

logger.info(f"総件数: {r.total}件")
logger.info(f"郵便番号: {r.zip_filled}件入力済み")
logger.info(f"駅名: {r.station_name_filled}件入力済み")
logger.info(f"沿線名: {r.line_name_filled}件入力済み")
logger.info(f"土地権利区分: {r.land_rights_filled}件入力済み")
logger.info(f"総戸数: {r.total_units_filled}件入力済み")

# 3. 一括同期（SQL MERGE）
logger.info("\n=== 一括同期を実行中 ===")

sync_query = """
MERGE INTO `dj-ga4.scd.research_results` r
USING (
    SELECT
        purojiekutokoodo,
        yuubinbangou1_ue3keta as zip1,
        yuubinbangou2_shita4keta as zip2,
        ekimei,
        ensenmei,
        tochinokenrikubun,
        soukosuujuukyo
    FROM `dj-ga4.scd.project_info`
    WHERE purojiekutokoodo IS NOT NULL
) p
ON r.purojiekutokoodo = p.purojiekutokoodo
WHEN MATCHED THEN
    UPDATE SET
        r.yubinkodo1 = COALESCE(r.yubinkodo1, p.zip1),
        r.yubinkodo2 = COALESCE(r.yubinkodo2, p.zip2),
        r.ekimei = COALESCE(r.ekimei, p.ekimei),
        r.ensenmei = COALESCE(r.ensenmei, p.ensenmei),
        r.tochinokenrikubun = COALESCE(r.tochinokenrikubun, p.tochinokenrikubun),
        r.soukosuujuukyo = COALESCE(r.soukosuujuukyo, p.soukosuujuukyo)
"""

try:
    bq.execute_query(sync_query)
    logger.info("✓ 一括同期を実行しました")
except Exception as e:
    logger.error(f"✗ 同期エラー: {e}")

# 4. 同期後の状態確認
logger.info("\n=== 同期後の research_results ===")

results_after = bq.fetch_results(query_research)
a = results_after[0]

logger.info(f"総件数: {a.total}件")
logger.info(f"郵便番号: {a.zip_filled}件入力済み（増加分: +{a.zip_filled - r.zip_filled}件）")
logger.info(f"駅名: {a.station_name_filled}件入力済み（増加分: +{a.station_name_filled - r.station_name_filled}件）")
logger.info(f"沿線名: {a.line_name_filled}件入力済み（増加分: +{a.line_name_filled - r.line_name_filled}件）")
logger.info(f"土地権利区分: {a.land_rights_filled}件入力済み（増加分: +{a.land_rights_filled - r.land_rights_filled}件）")
logger.info(f"総戸数: {a.total_units_filled}件入力済み（増加分: +{a.total_units_filled - r.total_units_filled}件）")

logger.info("\n" + "=" * 60)
logger.info("✅ 一括同期が完了しました")
logger.info("=" * 60)
