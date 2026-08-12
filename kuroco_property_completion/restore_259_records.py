"""甘雨が元の 259件に戻すお手伝い"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("🌙 甘雨より：research_results を元の 259件に戻させていただきます")
logger.info("=" * 70)

# 現在の状態確認
before = bq.fetch_results('SELECT COUNT(*) as cnt, COUNT(DISTINCT purojiekutokoodo) as codes FROM `dj-ga4.scd.research_results`')[0]
logger.info(f"\n【現在の状態】")
logger.info(f"総行数: {before.cnt}件")
logger.info(f"ユニークコード: {before.codes}件")

# ユニークなプロジェクトコードで削減
# つまり、同じプロジェクトコードが複数行ある場合は 1行だけ残す
restore_query = """
CREATE OR REPLACE TABLE `dj-ga4.scd.research_results` AS
SELECT *
FROM (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY purojiekutokoodo ORDER BY purojiekutokoodo) as rn
    FROM `dj-ga4.scd.research_results`
)
WHERE rn = 1
"""

logger.info(f"\n【復元処理を実行中】")
logger.info(f"重複を削除して、ユニークなプロジェクトコードのみを保持します...")

try:
    bq.execute_query(restore_query)
    logger.info(f"✓ 復元処理完了")
except Exception as e:
    logger.error(f"✗ エラーが発生してしまいました: {e}")

# 復元後の状態確認
logger.info(f"\n【復元後の状態】")
after = bq.fetch_results('SELECT COUNT(*) as cnt FROM `dj-ga4.scd.research_results`')[0]
logger.info(f"総行数: {after.cnt}件")

if after.cnt == 259:
    logger.info(f"\n✨ 無事に元の 259件に戻りました！")

    # 補完状況も確認
    status = bq.fetch_results("""
    SELECT
        COUNTIF(yubinkodo1 IS NOT NULL AND yubinkodo1 != '') as zip_filled,
        COUNTIF(ekimei IS NOT NULL AND ekimei != '') as station_filled,
        COUNTIF(ensenmei IS NOT NULL AND ensenmei != '') as line_filled,
        COUNTIF(tochinokenrikubun IS NOT NULL AND tochinokenrikubun != '') as rights_filled
    FROM `dj-ga4.scd.research_results`
    """)[0]

    logger.info(f"\n【補完状況】")
    logger.info(f"郵便番号: {status.zip_filled}件（{status.zip_filled / 259 * 100:.1f}%）")
    logger.info(f"駅名: {status.station_filled}件（{status.station_filled / 259 * 100:.1f}%）")
    logger.info(f"沿線: {status.line_filled}件（{status.line_filled / 259 * 100:.1f}%）")
    logger.info(f"権利区分: {status.rights_filled}件（{status.rights_filled / 259 * 100:.1f}%）")

else:
    logger.info(f"\n⚠️  {after.cnt}件になってしまいました...")

logger.info("\n" + "=" * 70)
logger.info("🌙 甘雨より：お疲れ様でした。良い夜をお過ごしくださいね")
logger.info("=" * 70)
