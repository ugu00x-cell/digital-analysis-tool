"""project_info.purojiekutomei（プロジェクト名）で C分類33件を照合"""

import csv
from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

# CSVから対象コードを読み込み
codes = []
with open('candidates_C_needs_review.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        codes.append(row['purojiekutokoodo'])

# 確定済み13件（13件確定でchousa_bukkenmei空欄のまま）は除外
confirmed_blank = {
    '34210011', '35110035', '38101000', '41102900', '41103600',
    '41103900', '41108100', '42107400', '42107800', '42108800',
    '43100900', '43101900', '43102000',
}
target_codes = [c for c in codes if c not in confirmed_blank]

print(f"CSV内コード数: {len(codes)}件")
print(f"確定済み(空欄でOK)除外後: {len(target_codes)}件\n")

codes_str = ",".join(f"'{c}'" for c in target_codes)
query = f"""
SELECT
    r.purojiekutokoodo,
    r.bukkenmei as research_bukkenmei,
    p.purojiekutomei,
    p.bukkenmei as project_bukkenmei,
    p.purojiekutoryakushou,
    p.bukkenryakushou
FROM `dj-ga4.scd.research_results` r
LEFT JOIN `dj-ga4.scd.project_info` p
    ON r.purojiekutokoodo = p.purojiekutokoodo
WHERE r.purojiekutokoodo IN ({codes_str})
ORDER BY r.purojiekutokoodo
"""
results = bq.fetch_results(query)

print("=== project_info との照合結果 ===\n")
resolved = []
still_unresolved = []

for row in results:
    # purojiekutomei が bukkenmei と異なり、かつ意味のある値であれば有力候補
    candidate = row.purojiekutomei
    if candidate and candidate.strip() and candidate != row.research_bukkenmei:
        resolved.append({
            'code': row.purojiekutokoodo,
            'research_bukkenmei': row.research_bukkenmei,
            'candidate': candidate,
        })
        print(f"✓ {row.purojiekutokoodo}: {row.research_bukkenmei} → 【{candidate}】")
    else:
        still_unresolved.append({
            'code': row.purojiekutokoodo,
            'bukkenmei': row.research_bukkenmei,
        })

print(f"\n=== サマリー ===")
print(f"project_info から解決: {len(resolved)}件")
print(f"まだ未解決: {len(still_unresolved)}件\n")

print("=== まだ未解決の一覧 ===")
for r in still_unresolved:
    print(f"{r['code']}: {r['bukkenmei']}")

# 未解決分をCSV出力
with open('candidates_D_still_unresolved.csv', 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['purojiekutokoodo', 'bukkenmei'])
    for r in still_unresolved:
        writer.writerow([r['code'], r['bukkenmei']])
