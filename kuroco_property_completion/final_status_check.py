"""最終的なテーブル状態を確認"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

print("\n" + "=" * 70)
print("📊 research_results テーブル 最終状態レポート")
print("=" * 70)

# テーブル状態
query = """
SELECT
    COUNT(*) as total,
    COUNT(DISTINCT purojiekutokoodo) as unique_codes,
    COUNTIF(yubinkodo1 IS NOT NULL AND yubinkodo1 != '') as zip_filled,
    COUNTIF(ekimei IS NOT NULL AND ekimei != '') as station_filled,
    COUNTIF(ensenmei IS NOT NULL AND ensenmei != '') as line_filled,
    COUNTIF(tochinokenrikubun IS NOT NULL AND tochinokenrikubun != '') as rights_filled,
    COUNTIF(soukosuujuukyo IS NOT NULL AND soukosuujuukyo != '') as units_filled
FROM `dj-ga4.scd.research_results`
"""

result = bq.fetch_results(query)[0]

print(f"\n【テーブル構成】")
print(f"総行数: {result.total}件")
print(f"ユニークなプロジェクトコード: {result.unique_codes}件")

print(f"\n【補完状況】")
print(f"郵便番号: {result.zip_filled}件（{result.zip_filled / result.total * 100:.1f}%）")
print(f"駅名: {result.station_filled}件（{result.station_filled / result.total * 100:.1f}%）")
print(f"沿線: {result.line_filled}件（{result.line_filled / result.total * 100:.1f}%）")
print(f"土地権利区分: {result.rights_filled}件（{result.rights_filled / result.total * 100:.1f}%）")
print(f"総戸数: {result.units_filled}件（{result.units_filled / result.total * 100:.1f}%）")

# 判定
if result.unique_codes == 259:
    print(f"\n✅ ユニークなプロジェクトコードが 259件 → 元の状態と一致")
elif result.total == 259:
    print(f"\n✅ 総行数が 259件 → 元の状態と一致")
else:
    print(f"\n⚠️  元の状態（259件）と異なります")
    print(f"   → 復元が別のバージョンか、重複が発生している可能性")

print("\n" + "=" * 70)
