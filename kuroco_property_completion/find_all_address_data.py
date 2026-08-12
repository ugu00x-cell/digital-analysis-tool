"""research_results で住所を含むレコードを全件探す"""

import re
from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

# 都道府県名パターン
pref_pattern = re.compile(
    r'(北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|'
    r'新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|'
    r'奈良県|和歌山県|鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|佐賀県|長崎県|'
    r'熊本県|大分県|宮崎県|鹿児島県|沖縄県)'
)

print("=" * 80)
print("research_results で住所情報を含むカラムを探す")
print("=" * 80)

# すべてのレコードをスキャン
query = "SELECT * FROM `dj-ga4.scd.research_results`"
results = bq.fetch_results(query)

# 各カラムに住所情報が含まれているレコード数をカウント
field_with_address = {}

for row in results:
    for key in row.keys():
        value = row[key]

        if value is None or value == '':
            continue

        # 都道府県名を含むか確認
        if pref_pattern.search(str(value)):
            if key not in field_with_address:
                field_with_address[key] = []
            field_with_address[key].append({
                'code': row['purojiekutokoodo'],
                'value': str(value)[:100]
            })

print(f"\n【住所情報を含むカラム】\n")

for field, records in sorted(field_with_address.items(), key=lambda x: len(x[1]), reverse=True):
    print(f"{field}: {len(records)}件")
    for rec in records[:3]:
        print(f"  - {rec['code']}: {rec['value']}")
    if len(records) > 3:
        print(f"  ... ほか {len(records) - 3}件")
    print()
