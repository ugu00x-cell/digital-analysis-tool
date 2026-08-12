"""34210011・35110035の重複行を詳しく調査"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

codes = ['34210011', '35110035']
codes_str = ",".join(f"'{c}'" for c in codes)

query = f"""
SELECT *
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo IN ({codes_str})
ORDER BY purojiekutokoodo
"""
results = bq.fetch_results(query)

print(f"=== 重複行の詳細（{len(results)}行） ===\n")
for i, row in enumerate(results, 1):
    print(f"--- 行{i} ---")
    for key in row.keys():
        print(f"  {key}: {row[key]!r}")
    print()

# 全カラムが完全一致しているか確認
print("=== 完全一致チェック ===")
import hashlib
hashes = {}
for row in results:
    row_dict = {k: row[k] for k in row.keys()}
    h = hashlib.md5(str(sorted(row_dict.items())).encode()).hexdigest()
    hashes.setdefault(row.purojiekutokoodo, []).append(h)

for code, hs in hashes.items():
    unique_hs = set(hs)
    print(f"{code}: {len(hs)}行 → ユニークな内容: {len(unique_hs)}種類")
