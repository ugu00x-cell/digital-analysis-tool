"""全ユニークな郵便番号リストを取得（外部検証用）"""

from services.bigquery_handler import BigQueryHandler
import json

bq = BigQueryHandler('dj-ga4', 'scd')

query = """
SELECT DISTINCT
    r.yubinkodo1,
    r.yubinkodo2,
    p.todoufukenmei_kanji,
    p.shikuchousonmei_kanji
FROM `dj-ga4.scd.research_results` r
LEFT JOIN `dj-ga4.scd.project_info` p
    ON r.purojiekutokoodo = p.purojiekutokoodo
WHERE r.yubinkodo1 IS NOT NULL AND r.yubinkodo1 != ''
ORDER BY r.yubinkodo1, r.yubinkodo2
"""

results = bq.fetch_results(query)
print(f"ユニークな郵便番号: {len(results)}件\n")

data = []
for row in results:
    data.append({
        'zip': f"{row.yubinkodo1}{row.yubinkodo2}",
        'zip_display': f"{row.yubinkodo1}-{row.yubinkodo2}",
        'pref': row.todoufukenmei_kanji or "",
        'city': row.shikuchousonmei_kanji or "",
    })

# JSON形式で保存
with open('all_zipcodes.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("all_zipcodes.json に保存しました")
for d in data[:5]:
    print(d)
