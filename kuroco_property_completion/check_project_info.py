"""project_info テーブルの構造確認スクリプト"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

# project_info の全カラム名を取得
table = bq.client.get_table('dj-ga4.scd.project_info')
print("=== project_info columns ===")
for f in table.schema:
    print(f"{f.name} ({f.field_type})")

print("\n=== Sample row (matching a research_results project code) ===")
query = """
SELECT *
FROM `dj-ga4.scd.project_info`
WHERE purojiekutokoodo = '36210004'
LIMIT 1
"""
results = bq.fetch_results(query)
if results:
    row = results[0]
    for key in row.keys():
        print(f"{key}: {row[key]}")
else:
    print("No matching row found")
