"""グランドオーク大分駅前リブレの判明情報を反映"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

update_query = """
UPDATE `dj-ga4.scd.research_results`
SET
    soukosuujuukyo = '101',
    chijoukaisuu = '14',
    ekimei = '大分',
    ensenmei = 'JR日豊本線',
    toho_fun = '2',
    tochinokenrikubun = '区分所有権',
    kakunin_status = '確認済',
    biko = '九電不動産公式サイト(go-oitaekimae.jp)で詳細確認。事業協力者住戸2戸含む'
WHERE purojiekutokoodo = '41109000'
"""
job = bq.execute_query(update_query)
logger.info(f"✓ 41109000(グランドオーク大分駅前リブレ): 反映完了 (affected: {job.num_dml_affected_rows})")

# 確認
verify = bq.fetch_results("""
SELECT purojiekutokoodo, bukkenmei, soukosuujuukyo, chijoukaisuu, ekimei, ensenmei, toho_fun, tochinokenrikubun
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo = '41109000'
""")
for row in verify:
    logger.info(f"{row.bukkenmei}: 総戸数{row.soukosuujuukyo} 階建{row.chijoukaisuu} 駅{row.ekimei}({row.ensenmei})徒歩{row.toho_fun}分 権利{row.tochinokenrikubun}")
