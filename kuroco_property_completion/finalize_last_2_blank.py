"""最後の2件(40107100, 41100400)も確定13件と同様に空欄確定とする"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("最後の2件を空欄確定（chousa_bukkenmei = NULL のまま確定）")
logger.info("=" * 70)

# chousa_bukkenmei は既にNULLのままだが、biko に「調査したが特定不可」の
# 確認済みメモを残す（既存bikoを上書きしないよう、既存内容を踏まえて追記）
codes = {
    '40107100': '参照元URL(タイムス住宅新聞)削除済み。最寄り駅情報未確認のまま特定不可で確定',
    '41100400': '参照元URL(荏田西エリア一覧)から総合地所開発物件を特定できず。マンション名称・戸数未確認のまま特定不可で確定',
}

for code, note in codes.items():
    safe_note = note.replace("'", "''")
    update_query = f"""
    UPDATE `dj-ga4.scd.research_results`
    SET biko = '{safe_note}'
    WHERE purojiekutokoodo = '{code}'
    """
    job = bq.execute_query(update_query)
    logger.info(f"✓ {code}: biko更新 (affected: {job.num_dml_affected_rows})")

# 確認
logger.info(f"\n=== 確認 ===")
codes_str = ",".join(f"'{c}'" for c in codes.keys())
verify_query = f"""
SELECT purojiekutokoodo, bukkenmei, chousa_bukkenmei, biko
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo IN ({codes_str})
"""
results = bq.fetch_results(verify_query)
for row in results:
    logger.info(f"{row.purojiekutokoodo}: {row.bukkenmei}")
    logger.info(f"  chousa_bukkenmei: {row.chousa_bukkenmei}")
    logger.info(f"  biko: {row.biko}")

logger.info("\n" + "=" * 70)
logger.info("✅ chousa_bukkenmei 作業 完全終了")
logger.info("=" * 70)
