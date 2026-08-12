"""project_info全体から駅名→駅コードの対応表を作り、research_resultsと照合"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

# project_info全体から、駅名ごとに駅コードのユニークな対応を確認
print("=== project_info全体の駅名マスタ確認 ===\n")

master_query = """
SELECT
    ekimei,
    ekikoodo,
    COUNT(*) as cnt
FROM `dj-ga4.scd.project_info`
WHERE ekimei IS NOT NULL AND ekimei != ''
    AND ekikoodo IS NOT NULL AND ekikoodo != ''
GROUP BY ekimei, ekikoodo
ORDER BY ekimei
"""
master_results = bq.fetch_results(master_query)
print(f"駅名マスタのユニークな組み合わせ: {len(master_results)}件")

# 同じ駅名で複数の駅コードがある（表記は同じでも路線違いで複数コードありうる）ケースを確認
station_names = {}
for row in master_results:
    station_names.setdefault(row.ekimei, []).append(row.ekikoodo)

multi_code_stations = {k: v for k, v in station_names.items() if len(v) > 1}
print(f"同名で複数の駅コードを持つ駅名: {len(multi_code_stations)}件")
for name, codes in list(multi_code_stations.items())[:10]:
    print(f"  {name}: {codes}")

# research_results の駅名を、このマスタ（グローバル）と照合
print(f"\n=== research_results をグローバル駅名マスタと照合 ===\n")
compare_query = """
SELECT DISTINCT
    r.purojiekutokoodo,
    r.ekimei
FROM `dj-ga4.scd.research_results` r
WHERE r.ekimei IS NOT NULL AND r.ekimei != ''
"""
compare_results = bq.fetch_results(compare_query)

matched = 0
unmatched_names = set()
for row in compare_results:
    if row.ekimei in station_names:
        matched += 1
    else:
        unmatched_names.add(row.ekimei)

print(f"総件数: {len(compare_results)}件")
print(f"グローバルマスタとマッチ: {matched}件")
print(f"未マッチ: {len(compare_results) - matched}件")
print(f"\n未マッチのユニーク駅名: {len(unmatched_names)}種類")
for name in sorted(unmatched_names):
    print(f"  {name!r}")
