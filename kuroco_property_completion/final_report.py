"""最終的な research_results の補完状況レポート"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

print("=" * 70)
print("research_results テーブル 補完状況最終レポート")
print("=" * 70)

query = """
SELECT
    COUNT(*) as total,
    COUNTIF(yubinkodo1 IS NOT NULL AND yubinkodo1 != '') as zip_filled,
    COUNTIF(ekimei IS NOT NULL AND ekimei != '') as station_filled,
    COUNTIF(ensenmei IS NOT NULL AND ensenmei != '') as line_filled,
    COUNTIF(tochinokenrikubun IS NOT NULL AND tochinokenrikubun != '') as rights_filled,
    COUNTIF(soukosuujuukyo IS NOT NULL AND soukosuujuukyo != '') as units_filled
FROM `dj-ga4.scd.research_results`
"""

result = bq.fetch_results(query)[0]

total = result.total
data = [
    ("郵便番号（yubinkodo1）", result.zip_filled),
    ("駅名（ekimei）", result.station_filled),
    ("沿線名（ensenmei）", result.line_filled),
    ("土地権利区分（tochinokenrikubun）", result.rights_filled),
    ("総戸数（soukosuujuukyo）", result.units_filled),
]

print(f"\n【総件数】{total}件\n")
print(f"{'項目':<30} {'入力済み':<10} {'補完率':<10}")
print("-" * 50)

for label, filled in data:
    rate = f"{filled / total * 100:.1f}%" if total > 0 else "0%"
    print(f"{label:<30} {filled:<10} {rate:<10}")

# 平均補完率
avg_rate = sum([d[1] for d in data]) / (len(data) * total) * 100
print("-" * 50)
print(f"{'【平均補完率】':<30} {'':<10} {avg_rate:.1f}%")

print("\n" + "=" * 70)
print("✅ 本日（8/11）の補完作業完了")
print("=" * 70)
