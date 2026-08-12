"""現在のテーブル状態を確認"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

print("=" * 70)
print("🌙 甘雨より：現在のテーブル状態を確認いたします")
print("=" * 70)

# テーブル統計
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

# 郵便番号の形式をチェック
print(f"\n【郵便番号フォーマット確認】")

format_query = """
SELECT
    COUNT(*) as total,
    COUNTIF(LENGTH(yubinkodo1) = 3 AND LENGTH(yubinkodo2) = 4) as correct_format,
    COUNTIF(LENGTH(yubinkodo1) != 3 OR LENGTH(yubinkodo2) != 4) as incorrect_format
FROM `dj-ga4.scd.research_results`
WHERE yubinkodo1 IS NOT NULL AND yubinkodo1 != ''
"""

fmt_result = bq.fetch_results(format_query)[0]
print(f"正常な形式（3-4）: {fmt_result.correct_format}件")
print(f"不正な形式: {fmt_result.incorrect_format}件")

# 判定
print(f"\n【判定】")
if result.total == 259:
    print(f"✅ 元の 259件に復元されました！")
elif result.total == 230:
    print(f"⚠️  230件です（元は 259件、現在は 230件のユニークコード）")
    print(f"   → ユニークなプロジェクトコードのみが保持されている状態")
else:
    print(f"⚠️  {result.total}件です")

print("\n" + "=" * 70)
