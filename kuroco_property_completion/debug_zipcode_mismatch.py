"""研究結果と project_info の郵便番号の乖離を確認"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

# research_results の未入力レコードを取得
query1 = """
SELECT DISTINCT purojiekutokoodo
FROM `dj-ga4.scd.research_results`
WHERE yubinkodo1 IS NULL OR yubinkodo1 = ''
LIMIT 10
"""

results1 = bq.fetch_results(query1)
print("=== research_results の郵便番号未入力レコード ===\n")

missing_codes = []
for row in results1:
    code = row.purojiekutokoodo
    missing_codes.append(code)
    print(f"{code}")

# これらのコードが project_info に存在するか、そして郵便番号があるか確認
print(f"\n=== project_info での確認 ===\n")

for code in missing_codes:
    query2 = f"""
    SELECT
        purojiekutokoodo,
        bukkenmei,
        yuubinbangou1_ue3keta,
        yuubinbangou2_shita4keta
    FROM `dj-ga4.scd.project_info`
    WHERE purojiekutokoodo = '{code}'
    """

    results2 = bq.fetch_results(query2)
    if results2:
        row = results2[0]
        print(f"{code}: 存在 ✓")
        print(f"  物件名: {row.bukkenmei}")
        print(f"  郵便番号: {row.yuubinbangou1_ue3keta}-{row.yuubinbangou2_shita4keta}")
    else:
        print(f"{code}: 存在しない ✗")

# 統計
print(f"\n=== 統計 ===")
query_stats = """
SELECT
    (SELECT COUNT(*) FROM `dj-ga4.scd.research_results` WHERE yubinkodo1 IS NULL OR yubinkodo1 = '') as research_empty,
    (SELECT COUNT(DISTINCT purojiekutokoodo) FROM `dj-ga4.scd.project_info` WHERE yuubinbangou1_ue3keta IS NOT NULL AND yuubinbangou1_ue3keta != '') as project_has_zip
"""

stats = bq.fetch_results(query_stats)[0]
print(f"research_results 郵便番号未入力: {stats.research_empty}件")
print(f"project_info 郵便番号あり: {stats.project_has_zip}件")
