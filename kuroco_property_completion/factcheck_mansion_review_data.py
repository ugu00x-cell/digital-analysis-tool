"""mansion-review.jp自動アクセス時点で取得した2件のデータを内部整合性チェック"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

codes = ['38101000', '38102600']
codes_str = ",".join(f"'{c}'" for c in codes)

query = f"""
SELECT r.purojiekutokoodo, r.bukkenmei, r.chousa_bukkenmei, r.soukosuujuukyo,
       r.chijoukaisuu, r.tochinokenrikubun, r.ekimei, r.ensenmei, r.toho_fun,
       r.yubinkodo1, r.yubinkodo2, r.source_url, r.biko,
       p.todoufukenmei_kanji, p.shikuchousonmei_kanji, p.purojiekutomei
FROM `dj-ga4.scd.research_results` r
LEFT JOIN `dj-ga4.scd.project_info` p
    ON r.purojiekutokoodo = p.purojiekutokoodo
WHERE r.purojiekutokoodo IN ({codes_str})
"""
results = bq.fetch_results(query)

print("=== 内部整合性チェック ===\n")
for row in results:
    print(f"コード: {row.purojiekutokoodo}")
    print(f"  research_results.bukkenmei: {row.bukkenmei}")
    print(f"  chousa_bukkenmei: {row.chousa_bukkenmei}")
    print(f"  project_info.purojiekutomei: {row.purojiekutomei}")
    print(f"  住所(project_info): {row.todoufukenmei_kanji}{row.shikuchousonmei_kanji}")
    print(f"  郵便番号: {row.yubinkodo1}-{row.yubinkodo2}")
    print(f"  総戸数: {row.soukosuujuukyo} / 階建: {row.chijoukaisuu}")
    print(f"  土地権利: {row.tochinokenrikubun}")
    print(f"  駅: {row.ekimei}({row.ensenmei}) 徒歩{row.toho_fun}分")
    print(f"  source_url: {row.source_url}")
    print(f"  biko: {row.biko}")
    print()
