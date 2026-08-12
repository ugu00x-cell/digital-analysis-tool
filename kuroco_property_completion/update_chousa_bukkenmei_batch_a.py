"""A) biko から自動抽出できた物件名を chousa_bukkenmei に転記（誤抽出3件は除外）"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("A) 自動抽出できた物件名を chousa_bukkenmei に転記（26件）")
logger.info("=" * 70)

# 誤抽出3件（36110009, 37110008, 40200600）を除いた26件
updates = {
    '33110044': 'ブランズタワー芝浦',
    '36110016': 'ブランシエラ赤坂はなみずき通り',
    '36110023': 'MJR深川住吉',
    '37111700': 'ル・サンク津田沼',
    '37210007': 'エムズシティ鳴子プレディア',
    '38100100': 'リビオ船橋夏見',
    '38100200': 'ハイムスイート平岸ブランシエライースト',
    '38100300': 'エクセレント・ザ・タワー',
    '38100900': 'つくばテラス',
    '38101600': 'ブランシエラ札幌桑園',
    '38105600': 'ファインレジデンス蓮田ブランシエラ',
    '38105700': 'ハイムスイートつくば春日',
    '38106200': 'グレーシア湘南平塚海岸',
    '38108000': 'プラウド水戸桜川',
    '38108400': 'オーベル千葉エアーズ',
    '39100100': 'リビオシティ南砂町ステーションサイト',
    '39100300': 'プレミスト青森新町ザ・タワー',
    '39100400': 'ソライエ新鎌ヶ谷',
    '39100500': 'バウス金町',
    '39100700': 'レジデンシャル原ブランシエラ',  # 2レコード共通（S棟／N棟）
    '39102600': 'プレディア西葛西',
    '39103700': 'ソライエ若葉ステーションヴィラ',
    '39103800': 'サングランデ千葉都賀テラス',
    '40102300': 'ファインレジデンス高崎ステーションサイド',
    '40106000': 'ルフォン松戸北小金',
}

logger.info(f"\n対象件数: {len(updates)}コード")

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

# 全体進捗確認
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
