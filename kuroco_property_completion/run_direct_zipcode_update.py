"""郵便番号の直接 UPDATE - シンプル版"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("郵便番号補完 - 直接 UPDATE（シンプル版）")
logger.info("=" * 70)

# 補完前の状態確認
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

# シンプルな UPDATE クエリ
# 未入力のレコードに対して、project_info から郵便番号を取得
update_queries = [
    # 郵便番号1を更新
    """
    UPDATE `dj-ga4.scd.research_results` r
    SET r.yubinkodo1 = p.yuubinbangou1_ue3keta
    FROM `dj-ga4.scd.project_info` p
    WHERE r.purojiekutokoodo = p.purojiekutokoodo
        AND (r.yubinkodo1 IS NULL OR r.yubinkodo1 = '')
        AND p.yuubinbangou1_ue3keta IS NOT NULL
        AND p.yuubinbangou1_ue3keta != ''
    """,
    # 郵便番号2を更新
    """
    UPDATE `dj-ga4.scd.research_results` r
    SET r.yubinkodo2 = p.yuubinbangou2_shita4keta
    FROM `dj-ga4.scd.project_info` p
    WHERE r.purojiekutokoodo = p.purojiekutokoodo
        AND p.yuubinbangou2_shita4keta IS NOT NULL
        AND p.yuubinbangou2_shita4keta != ''
    """,
]

logger.info(f"\n=== 郵便番号を更新中 ===")
for i, query in enumerate(update_queries, 1):
    try:
        bq.execute_query(query)
        logger.info(f"✓ 更新クエリ {i} 完了")
    except Exception as e:
        logger.error(f"✗ エラー {i}: {e}")

# 補完後の状態確認
logger.info(f"\n=== 補完後 ===")
after = bq.fetch_results(before_query)[0]
logger.info(f"総件数: {after.total}件")
logger.info(f"郵便番号入力済み: {after.filled}件（増加分: +{after.filled - before.filled}件）")
logger.info(f"郵便番号未入力: {after.empty}件")

if after.total > 0:
    rate = after.filled / after.total * 100
    logger.info(f"補完率: {rate:.1f}%")

# 補完されたデータの詳細確認
logger.info(f"\n=== 補完されたデータの確認 ===")
# 郵便番号が入っているものを確認
verify_query = """
SELECT
    COUNT(*) as total_with_zip,
    COUNT(DISTINCT yubinkodo1) as unique_zips
FROM `dj-ga4.scd.research_results`
WHERE yubinkodo1 IS NOT NULL AND yubinkodo1 != ''
"""

verify = bq.fetch_results(verify_query)[0]
logger.info(f"郵便番号が入っているレコード: {verify.total_with_zip}件")
logger.info(f"ユニークな郵便番号: {verify.unique_zips}個")

logger.info("\n" + "=" * 70)
logger.info("✅ 郵便番号補完完了")
logger.info("=" * 70)
