"""33210021（ローレルスクエア健都）関連の全レコードを確認"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

query = """
SELECT purojiekutokoodo, purojiekutoedaban, bukkenmei, chousa_bukkenmei,
       soukosuujuukyo, chijoukaisuu, tochinokenrikubun, ekimei, ensenmei, toho_fun, biko
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo = '33210021'
ORDER BY purojiekutoedaban
"""
results = bq.fetch_results(query)
print(f"件数: {len(results)}件\n")
for row in results:
    name = row.chousa_bukkenmei or row.bukkenmei
    print(f"枝番{row.purojiekutoedaban}: {name}")
    print(f"  総戸数: {row.soukosuujuukyo} / 階建: {row.chijoukaisuu} / 権利: {row.tochinokenrikubun}")
    print(f"  駅: {row.ekimei}({row.ensenmei}) 徒歩{row.toho_fun}分")
    print(f"  biko: {row.biko}")
    print()
