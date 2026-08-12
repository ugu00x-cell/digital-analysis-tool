"""project_info.purojiekutomei から解決した名前を chousa_bukkenmei に転記"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("project_info.purojiekutomei から解決した物件名を転記")
logger.info("=" * 70)

# コード単位でユニークな名前（重複JOINの結果を手動で整理）
updates = {
    '33110021': 'プレミスト湘南辻堂（藤沢羽鳥）',
    '34110034': 'メイツ・ザ・マークス新横浜',
    '34210012': 'ルネ西宮仁川',
    '35110049': 'リーフィアレジデンス橋本町田小山が丘',
    '35210012': 'ポレスター学研奈良登美ヶ丘',
    '35210019': 'エムズシティ新安城ブランシエラ',
    '36110025': 'アーバンパレス武蔵浦和（西浦和南区四谷）',
    '36110032': 'サンリヤン東戸塚',
    '36110039': 'ローレルスクエア湘南平塚（平塚市宮松町）',
    '36110045': 'パークホームズ千葉',
    '36110051': 'メイツ西白井（白井市清水口）',
    '36210004': 'ブランシエラ長浜元町',
    '36210027': 'ルネ鶴見横堤',
    '37110001': 'パークホームズ土浦',
    '37110012': 'ハイムスイート東松山',
    '37110027': 'パークホームズ昭島中神（昭島宮沢町）',
    '37110100': 'サンリヤン相模原',
    '37210009': 'プレディア名古屋城西',
    '38100200': 'ハイムスイート平岸ブランシエラ',
    '38107900': 'シエリア与野中央公園',
}

logger.info(f"\n対象コード数: {len(updates)}件")

success = 0
failed = 0

for code, name in updates.items():
    safe_name = name.replace("'", "''")
    update_query = f"""
    UPDATE `dj-ga4.scd.research_results`
    SET chousa_bukkenmei = '{safe_name}'
    WHERE purojiekutokoodo = '{code}'
    """
    try:
        job = bq.execute_query(update_query)
        affected = getattr(job, "num_dml_affected_rows", None)
        logger.info(f"✓ {code}: {name} (affected: {affected})")
        success += 1
    except Exception as e:
        logger.error(f"✗ {code}: {e}")
        failed += 1

logger.info(f"\n=== 実行結果 ===")
logger.info(f"成功: {success}コード / 失敗: {failed}コード")

progress_query = """
SELECT
    COUNT(*) as total,
    COUNTIF(chousa_bukkenmei IS NOT NULL AND chousa_bukkenmei != '') as filled
FROM `dj-ga4.scd.research_results`
"""
p = bq.fetch_results(progress_query)[0]
logger.info(f"\n=== chousa_bukkenmei 全体進捗 ===")
logger.info(f"総件数: {p.total}件")
logger.info(f"入力済み: {p.filled}件（{p.filled / p.total * 100:.1f}%）")

logger.info("\n" + "=" * 70)
