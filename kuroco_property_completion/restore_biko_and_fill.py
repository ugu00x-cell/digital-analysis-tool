"""失われたbikoを復元し、セントガーデン海老名Ⅱをchousa_bukkenmeiに転記"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("biko復元 + chousa_bukkenmei転記（枝番を指定して正確に処理）")
logger.info("=" * 70)

# 枝番も条件に含めて正確に1行だけを対象にする
updates = [
    {
        'code': '34210011',
        'edaban': '0.0',
        'biko': '既存値で埋まっていた項目は変更なし、土地権利のみ確認',
        'chousa': None,  # chousa_bukkenmeiは変更しない
    },
    {
        'code': '35110035',
        'edaban': '1.0',
        'biko': 'I街区と同一複合施設',
        'chousa': 'セントガーデン海老名Ⅱ',
    },
]

for u in updates:
    set_clauses = [f"biko = '{u['biko'].replace(chr(39), chr(39)+chr(39))}'"]
    if u['chousa']:
        set_clauses.append(f"chousa_bukkenmei = '{u['chousa'].replace(chr(39), chr(39)+chr(39))}'")
    set_sql = ", ".join(set_clauses)

    update_query = f"""
    UPDATE `dj-ga4.scd.research_results`
    SET {set_sql}
    WHERE purojiekutokoodo = '{u['code']}' AND purojiekutoedaban = '{u['edaban']}'
    """
    job = bq.execute_query(update_query)
    logger.info(f"✓ {u['code']}(枝番{u['edaban']}): biko復元{'+ chousa転記' if u['chousa'] else ''} (affected: {job.num_dml_affected_rows})")

# 確認
logger.info(f"\n=== 確認 ===")
codes_str = ",".join(f"'{u['code']}'" for u in updates)
verify_query = f"""
SELECT purojiekutokoodo, purojiekutoedaban, bukkenmei, chousa_bukkenmei, biko
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo IN ({codes_str})
ORDER BY purojiekutokoodo, purojiekutoedaban
"""
results = bq.fetch_results(verify_query)
for row in results:
    logger.info(f"{row.purojiekutokoodo}(枝番{row.purojiekutoedaban}): {row.bukkenmei}")
    logger.info(f"  chousa_bukkenmei: {row.chousa_bukkenmei}")
    logger.info(f"  biko: {row.biko}")

logger.info("\n" + "=" * 70)
