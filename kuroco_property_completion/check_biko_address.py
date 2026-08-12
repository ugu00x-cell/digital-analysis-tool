"""biko欄に住所情報が含まれているか確認するスクリプト"""

import re
from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

# 全件のbiko欄を取得
query = """
SELECT purojiekutokoodo, bukkenmei, biko, yubinkodo1, yubinkodo2
FROM `dj-ga4.scd.research_results`
WHERE biko IS NOT NULL AND biko != ''
"""

results = bq.fetch_results(query)
print(f"Total records with biko: {len(results)}")

# 住所らしきパターンを検索（都道府県名、市区町村、丁目、番地など）
address_pattern = re.compile(
    r'(北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|'
    r'新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|'
    r'奈良県|和歌山県|鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|佐賀県|長崎県|'
    r'熊本県|大分県|宮崎県|鹿児島県|沖縄県)'
)

zip_pattern = re.compile(r'\d{3}-?\d{4}')

address_found = []
zip_found = []

for row in results:
    biko_text = row.biko or ""
    if address_pattern.search(biko_text):
        address_found.append((row.purojiekutokoodo, row.bukkenmei, biko_text))
    if zip_pattern.search(biko_text):
        zip_found.append((row.purojiekutokoodo, row.bukkenmei, biko_text))

print(f"\n=== biko内に都道府県名を含む件数: {len(address_found)} ===")
for code, name, biko in address_found[:10]:
    print(f"{code} | {name} | {biko}")

print(f"\n=== biko内に郵便番号らしき数字を含む件数: {len(zip_found)} ===")
for code, name, biko in zip_found[:10]:
    print(f"{code} | {name} | {biko}")

print(f"\n=== yubinkodo1が既に入力済みの件数を確認 ===")
query2 = """
SELECT COUNT(*) as cnt
FROM `dj-ga4.scd.research_results`
WHERE yubinkodo1 IS NOT NULL AND yubinkodo1 != ''
"""
results2 = bq.fetch_results(query2)
print(f"yubinkodo1 入力済み: {results2[0].cnt}件")
