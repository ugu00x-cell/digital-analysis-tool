"""38102600のbikoにファクトチェック結果を反映"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

update_query = """
UPDATE `dj-ga4.scd.research_results`
SET biko = 'mansion-review.jpの掲載終了アーカイブより「杉並区久我山5丁目 売地 全3区画」の土地権利=所有権を確認。'
    'ただしこれはproject_info上の物件名「グローイングスクエア久我山」としてブランド化される前の、売地段階の情報。'
    '土地権利(所有権)は宅地分譲の標準形態のため採用、駅・区画数の詳細は同一物件との確証がないため反映せず'
WHERE purojiekutokoodo = '38102600'
"""
job = bq.execute_query(update_query)
logger.info(f"✓ 38102600: biko更新完了 (affected: {job.num_dml_affected_rows})")

# 確認
verify = bq.fetch_results("""
SELECT purojiekutokoodo, bukkenmei, tochinokenrikubun, ekimei, biko
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo = '38102600'
""")
for row in verify:
    logger.info(f"{row.bukkenmei}: 権利={row.tochinokenrikubun} 駅={row.ekimei}")
    logger.info(f"biko: {row.biko}")
