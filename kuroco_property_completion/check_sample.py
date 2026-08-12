"""research_results のサンプルデータ確認スクリプト"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

# source_url が入っているレコードを1件取得
query = """
SELECT purojiekutokoodo, bukkenmei, source_url, chousa_bukkenmei, biko
FROM `dj-ga4.scd.research_results`
WHERE source_url IS NOT NULL AND source_url != ''
LIMIT 3
"""

results = bq.fetch_results(query)

if results:
    for i, row in enumerate(results, 1):
        print(f"\n--- Record {i} ---")
        print(f"purojiekutokoodo: {row.purojiekutokoodo}")
        print(f"bukkenmei: {row.bukkenmei}")
        print(f"source_url: {row.source_url}")
        print(f"chousa_bukkenmei: {row.chousa_bukkenmei}")
        print(f"biko: {row.biko}")
else:
    print("No data found with source_url")
