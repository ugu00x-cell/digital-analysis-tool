"""つくばグランヴィラのレコード詳細を確認（棟別内訳の可能性を調べる）"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

query = """
SELECT purojiekutokoodo, purojiekutoedaban, bukkenmei, soukosuujuukyo, chijoukaisuu,
       ekimei, ensenmei, toho_fun, tochinokenrikubun, source_url, biko
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo = '39100600'
"""
results = bq.fetch_results(query)
for row in results:
    print(f"コード: {row.purojiekutokoodo}(枝番{row.purojiekutoedaban})")
    print(f"bukkenmei: {row.bukkenmei}")
    print(f"総戸数(現在値): {row.soukosuujuukyo}")
    print(f"階建: {row.chijoukaisuu}")
    print(f"駅: {row.ekimei} / 沿線: {row.ensenmei} / 徒歩: {row.toho_fun}分")
    print(f"土地権利: {row.tochinokenrikubun}")
    print(f"source_url: {row.source_url}")
    print(f"biko: {row.biko}")
    print()

# project_infoの原本も確認
print("=== project_info側の原本 ===\n")
query2 = """
SELECT purojiekutokoodo, purojiekutoedaban, bukkenmei, soukosuujuukyo, chijoukaisuu, tochinokenrikubun
FROM `dj-ga4.scd.project_info`
WHERE purojiekutokoodo = '39100600'
"""
results2 = bq.fetch_results(query2)
for row in results2:
    print(f"コード: {row.purojiekutokoodo}(枝番{row.purojiekutoedaban}): {row.bukkenmei}")
    print(f"  総戸数: {row.soukosuujuukyo} / 階建: {row.chijoukaisuu} / 土地権利: {row.tochinokenrikubun}")
