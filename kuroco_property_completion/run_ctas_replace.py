"""CREATE OR REPLACE TABLE で research_results を置き換え"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("CREATE OR REPLACE TABLE で research_results を置き換え")
logger.info("=" * 70)

# 置き換え前の状態確認
before_query = """
SELECT
    COUNT(*) as total,
    COUNTIF(yubinkodo1 IS NOT NULL AND yubinkodo1 != '') as filled
FROM `dj-ga4.scd.research_results`
"""

before = bq.fetch_results(before_query)[0]
logger.info(f"\n=== 置き換え前 ===")
logger.info(f"総件数: {before.total}件")
logger.info(f"郵便番号入力済み: {before.filled}件")

# CREATE OR REPLACE TABLE で新しいテーブルを作成
# LEFT JOIN で project_info と zipcode_master から郵便番号を補完
ctas_query = """
CREATE OR REPLACE TABLE `dj-ga4.scd.research_results` AS
SELECT
    r.purojiekutokoodo,
    r.purojiekutoedaban,
    r.bukkenmei,
    r.soukosuujuukyo,
    r.chijoukaisuu,
    r.ensenmei,
    r.ekimei,
    r.toho_fun,
    r.tochinokenrikubun,
    r.kakunin_status,
    r.source_url,
    r.biko,
    r.chousa_bukkenmei,
    COALESCE(r.yubinkodo1, CAST(z.int64_field_0 AS STRING)) as yubinkodo1,
    COALESCE(r.yubinkodo2, CAST(z.int64_field_1 AS STRING)) as yubinkodo2
FROM `dj-ga4.scd.research_results` r
LEFT JOIN `dj-ga4.scd.project_info` p
    ON r.purojiekutokoodo = p.purojiekutokoodo
LEFT JOIN `dj-ga4.scd.zipcode_master` z
    ON p.todoufukenmei_kanji = z.string_field_6
    AND p.shikuchousonmei_kanji = z.string_field_7
"""

logger.info(f"\n=== テーブル置き換え中 ===")
try:
    bq.execute_query(ctas_query)
    logger.info(f"✓ CREATE OR REPLACE TABLE 完了")
except Exception as e:
    logger.error(f"✗ エラー: {e}")

# 置き換え後の状態確認
logger.info(f"\n=== 置き換え後 ===")
after = bq.fetch_results(before_query)[0]
logger.info(f"総件数: {after.total}件")
logger.info(f"郵便番号入力済み: {after.filled}件（増加分: +{after.filled - before.filled}件）")

if after.total > 0:
    rate = after.filled / after.total * 100
    logger.info(f"補完率: {rate:.1f}%")

logger.info("\n" + "=" * 70)
logger.info("✅ テーブル置き換え完了")
logger.info("=" * 70)
