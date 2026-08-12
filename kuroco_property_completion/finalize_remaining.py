"""40200600(bukkenmei自体が実名)を転記 + 最後の4件のsource_urlを確認"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

# 40200600 はbukkenmei自体が実物件名なのでそのまま転記
update_query = """
UPDATE `dj-ga4.scd.research_results`
SET chousa_bukkenmei = 'プレディア観音新町'
WHERE purojiekutokoodo = '40200600'
"""
job = bq.execute_query(update_query)
logger.info(f"✓ 40200600: プレディア観音新町 (affected: {job.num_dml_affected_rows})")

# 最後の4件のsource_urlを確認
logger.info("\n=== 最後の4件のsource_url確認 ===")
codes = ['39107900', '39108000', '40107100', '41100400']
codes_str = ",".join(f"'{c}'" for c in codes)
query = f"""
SELECT purojiekutokoodo, bukkenmei, source_url, biko
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo IN ({codes_str})
"""
results = bq.fetch_results(query)
for row in results:
    logger.info(f"\n{row.purojiekutokoodo}: {row.bukkenmei}")
    logger.info(f"  source_url: {row.source_url}")
    logger.info(f"  biko: {row.biko}")

# 全体進捗
progress_query = """
SELECT
    COUNT(*) as total,
    COUNTIF(chousa_bukkenmei IS NOT NULL AND chousa_bukkenmei != '') as filled
FROM `dj-ga4.scd.research_results`
"""
p = bq.fetch_results(progress_query)[0]
logger.info(f"\n=== chousa_bukkenmei 全体進捗 ===")
logger.info(f"総件数: {p.total}件")
logger.info(f"入力済み: {p.filled}件（{p.filled / p.total * 100:.1f}%）")
