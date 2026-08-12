"""project_info の住所から郵便番号を取得"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("郵便番号補完 - project_info の住所情報を活用")
logger.info("=" * 70)

# 補完前の状態確認
before_query = """
SELECT
    COUNT(*) as total,
    COUNTIF(yubinkodo1 IS NOT NULL AND yubinkodo1 != '') as filled
FROM `dj-ga4.scd.research_results`
"""

before = bq.fetch_results(before_query)[0]
logger.info(f"\n=== 補完前 ===")
logger.info(f"総件数: {before.total}件")
logger.info(f"郵便番号入力済み: {before.filled}件")

# project_info の住所情報から郵便番号を検索
# 戦略：project_info に都道府県・市区町村の住所情報がある
#      → zipcode_master で照合して郵便番号を取得
#      → research_results に UPDATE

complement_query = """
UPDATE `dj-ga4.scd.research_results` r
SET
    r.yubinkodo1 = CAST(z.int64_field_0 AS STRING),
    r.yubinkodo2 = CAST(z.int64_field_1 AS STRING)
FROM `dj-ga4.scd.project_info` p
INNER JOIN `dj-ga4.scd.zipcode_master` z
    ON p.todoufukenmei_kanji = z.string_field_6
    AND p.shikuchousonmei_kanji = z.string_field_7
WHERE r.purojiekutokoodo = p.purojiekutokoodo
    AND (r.yubinkodo1 IS NULL OR r.yubinkodo1 = '')
    AND p.todoufukenmei_kanji IS NOT NULL
    AND p.shikuchousonmei_kanji IS NOT NULL
"""

logger.info(f"\n=== 郵便番号を検索・補完中 ===")
try:
    bq.execute_query(complement_query)
    logger.info(f"✓ 補完クエリ実行完了")
except Exception as e:
    logger.error(f"✗ エラー: {e}")

# 補完後の状態確認
logger.info(f"\n=== 補完後 ===")
after = bq.fetch_results(before_query)[0]
logger.info(f"総件数: {after.total}件")
logger.info(f"郵便番号入力済み: {after.filled}件（増加分: +{after.filled - before.filled}件）")

if after.total > 0:
    rate = after.filled / after.total * 100
    logger.info(f"補完率: {rate:.1f}%")

# サンプル確認
logger.info(f"\n=== サンプルデータ確認 ===")
sample_query = """
SELECT
    purojiekutokoodo,
    bukkenmei,
    yubinkodo1,
    yubinkodo2
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
logger.info("✅ 郵便番号補完完了")
logger.info("=" * 70)
