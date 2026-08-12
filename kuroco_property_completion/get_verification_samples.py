"""日本郵便での外部検証用に、ランダムサンプルを抽出"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

query = """
SELECT
    r.purojiekutokoodo,
    r.bukkenmei,
    r.yubinkodo1,
    r.yubinkodo2,
    p.todoufukenmei_kanji,
    p.shikuchousonmei_kanji
FROM `dj-ga4.scd.research_results` r
LEFT JOIN `dj-ga4.scd.project_info` p
    ON r.purojiekutokoodo = p.purojiekutokoodo
WHERE r.yubinkodo1 IS NOT NULL AND r.yubinkodo1 != ''
ORDER BY RAND()
LIMIT 5
"""

results = bq.fetch_results(query)

print("=== 日本郵便公式サイトでの外部検証サンプル ===\n")
for row in results:
    print(f"物件: {row.bukkenmei}")
    print(f"郵便番号: {row.yubinkodo1}-{row.yubinkodo2}")
    print(f"登録住所: {row.todoufukenmei_kanji}{row.shikuchousonmei_kanji}")
    print()
