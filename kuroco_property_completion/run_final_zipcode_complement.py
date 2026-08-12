"""【8/12実行】郵便番号の残り 142 件を完全補完"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("【最終タスク】郵便番号補完 - 残り 142 件を完成")
logger.info("=" * 70)

# 現状確認
before_query = """
SELECT
    COUNT(*) as total,
    COUNTIF(yubinkodo1 IS NOT NULL AND yubinkodo1 != '') as filled,
    COUNTIF(yubinkodo1 IS NULL OR yubinkodo1 = '') as empty
FROM `dj-ga4.scd.research_results`
"""

before = bq.fetch_results(before_query)[0]
logger.info(f"\n=== 補完前 ===")
logger.info(f"総件数: {before.total}件")
logger.info(f"郵便番号入力済み: {before.filled}件")
logger.info(f"郵便番号未入力: {before.empty}件")

# project_info から郵便番号を取得して補完
# 未入力のレコードについて、project_info から郵便番号を取得
complement_query = """
UPDATE `dj-ga4.scd.research_results` r
SET
    r.yubinkodo1 = p.yuubinbangou1_ue3keta,
    r.yubinkodo2 = p.yuubinbangou2_shita4keta
WHERE r.purojiekutokoodo IN (
    SELECT DISTINCT r2.purojiekutokoodo
    FROM `dj-ga4.scd.research_results` r2
    WHERE (r2.yubinkodo1 IS NULL OR r2.yubinkodo1 = '')
)
AND r.purojiekutokoodo IN (
    SELECT purojiekutokoodo
    FROM `dj-ga4.scd.project_info`
    WHERE yuubinbangou1_ue3keta IS NOT NULL AND yuubinbangou1_ue3keta != ''
)
AND EXISTS (
    SELECT 1
    FROM `dj-ga4.scd.project_info` p
    WHERE p.purojiekutokoodo = r.purojiekutokoodo
        AND p.yuubinbangou1_ue3keta IS NOT NULL
        AND p.yuubinbangou1_ue3keta != ''
    LIMIT 1
)
"""

logger.info(f"\n=== 郵便番号補完を実行中 ===")
try:
    bq.execute_query(complement_query)
    logger.info("✓ 補完クエリ実行完了")
except Exception as e:
    logger.error(f"✗ エラー: {e}")

# 補完後の状態確認
logger.info(f"\n=== 補完後 ===")
after = bq.fetch_results(before_query)[0]
logger.info(f"総件数: {after.total}件")
logger.info(f"郵便番号入力済み: {after.filled}件（増加分: +{after.filled - before.filled}件）")
logger.info(f"郵便番号未入力: {after.empty}件")
logger.info(f"補完率: {after.filled / after.total * 100:.1f}%")

# 補完されたサンプルを確認
logger.info(f"\n=== サンプルデータ確認 ===")
sample_query = """
SELECT purojiekutokoodo, bukkenmei, yubinkodo1, yubinkodo2
FROM `dj-ga4.scd.research_results`
WHERE yubinkodo1 IS NOT NULL AND yubinkodo1 != ''
ORDER BY RAND()
LIMIT 5
"""

samples = bq.fetch_results(sample_query)
for row in samples:
    logger.info(f"{row.purojiekutokoodo}: {row.bukkenmei}")
    logger.info(f"  郵便番号: {row.yubinkodo1}-{row.yubinkodo2}")

logger.info("\n" + "=" * 70)
logger.info("✅ 郵便番号補完タスク完了")
logger.info("=" * 70)
