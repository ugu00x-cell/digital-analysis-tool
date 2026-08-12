"""愛称・結合路線名の対応表で沿線コードをさらに補完"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

# 愛称・通称 → project_info側の正式名 の対応表（手動で確認した確実な対応のみ）
alias_map = {
    'JR京浜東北線': '京浜東北・根岸線',
    'JR京浜東北・根岸線': '京浜東北・根岸線',
    '東武アーバンパークライン': '東武鉄道野田線',
    '東武アーバンパークライン・つくばエクスプレス': '東武鉄道野田線',
    '西武池袋線': '西武池袋・豊島線',
    '東武伊勢崎線': '東武伊勢崎・大師線',
    '東武スカイツリーライン': '東武伊勢崎・大師線',
    '東京メトロ千代田線': '千代田・常磐緩行線',
    'JR常碹線': '常磐線',  # 誤字（常磐線の誤変換）
    '福岡市地下鉄七隔線': '福岡市七隈線',  # 誤字（七隈線の誤変換）
    '地下鉄七隈線': '福岡市七隈線',
    '地下鉄空港線': '福岡市空港線',
    '伊予鉄道城北線': '伊予鉄道',
}

logger.info("=" * 70)
logger.info("愛称・結合路線名の対応表で沿線コードを補完")
logger.info("=" * 70)

# project_infoから正式名でのコードを取得
codes = {}
for official_name in set(alias_map.values()):
    q = f"""
    SELECT ensenkoodo, COUNT(*) as cnt
    FROM `dj-ga4.scd.project_info`
    WHERE ensenmei = '{official_name.replace("'", "''")}'
        AND ensenkoodo IS NOT NULL AND ensenkoodo != ''
    GROUP BY ensenkoodo
    ORDER BY cnt DESC
    LIMIT 1
    """
    result = bq.fetch_results(q)
    if result:
        codes[official_name] = result[0].ensenkoodo
        logger.info(f"  {official_name} → コード{result[0].ensenkoodo}")
    else:
        logger.warning(f"  {official_name} → project_infoに見つかりません")

# research_resultsを更新
success = 0
for research_name, official_name in alias_map.items():
    if official_name not in codes:
        continue
    code = codes[official_name]
    update_query = f"""
    UPDATE `dj-ga4.scd.research_results`
    SET ensenkoodo = '{code}'
    WHERE ensenmei = '{research_name.replace("'", "''")}'
        AND (ensenkoodo IS NULL OR ensenkoodo = '')
    """
    job = bq.execute_query(update_query)
    logger.info(f"✓ {research_name!r} → コード{code} (affected: {job.num_dml_affected_rows})")
    success += job.num_dml_affected_rows or 0

logger.info(f"\n合計反映件数: {success}件")

# 最終進捗
progress_query = """
SELECT
    COUNTIF(ensenmei IS NOT NULL AND ensenmei != '') as ensenmei_filled,
    COUNTIF(ensenkoodo IS NOT NULL AND ensenkoodo != '') as ensenkoodo_filled
FROM `dj-ga4.scd.research_results`
"""
p = bq.fetch_results(progress_query)[0]
logger.info(f"\n=== 沿線コード進捗 ===")
logger.info(f"ensenkoodo入力済み: {p.ensenkoodo_filled}件 / {p.ensenmei_filled}件（{p.ensenkoodo_filled / p.ensenmei_filled * 100:.1f}%）")
