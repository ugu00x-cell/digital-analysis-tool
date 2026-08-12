"""research_results と project_info の JOIN を確認"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

# research_results のプロジェクトコード
query1 = """
SELECT DISTINCT purojiekutokoodo
FROM `dj-ga4.scd.research_results`
LIMIT 5
"""

results1 = bq.fetch_results(query1)
print("=== research_results のプロジェクトコード ===")
codes = []
for row in results1:
    print(f"  {row.purojiekutokoodo}")
    codes.append(row.purojiekutokoodo)

# project_info に存在するか確認
print(f"\n=== project_info との照合 ===")
for code in codes:
    query2 = f"""
    SELECT
        purojiekutokoodo,
        ekimei,
        ensenmei,
        soukosuujuukyo
    FROM `dj-ga4.scd.project_info`
    WHERE purojiekutokoodo = '{code}'
    """

    results2 = bq.fetch_results(query2)
    if results2:
        row = results2[0]
        print(f"\n{code}: 見つかった ✓")
        print(f"  駅名: {row.ekimei}")
        print(f"  沿線: {row.ensenmei}")
        print(f"  総戸数: {row.soukosuujuukyo}")
    else:
        print(f"\n{code}: 見つからない ✗")
