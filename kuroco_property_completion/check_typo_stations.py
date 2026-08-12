"""誤字疑いの駅名3件の元データを確認"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

stations = ['朝雺', '本八幕', '鷒池']
stations_str = ",".join(f"'{s}'" for s in stations)

query = f"""
SELECT purojiekutokoodo, bukkenmei, ekimei, ensenmei, source_url, biko, chousa_bukkenmei
FROM `dj-ga4.scd.research_results`
WHERE ekimei IN ({stations_str})
ORDER BY ekimei
"""
results = bq.fetch_results(query)

print(f"=== 誤字疑い駅名の該当レコード（{len(results)}件） ===\n")
for row in results:
    print(f"コード: {row.purojiekutokoodo}")
    print(f"bukkenmei: {row.bukkenmei}")
    print(f"chousa_bukkenmei: {row.chousa_bukkenmei}")
    print(f"ekimei: {row.ekimei!r}")
    print(f"ensenmei: {row.ensenmei}")
    print(f"source_url: {row.source_url}")
    print(f"biko: {row.biko}")
    print()
