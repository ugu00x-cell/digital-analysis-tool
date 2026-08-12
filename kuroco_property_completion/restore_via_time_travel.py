"""タイムトラベル機能で元の259件を正確に復元"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("🌙 甘雨より：タイムトラベルで元の259件を正確に復元いたします")
logger.info("=" * 70)

# 14:44:00 JST 時点（郵便番号117件補完済み・259件で完全一致確認済み）を復元
restore_query = """
CREATE OR REPLACE TABLE `dj-ga4.scd.research_results` AS
SELECT *
FROM `dj-ga4.scd.research_results`
FOR SYSTEM_TIME AS OF TIMESTAMP('2026-08-11 14:44:00+09:00')
"""

logger.info("\n【14:44:00 JST 時点のデータで復元中】")
try:
    bq.execute_query(restore_query)
    logger.info("✓ 復元完了")
except Exception as e:
    logger.error(f"✗ エラー: {e}")

# 復元後の確認
logger.info("\n【復元後の状態を確認】")
verify_query = """
SELECT
    COUNT(*) as total,
    COUNTIF(yubinkodo1 IS NOT NULL AND yubinkodo1 != '') as zip_filled,
    COUNTIF(ekimei IS NOT NULL AND ekimei != '') as station_filled,
    COUNTIF(ensenmei IS NOT NULL AND ensenmei != '') as line_filled,
    COUNTIF(tochinokenrikubun IS NOT NULL AND tochinokenrikubun != '') as rights_filled,
    COUNTIF(soukosuujuukyo IS NOT NULL AND soukosuujuukyo != '') as units_filled
FROM `dj-ga4.scd.research_results`
"""

result = bq.fetch_results(verify_query)[0]
logger.info(f"総行数: {result.total}件")

if result.total == 259:
    logger.info("\n✨ 元の259件に正確に復元されました！\n")
    logger.info(f"郵便番号: {result.zip_filled}件（{result.zip_filled / 259 * 100:.1f}%）")
    logger.info(f"駅名: {result.station_filled}件（{result.station_filled / 259 * 100:.1f}%）")
    logger.info(f"沿線: {result.line_filled}件（{result.line_filled / 259 * 100:.1f}%）")
    logger.info(f"土地権利区分: {result.rights_filled}件（{result.rights_filled / 259 * 100:.1f}%）")
    logger.info(f"総戸数: {result.units_filled}件（{result.units_filled / 259 * 100:.1f}%）")
else:
    logger.warning(f"\n⚠️ {result.total}件です。期待値の259件と異なります")

# 郵便番号のフォーマットも確認
logger.info("\n【郵便番号フォーマット確認】")
fmt_query = """
SELECT
    COUNTIF(LENGTH(yubinkodo1) = 3 AND LENGTH(yubinkodo2) = 4) as correct_format,
    COUNTIF(yubinkodo1 IS NOT NULL AND yubinkodo1 != '' AND NOT(LENGTH(yubinkodo1) = 3 AND LENGTH(yubinkodo2) = 4)) as incorrect_format
FROM `dj-ga4.scd.research_results`
"""
fmt = bq.fetch_results(fmt_query)[0]
logger.info(f"正常な形式: {fmt.correct_format}件")
logger.info(f"不正な形式: {fmt.incorrect_format}件")

# biko の調査メモが残っているか確認
logger.info("\n【調査メモ（biko）の保全確認】")
biko_query = """
SELECT COUNT(*) as cnt
FROM `dj-ga4.scd.research_results`
WHERE biko IS NOT NULL AND biko != ''
"""
biko_result = bq.fetch_results(biko_query)[0]
logger.info(f"biko（調査メモ）が入っているレコード: {biko_result.cnt}件")

logger.info("\n" + "=" * 70)
logger.info("🌙 甘雨より：復元処理が完了いたしました")
logger.info("=" * 70)
