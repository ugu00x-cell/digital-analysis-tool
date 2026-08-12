"""本当にsoukosuujuukyoが空欄のレコードを、source_urlのドメイン別に集計"""

from urllib.parse import urlparse
from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

query = """
SELECT purojiekutokoodo, purojiekutoedaban, bukkenmei, source_url, biko
FROM `dj-ga4.scd.research_results`
WHERE (soukosuujuukyo IS NULL OR soukosuujuukyo = '')
    AND source_url IS NOT NULL AND source_url != ''
"""
results = bq.fetch_results(query)

print(f"=== 本当に総戸数が空欄のレコード: {len(results)}件 ===\n")

domain_counts = {}
for row in results:
    domain = urlparse(row.source_url).netloc
    domain_counts.setdefault(domain, []).append(row)

print("=== ドメイン別内訳 ===")
for domain, rows in sorted(domain_counts.items(), key=lambda x: -len(x[1])):
    print(f"{domain}: {len(rows)}件")

print("\n=== mansion-review.jp 以外のサンプル（検証対象候補） ===\n")
for domain, rows in domain_counts.items():
    if "mansion-review" not in domain:
        for row in rows[:3]:
            print(f"{row.purojiekutokoodo}(枝番{row.purojiekutoedaban}): {row.bukkenmei}")
            print(f"  URL: {row.source_url}")
            print(f"  biko: {row.biko}")
            print()
