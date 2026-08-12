"""chousa_bukkenmei 最終進捗確認"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

query = """
SELECT
    COUNT(*) as total,
    COUNTIF(chousa_bukkenmei IS NOT NULL AND chousa_bukkenmei != '') as filled
FROM `dj-ga4.scd.research_results`
"""
p = bq.fetch_results(query)[0]
print(f"総件数: {p.total}件")
print(f"chousa_bukkenmei 入力済み: {p.filled}件（{p.filled / p.total * 100:.1f}%）")

# 残りの未入力（かつ確定13件でもない）を確認
confirmed_blank = [
    '34210011', '35110035', '38101000', '41102900', '41103600',
    '41103900', '41108100', '42107400', '42107800', '42108800',
    '43100900', '43101900', '43102000',
]
codes_str = ",".join(f"'{c}'" for c in confirmed_blank)

remaining_query = f"""
SELECT purojiekutokoodo, bukkenmei, biko
FROM `dj-ga4.scd.research_results`
WHERE (chousa_bukkenmei IS NULL OR chousa_bukkenmei = '')
  AND purojiekutokoodo NOT IN ({codes_str})
  AND (
    REGEXP_CONTAINS(bukkenmei, r'(市|区|町|村)')
  )
ORDER BY purojiekutokoodo
"""
remaining = bq.fetch_results(remaining_query)
print(f"\n=== まだ chousa_bukkenmei 未入力（住所形式候補） ===")
print(f"件数: {len(remaining)}件\n")
for row in remaining:
    print(f"{row.purojiekutokoodo}: {row.bukkenmei}")
    if row.biko:
        print(f"  biko: {row.biko}")
