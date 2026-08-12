"""駅コード未マッチの残りを分析（現在の最新状態で）"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

query = """
SELECT DISTINCT r.ekimei
FROM `dj-ga4.scd.research_results` r
WHERE r.ekimei IS NOT NULL AND r.ekimei != ''
    AND (r.ekikoodo IS NULL OR r.ekikoodo = '')
ORDER BY r.ekimei
"""
results = bq.fetch_results(query)
print(f"未マッチ駅名: {len(results)}件\n")
for row in results:
    print(f"  {row.ekimei!r}")
