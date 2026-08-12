"""INSERT OVERWRITE を使った郵便番号補完"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("郵便番号補完 - INSERT OVERWRITE 方式")
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

# INSERT OVERWRITE で新しいテーブルデータを作成
# research_results のすべてのカラムを取得し、project_info から郵便番号を補完
overwrite_query = """
INSERT OVERWRITE TABLE `dj-ga4.scd.research_results`
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
    COALESCE(r.yubinkodo1, p.yuubinbangou1_ue3keta) as yubinkodo1,
    COALESCE(r.yubinkodo2, p.yuubinbangou2_shita4keta) as yubinkodo2
FROM `dj-ga4.scd.research_results` r
LEFT JOIN `dj-ga4.scd.project_info` p
    ON r.purojiekutokoodo = p.purojiekutokoodo
"""

logger.info(f"\n=== INSERT OVERWRITE を実行中 ===")
try:
    bq.execute_query(overwrite_query)
    logger.info(f"✓ INSERT OVERWRITE 完了")
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

logger.info("\n" + "=" * 70)
logger.info("✅ 郵便番号補完完了")
logger.info("=" * 70)
