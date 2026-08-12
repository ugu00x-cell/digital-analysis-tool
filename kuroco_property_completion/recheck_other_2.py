"""ウエリス豊中桃山台・鎌ヶ谷市新鎌ヶ谷も同様に既存データを確認"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

codes = ['31210013', '39100400']
codes_str = ",".join(f"'{c}'" for c in codes)

query = f"""
SELECT purojiekutokoodo, purojiekutoedaban, bukkenmei, soukosuujuukyo, chijoukaisuu, source_url, biko
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo IN ({codes_str})
ORDER BY purojiekutokoodo, purojiekutoedaban
"""
results = bq.fetch_results(query)
for row in results:
    print(f"コード: {row.purojiekutokoodo}(枝番{row.purojiekutoedaban}): {row.bukkenmei}")
    print(f"  総戸数: {row.soukosuujuukyo} / 階建: {row.chijoukaisuu}")
    print(f"  biko: {row.biko}")
    print()
