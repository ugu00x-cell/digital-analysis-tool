"""biko空欄化前(18:27JST以前)の元の内容をタイムトラベルで確認"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

codes = ['34210011', '35110035']
codes_str = ",".join(f"'{c}'" for c in codes)

# mark_unresolvable_13.py 実行(18:27頃)より前の状態を確認
query = f"""
SELECT purojiekutokoodo, purojiekutoedaban, bukkenmei, chousa_bukkenmei, biko
FROM `dj-ga4.scd.research_results`
FOR SYSTEM_TIME AS OF TIMESTAMP('2026-08-11 18:26:00+09:00')
WHERE purojiekutokoodo IN ({codes_str})
ORDER BY purojiekutokoodo, purojiekutoedaban
"""
results = bq.fetch_results(query)

print("=== 18:26 JST時点(biko空欄化前)の内容 ===\n")
for row in results:
    print(f"{row.purojiekutokoodo} (枝番{row.purojiekutoedaban}): {row.bukkenmei}")
    print(f"  chousa_bukkenmei: {row.chousa_bukkenmei}")
    print(f"  biko: {row.biko}")
    print()
