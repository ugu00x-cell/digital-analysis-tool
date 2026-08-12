"""mansion-review.jp以外の未取得URLを全件リストアップ"""

from urllib.parse import urlparse
from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

query = """
SELECT purojiekutokoodo, purojiekutoedaban, bukkenmei, source_url, biko
FROM `dj-ga4.scd.research_results`
WHERE (soukosuujuukyo IS NULL OR soukosuujuukyo = '')
    AND source_url IS NOT NULL AND source_url != ''
    AND source_url NOT LIKE '%mansion-review.jp%'
ORDER BY source_url
"""
results = bq.fetch_results(query)

print(f"対象件数: {len(results)}件\n")
for row in results:
    print(f"{row.purojiekutokoodo}|{row.purojiekutoedaban}|{row.bukkenmei}|{row.source_url}")
