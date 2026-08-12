"""沿線コード補完率が低い原因を調査"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

# project_infoの沿線マスタの件数確認
master_query = """
SELECT COUNT(DISTINCT ensenmei) as cnt
FROM `dj-ga4.scd.project_info`
WHERE ensenmei IS NOT NULL AND ensenmei != '' AND ensenkoodo IS NOT NULL AND ensenkoodo != ''
"""
master = bq.fetch_results(master_query)[0]
print(f"project_info 沿線マスタ: {master.cnt}種類\n")

# research_results で未マッチの沿線名を確認
unmatched_query = """
SELECT DISTINCT ensenmei
FROM `dj-ga4.scd.research_results`
WHERE ensenmei IS NOT NULL AND ensenmei != ''
    AND (ensenkoodo IS NULL OR ensenkoodo = '')
ORDER BY ensenmei
"""
unmatched = bq.fetch_results(unmatched_query)
print(f"=== 未マッチの沿線名（{len(unmatched)}件） ===\n")
for row in unmatched:
    print(f"  {row.ensenmei!r}")
