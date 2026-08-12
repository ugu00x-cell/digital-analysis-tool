"""土地権利が未確認のまま要フォローの3件の現状を確認"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

codes = ['38101000', '38102600', '38104200']
codes_str = ",".join(f"'{c}'" for c in codes)

query = f"""
SELECT purojiekutokoodo, bukkenmei, chousa_bukkenmei, tochinokenrikubun, kakunin_status, source_url, biko
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo IN ({codes_str})
"""
results = bq.fetch_results(query)

print(f"=== 土地権利未確認3件の現状（{len(results)}件） ===\n")
for row in results:
    print(f"コード: {row.purojiekutokoodo}")
    print(f"bukkenmei: {row.bukkenmei}")
    print(f"chousa_bukkenmei: {row.chousa_bukkenmei}")
    print(f"tochinokenrikubun: {row.tochinokenrikubun}")
    print(f"kakunin_status: {row.kakunin_status}")
    print(f"source_url: {row.source_url}")
    print(f"biko: {row.biko}")
    print()
