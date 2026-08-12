"""mansion-review.jpドメインで未取得のレコード一覧（竹中さん手動確認用）"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

query = """
SELECT purojiekutokoodo, purojiekutoedaban, bukkenmei, chousa_bukkenmei, source_url, biko
FROM `dj-ga4.scd.research_results`
WHERE (soukosuujuukyo IS NULL OR soukosuujuukyo = '')
    AND source_url LIKE '%mansion-review.jp%'
ORDER BY purojiekutokoodo
"""
results = bq.fetch_results(query)

print(f"=== マンションレビュー 未取得レコード一覧（{len(results)}件） ===\n")
for i, row in enumerate(results, 1):
    name = row.chousa_bukkenmei or row.bukkenmei
    print(f"{i}. {row.purojiekutokoodo}(枝番{row.purojiekutoedaban}): {name}")
    print(f"   URL: {row.source_url}")
    if row.biko:
        print(f"   備考: {row.biko}")
    print()
