"""project_info側の沿線マスタの表記形式を確認"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

query = """
SELECT DISTINCT ensenmei
FROM `dj-ga4.scd.project_info`
WHERE ensenmei IS NOT NULL AND ensenmei != '' AND ensenkoodo IS NOT NULL AND ensenkoodo != ''
ORDER BY ensenmei
"""
results = bq.fetch_results(query)
print(f"project_info 沿線マスタ一覧（{len(results)}件）:\n")
for row in results:
    print(f"  {row.ensenmei!r}")
