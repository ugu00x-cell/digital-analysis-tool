"""bukkenmeiがproject_info側の原本と完全一致しているか再検証（本日の事故による改変がないか確認）"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

query = """
SELECT
    r.purojiekutokoodo,
    r.purojiekutoedaban,
    r.bukkenmei as r_bukkenmei,
    p.bukkenmei as p_bukkenmei
FROM `dj-ga4.scd.research_results` r
LEFT JOIN `dj-ga4.scd.project_info` p
    ON r.purojiekutokoodo = p.purojiekutokoodo
    AND r.purojiekutoedaban = p.purojiekutoedaban
"""
results = bq.fetch_results(query)

mismatches = []
no_match_in_project_info = []
for row in results:
    if row.p_bukkenmei is None:
        no_match_in_project_info.append(row)
    elif row.r_bukkenmei != row.p_bukkenmei:
        mismatches.append(row)

print(f"総件数: {len(results)}件")
print(f"完全一致: {len(results) - len(mismatches) - len(no_match_in_project_info)}件")
print(f"不一致: {len(mismatches)}件")
print(f"project_info側に対応行なし: {len(no_match_in_project_info)}件\n")

if mismatches:
    print("=== 不一致の詳細 ===")
    for row in mismatches:
        print(f"{row.purojiekutokoodo}(枝番{row.purojiekutoedaban}):")
        print(f"  research_results: {row.r_bukkenmei!r}")
        print(f"  project_info:      {row.p_bukkenmei!r}")

if no_match_in_project_info:
    print("\n=== project_info側に対応行がないレコード（枝番不一致の可能性） ===")
    for row in no_match_in_project_info[:20]:
        print(f"{row.purojiekutokoodo}(枝番{row.purojiekutoedaban}): {row.r_bukkenmei}")
