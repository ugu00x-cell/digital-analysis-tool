"""別窓の報告と現在のテーブル状態を突き合わせるための確認スクリプト"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("現状確認：research_results の最新状態")
logger.info("=" * 70)

# 1. 総件数と基本補完状況
query = """
SELECT
    COUNT(*) as total,
    COUNTIF(chousa_bukkenmei IS NOT NULL AND chousa_bukkenmei != '') as chousa_filled,
    COUNTIF(yubinkodo1 IS NOT NULL AND yubinkodo1 != '') as zip_filled,
    COUNTIF(ekimei IS NOT NULL AND ekimei != '') as station_filled,
    COUNTIF(ensenmei IS NOT NULL AND ensenmei != '') as line_filled,
    COUNTIF(biko IS NOT NULL AND biko != '') as biko_filled
FROM `dj-ga4.scd.research_results`
"""
r = bq.fetch_results(query)[0]
logger.info(f"\n総件数: {r.total}件")
logger.info(f"chousa_bukkenmei 入力済み: {r.chousa_filled}件")
logger.info(f"郵便番号入力済み: {r.zip_filled}件")
logger.info(f"駅名入力済み: {r.station_filled}件")
logger.info(f"沿線名入力済み: {r.line_filled}件")
logger.info(f"biko入力済み: {r.biko_filled}件")

# 2. 別窓が言及した「特定不可13件」のコードが今どうなっているか確認
codes_13 = ['34210011', '35110035', '38101000', '41102900', '41103600',
            '41103900', '41108100', '42107400', '42107800', '42108800',
            '43100900', '43101900', '43102000']

logger.info(f"\n=== 別窓報告の「特定不可13件」の現在の状態 ===")
codes_str = "', '".join(codes_13)
check_query = f"""
SELECT purojiekutokoodo, bukkenmei, chousa_bukkenmei, biko
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo IN ('{codes_str}')
"""
found = bq.fetch_results(check_query)
logger.info(f"該当レコード: {len(found)}件（期待値13件）")
for row in found:
    logger.info(f"  {row.purojiekutokoodo}: chousa_bukkenmei={row.chousa_bukkenmei!r} biko={row.biko!r}")

# 3. 駅名の重複・表記ゆれ状況（project_infoとの照合率）
logger.info(f"\n=== 駅コード照合率の確認 ===")
match_query = """
SELECT
    COUNT(DISTINCT r.purojiekutokoodo) as total_with_station,
    COUNT(DISTINCT CASE WHEN p.ekikoodo IS NOT NULL AND p.ekikoodo != '' THEN r.purojiekutokoodo END) as matched
FROM `dj-ga4.scd.research_results` r
LEFT JOIN `dj-ga4.scd.project_info` p
    ON r.purojiekutokoodo = p.purojiekutokoodo AND r.ekimei = p.ekimei
WHERE r.ekimei IS NOT NULL AND r.ekimei != ''
"""
m = bq.fetch_results(match_query)[0]
logger.info(f"駅名が入っている件数: {m.total_with_station}件")
logger.info(f"project_infoの駅コードとマッチ: {m.matched}件")

logger.info("\n" + "=" * 70)
