"""住所形式bukkenmeiを分類し、biko内の物件名を自動抽出してCSV出力"""

import re
import csv
from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

query = """
SELECT purojiekutokoodo, bukkenmei, chousa_bukkenmei, biko, source_url
FROM `dj-ga4.scd.research_results`
ORDER BY purojiekutokoodo
"""
results = bq.fetch_results(query)

address_suffix_pattern = re.compile(r'(\d+[-－]?\d*丁目|\d+丁目|番地|地番)')
city_pattern = re.compile(r'(市|区|町|村)')

brand_keywords = [
    'ブリリア', 'シャリエ', 'パークホームズ', 'プラウド', 'ザ・パークハウス',
    'グランド', 'オーベル', 'ルネ', 'ガーラ', 'ジオ', 'クレアホームズ',
    'サンクレイドル', 'ライオンズ', 'コンフォート', 'ローレル', 'ヴェレーナ',
    'アルファステイツ', 'ウエリス', 'グローイングスクエア', 'グレーシア',
    'GS', 'ＧＳ', 'BG', 'ＢＧ', 'センチュリー', 'ハイム', 'コート',
    'レジデンス', 'マンション', 'ガーデン', 'テラス', 'スクエア', 'タワー',
    'ヒルズ', 'パーク', 'ステイツ', 'フォルム', 'エステート',
]

# biko から物件名らしき固有名詞を抽出するパターン
# 「〜と確定」「〜の一部」「棟別」などの前にある固有名詞、または文頭の固有名詞
name_extract_patterns = [
    re.compile(r'^([ぁ-んァ-ヶー一-龥A-Za-z・]{3,20}?)と確定'),
    re.compile(r'^([ぁ-んァ-ヶー一-龥A-Za-z・]{3,20}?)の一部'),
    re.compile(r'^([ぁ-んァ-ヶー一-龥A-Za-z・0-9]{3,25})(?:[。、]|$)'),
]

DETACHED_HOUSE_KEYWORDS = ['戸建て分譲', 'マンションではなく戸建て']
NO_INFO_KEYWORDS = ['最寄り駅なし', '未確認', '不明']


def extract_name_from_biko(biko: str) -> str:
    """biko欄から物件名らしき文字列を抽出（簡易ヒューリスティック）"""
    if not biko:
        return ""
    for pattern in name_extract_patterns:
        m = pattern.match(biko.strip())
        if m:
            candidate = m.group(1).strip()
            # 明らかに物件名でない語句を除外
            if any(kw in candidate for kw in DETACHED_HOUSE_KEYWORDS + NO_INFO_KEYWORDS):
                return ""
            if len(candidate) >= 3:
                return candidate
    return ""


rows_a = []  # biko から物件名抽出できた
rows_b = []  # 戸建て分譲（物件名なしでOK）
rows_c = []  # 判断材料不足（要手動確認）

for row in results:
    name = row.bukkenmei or ""
    has_brand = any(kw in name for kw in brand_keywords)
    has_address_suffix = bool(address_suffix_pattern.search(name))
    has_city = bool(city_pattern.search(name))

    if has_brand or not (has_address_suffix or has_city):
        continue
    if row.chousa_bukkenmei:  # 既に転記済みはスキップ
        continue

    biko = row.biko or ""

    if any(kw in biko for kw in DETACHED_HOUSE_KEYWORDS):
        rows_b.append({'code': row.purojiekutokoodo, 'bukkenmei': name, 'biko': biko})
        continue

    extracted = extract_name_from_biko(biko)
    if extracted:
        rows_a.append({
            'code': row.purojiekutokoodo,
            'bukkenmei': name,
            'extracted_name': extracted,
            'biko': biko,
        })
    else:
        rows_c.append({
            'code': row.purojiekutokoodo,
            'bukkenmei': name,
            'biko': biko,
            'source_url': row.source_url,
        })

print(f"=== 分類結果 ===")
print(f"A) biko から物件名を自動抽出できた: {len(rows_a)}件")
print(f"B) 戸建て分譲（物件名なしでOK）: {len(rows_b)}件")
print(f"C) 判断材料不足・要確認: {len(rows_c)}件")
print(f"合計: {len(rows_a) + len(rows_b) + len(rows_c)}件\n")

# CSV出力
with open('candidates_A_extracted.csv', 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['purojiekutokoodo', 'bukkenmei', 'extracted_name', 'biko'])
    for r in rows_a:
        writer.writerow([r['code'], r['bukkenmei'], r['extracted_name'], r['biko']])

with open('candidates_B_detached.csv', 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['purojiekutokoodo', 'bukkenmei', 'biko'])
    for r in rows_b:
        writer.writerow([r['code'], r['bukkenmei'], r['biko']])

with open('candidates_C_needs_review.csv', 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['purojiekutokoodo', 'bukkenmei', 'biko', 'source_url'])
    for r in rows_c:
        writer.writerow([r['code'], r['bukkenmei'], r['biko'], r['source_url']])

print("CSV出力完了:")
print("  candidates_A_extracted.csv")
print("  candidates_B_detached.csv")
print("  candidates_C_needs_review.csv")

print(f"\n=== A) 自動抽出できた物件名（要目視確認） ===")
for r in rows_a:
    print(f"{r['code']} | {r['bukkenmei']} → 【{r['extracted_name']}】")
    print(f"    biko全文: {r['biko']}")

print(f"\n=== C) 判断材料不足の一覧 ===")
for r in rows_c:
    print(f"{r['code']} | {r['bukkenmei']}")
    print(f"    biko: {r['biko']}")
