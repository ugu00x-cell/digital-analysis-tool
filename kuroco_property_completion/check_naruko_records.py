"""37210007（エムズシティ鳴子プレディア）関連の全レコードを確認"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

query = """
SELECT purojiekutokoodo, purojiekutoedaban, bukkenmei, chousa_bukkenmei,
       soukosuujuukyo, chijoukaisuu, tochinokenrikubun, biko
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo = '37210007'
ORDER BY purojiekutoedaban
"""
results = bq.fetch_results(query)
for row in results:
    name = row.chousa_bukkenmei or row.bukkenmei
    print(f"枝番{row.purojiekutoedaban}: {name}")
    print(f"  総戸数: {row.soukosuujuukyo} / 階建: {row.chijoukaisuu} / 権利: {row.tochinokenrikubun}")
    print(f"  biko: {row.biko}")
    print()
