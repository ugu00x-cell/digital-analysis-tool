"""テーブル復元状態を確認"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

print("=" * 70)
print("✅ テーブル復元状態を確認中")
print("=" * 70)

# テーブル状態を確認
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

print(f"\n【テーブル状態】")
print(f"総行数: {result.total}件")

if result.total == 259:
    print(f"\n🎉 元の状態に復元されました！\n")

    print(f"郵便番号: {result.zip_filled}件（{result.zip_filled / result.total * 100:.1f}%）")
    print(f"駅名: {result.station_filled}件（{result.station_filled / result.total * 100:.1f}%）")
    print(f"沿線: {result.line_filled}件（{result.line_filled / result.total * 100:.1f}%）")
    print(f"土地権利区分: {result.rights_filled}件（{result.rights_filled / result.total * 100:.1f}%）")
    print(f"総戸数: {result.units_filled}件（{result.units_filled / result.total * 100:.1f}%）")

    avg_rate = (result.zip_filled + result.station_filled + result.line_filled + result.rights_filled + result.units_filled) / (5 * result.total) * 100
    print(f"\n【全体補完率】{avg_rate:.1f}%")

else:
    print(f"\n⚠️  テーブルがまだ {result.total}件です（元は 259件）")

print("\n" + "=" * 70)
