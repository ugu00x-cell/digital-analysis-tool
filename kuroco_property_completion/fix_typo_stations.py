"""誤字駅名を修正し、駅コードも同時に補完"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("誤字駅名の修正 + 駅コード補完")
logger.info("=" * 70)

fixes = {
    '41106800': '朝霞',
    '41104800': '本八幡',
    '41105400': '鴨池',
}

for code, correct_name in fixes.items():
    # project_infoで正しい駅名のコードを確認
    lookup_query = f"""
    SELECT ekikoodo, COUNT(*) as cnt
    FROM `dj-ga4.scd.project_info`
    WHERE ekimei = '{correct_name}' AND ekikoodo IS NOT NULL AND ekikoodo != ''
    GROUP BY ekikoodo
    ORDER BY cnt DESC
    LIMIT 1
    """
    lookup_result = bq.fetch_results(lookup_query)
    ekikoodo = lookup_result[0].ekikoodo if lookup_result else None

    if ekikoodo:
        update_query = f"""
        UPDATE `dj-ga4.scd.research_results`
        SET ekimei = '{correct_name}', ekikoodo = '{ekikoodo}'
        WHERE purojiekutokoodo = '{code}'
        """
        logger.info(f"{code}: 駅名修正 + コード{ekikoodo}を補完")
    else:
        update_query = f"""
        UPDATE `dj-ga4.scd.research_results`
        SET ekimei = '{correct_name}'
        WHERE purojiekutokoodo = '{code}'
        """
        logger.info(f"{code}: 駅名修正のみ（project_infoにコードなし）")

    job = bq.execute_query(update_query)
    logger.info(f"  → affected: {job.num_dml_affected_rows}")

# 確認
logger.info(f"\n=== 修正後の確認 ===")
codes_str = ",".join(f"'{c}'" for c in fixes.keys())
verify_query = f"""
SELECT purojiekutokoodo, bukkenmei, ekimei, ekikoodo, ensenmei, ensenkoodo
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo IN ({codes_str})
"""
results = bq.fetch_results(verify_query)
for row in results:
    logger.info(f"{row.purojiekutokoodo}: {row.bukkenmei}")
    logger.info(f"  駅: {row.ekimei}（コード:{row.ekikoodo}） / 沿線: {row.ensenmei}（コード:{row.ensenkoodo}）")

logger.info("\n" + "=" * 70)
