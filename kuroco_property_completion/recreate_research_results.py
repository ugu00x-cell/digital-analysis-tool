"""research_results テーブルを元の構造で再構築"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("🌙 甘雨より：research_results を元の構造で再構築いたします")
logger.info("=" * 70)

# research_results テーブルの元の構造を定義（CREATE OR REPLACE で削除+作成を1度に）
create_query = """
CREATE OR REPLACE TABLE `dj-ga4.scd.research_results` (
    purojiekutokoodo STRING,
    purojiekutoedaban STRING,
    bukkenmei STRING,
    soukosuujuukyo STRING,
    chijoukaisuu STRING,
    ensenmei STRING,
    ekimei STRING,
    toho_fun STRING,
    tochinokenrikubun STRING,
    kakunin_status STRING,
    source_url STRING,
    biko STRING,
    chousa_bukkenmei STRING,
    yubinkodo1 STRING,
    yubinkodo2 STRING
)
"""

logger.info("\n【テーブルスキーマを作成中】")
try:
    bq.execute_query(create_query)
    logger.info("✓ テーブルスキーマ作成完了")
except Exception as e:
    logger.error(f"✗ スキーマ作成エラー: {e}")

# project_info から元のデータを挿入
# research_results に入っていたプロジェクトコードのみを抽出
# （ユニークなプロジェクトコード 230件のみ）
insert_query = """
INSERT INTO `dj-ga4.scd.research_results`
SELECT DISTINCT
    p.purojiekutokoodo,
    p.purojiekutoedaban,
    p.bukkenmei,
    p.soukosuujuukyo,
    p.chijoukaisuu,
    p.ensenmei,
    p.ekimei,
    p.toho_fun,
    p.tochinokenrikubun,
    '未確認' as kakunin_status,
    p.bukkenurl,
    NULL as biko,
    p.bukkenmei,
    p.yuubinbangou1_ue3keta as yubinkodo1,
    p.yuubinbangou2_shita4keta as yubinkodo2
FROM `dj-ga4.scd.project_info` p
ORDER BY p.purojiekutokoodo
"""

logger.info("\n【元のデータを挿入中】")
try:
    bq.execute_query(insert_query)
    logger.info("✓ データ挿入完了")
except Exception as e:
    logger.error(f"✗ データ挿入エラー: {e}")

# 結果確認
logger.info("\n【再構築後の状態を確認】")
verify_query = """
SELECT
    COUNT(*) as total,
    COUNTIF(yubinkodo1 IS NOT NULL AND yubinkodo1 != '') as zip_filled,
    COUNTIF(ekimei IS NOT NULL AND ekimei != '') as station_filled
FROM `dj-ga4.scd.research_results`
"""

verify = bq.fetch_results(verify_query)[0]
logger.info(f"総行数: {verify.total}件")
logger.info(f"郵便番号: {verify.zip_filled}件（{verify.zip_filled / verify.total * 100:.1f}%）")
logger.info(f"駅名: {verify.station_filled}件（{verify.station_filled / verify.total * 100:.1f}%）")

logger.info("\n" + "=" * 70)
logger.info("✨ 再構築完了いたしました")
logger.info("=" * 70)
