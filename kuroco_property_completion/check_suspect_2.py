"""要注意2件（41110400, 43105300）の現在の内容を確認"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

codes = ['41110400', '43105300']
query = f"""
SELECT purojiekutokoodo, bukkenmei, chousa_bukkenmei, biko, source_url
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo IN ({",".join(f"'{c}'" for c in codes)})
"""
results = bq.fetch_results(query)

print("=== 要注意2件の現在の内容 ===\n")
for row in results:
    print(f"コード: {row.purojiekutokoodo}")
    print(f"bukkenmei: {row.bukkenmei}")
    print(f"chousa_bukkenmei: {row.chousa_bukkenmei}")
    print(f"biko: {row.biko}")
    print(f"source_url: {row.source_url}")
    print()
