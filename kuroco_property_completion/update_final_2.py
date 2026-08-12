"""ブラウザ調査で判明した2件(39107900, 39108000)を転記"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

updates = {
    '39107900': 'グランドオーク別府 碧のテラス',
    '39108000': 'グランドオーク別府 碧のテラス',
}

for code, name in updates.items():
    safe_name = name.replace("'", "''")
    update_query = f"""
    UPDATE `dj-ga4.scd.research_results`
    SET chousa_bukkenmei = '{safe_name}'
    WHERE purojiekutokoodo = '{code}'
    """
    job = bq.execute_query(update_query)
    logger.info(f"✓ {code}: {name} (affected: {job.num_dml_affected_rows})")

# 最終進捗
progress_query = """
SELECT
    COUNT(*) as total,
    COUNTIF(chousa_bukkenmei IS NOT NULL AND chousa_bukkenmei != '') as filled
FROM `dj-ga4.scd.research_results`
"""
p = bq.fetch_results(progress_query)[0]
logger.info(f"\n=== chousa_bukkenmei 最終進捗 ===")
logger.info(f"総件数: {p.total}件")
logger.info(f"入力済み: {p.filled}件（{p.filled / p.total * 100:.1f}%）")
