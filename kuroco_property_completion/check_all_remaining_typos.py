"""残り全ての未マッチ駅名について、bukkenmeiとの整合性・実在性をチェック"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

query = """
SELECT purojiekutokoodo, bukkenmei, chousa_bukkenmei, ekimei, ensenmei, source_url
FROM `dj-ga4.scd.research_results`
WHERE ekimei IS NOT NULL AND ekimei != ''
    AND (ekikoodo IS NULL OR ekikoodo = '')
ORDER BY ekimei
"""
results = bq.fetch_results(query)

print(f"=== 未マッチ駅名 全{len(results)}件の詳細 ===\n")
for row in results:
    display_name = row.chousa_bukkenmei or row.bukkenmei
    print(f"{row.purojiekutokoodo} | 駅:{row.ekimei!r} 沿線:{row.ensenmei}")
    print(f"  物件名: {display_name}")
    print()
