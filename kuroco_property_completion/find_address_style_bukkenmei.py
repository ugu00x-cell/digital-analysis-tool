"""bukkenmei が住所形式（実物件名ではない）候補を全件スキャンでリストアップ"""

import re
from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

query = """
SELECT purojiekutokoodo, bukkenmei, chousa_bukkenmei, biko, source_url
FROM `dj-ga4.scd.research_results`
ORDER BY purojiekutokoodo
"""
results = bq.fetch_results(query)

print(f"総件数: {len(results)}件\n")

# === 住所形式らしさを判定するパターン ===
# 1. 市区町村＋丁目・番地で終わる（例：「港区白金１丁目」「茅ヶ崎市茅ヶ崎２丁目」）
# 2. 都道府県名から始まる、または市区町村名を含み、丁目・番地・住所表現で終わる
# 3. カタカナのブランド接頭辞（ブリリア、シャリエ、パークホームズ等）が付いていない

# 丁目・番地・地番などの住所末尾パターン
address_suffix_pattern = re.compile(
    r'(\d+[-－]?\d*丁目|\d+丁目|[０-９0-9]+[-－][０-９0-9]+|番地|地番|\d+$)'
)

# 市区町村を含むパターン
city_pattern = re.compile(
    r'(市|区|町|村)'
)

# 既知のマンション/ブランド接頭辞（これがあれば実物件名の可能性が高い）
brand_keywords = [
    'ブリリア', 'シャリエ', 'パークホームズ', 'プラウド', 'ザ・パークハウス',
    'グランド', 'オーベル', 'ルネ', 'ガーラ', 'ジオ', 'クレアホームズ',
    'サンクレイドル', 'ライオンズ', 'コンフォート', 'ローレル', 'ヴェレーナ',
    'アルファステイツ', 'ウエリス', 'グローイングスクエア', 'グレーシア',
    'GS', 'ＧＳ', 'BG', 'ＢＧ', 'センチュリー', 'ハイム', 'コート',
    'レジデンス', 'マンション', 'ガーデン', 'テラス', 'スクエア', 'タワー',
    'ヒルズ', 'パーク', 'ステイツ', 'フォルム', 'エステート',
]

candidates = []

for row in results:
    name = row.bukkenmei or ""

    # ブランド名が含まれていれば実物件名の可能性が高いのでスキップ
    has_brand = any(kw in name for kw in brand_keywords)

    # 住所形式らしさをチェック
    has_address_suffix = bool(address_suffix_pattern.search(name))
    has_city = bool(city_pattern.search(name))

    if not has_brand and (has_address_suffix or has_city):
        candidates.append({
            'code': row.purojiekutokoodo,
            'name': name,
            'chousa': row.chousa_bukkenmei,
            'biko': row.biko,
            'has_biko': bool(row.biko),
        })

print(f"=== 住所形式らしき bukkenmei 候補: {len(candidates)}件 ===\n")

# chousa_bukkenmei が既に入っているものは除外して表示
unfilled = [c for c in candidates if not c['chousa']]
filled = [c for c in candidates if c['chousa']]

print(f"うち chousa_bukkenmei 未入力: {len(unfilled)}件")
print(f"うち chousa_bukkenmei 入力済み: {len(filled)}件\n")

print("=== 未入力の候補一覧 ===")
for c in unfilled:
    biko_mark = "📝biko有り" if c['has_biko'] else ""
    print(f"{c['code']} | {c['name']} {biko_mark}")
    if c['biko']:
        print(f"    biko: {c['biko'][:80]}")
