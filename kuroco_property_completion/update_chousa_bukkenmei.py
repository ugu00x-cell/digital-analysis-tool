"""chousa_bukkenmei への転記（①判明11件 + ③要注意2件）"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("chousa_bukkenmei への転記（① 判明11件 + ③ 要注意2件）")
logger.info("=" * 70)

# ① 物件名が判明した11件
identified = {
    '37110010': '白金ザ・スカイ',
    '38101100': 'ルネ湘南茅ヶ崎',
    '38104700': 'ル・サンク小田原栄町',
    '38105100': 'ブリリア金沢本町',
    '38105400': 'ハイムスイート西千葉',
    '38106700': 'オーベル習志野大久保',
    '38108500': 'センチュリー葛西グリーンフィールド',
    '39102000': 'シャリエ朝霞グランフィールド',
    '39102300': 'ガーラ・レジデンス船橋',
    '40102100': 'グローイングスクエア世田谷千歳台Ⅱ',
    '40103800': 'グローイングスクエア国立東グランデ',
}

# ③ 要注意2件：bukkenmei の値をそのまま chousa_bukkenmei に転記（biko は変更しない）
suspect_2 = {
    '41110400': 'パラダイスR浦和美園',
    '43105300': 'クレアホームズ盛岡本町通3丁目',
}

all_updates = {**identified, **suspect_2}
logger.info(f"\n対象件数: {len(all_updates)}件")

success = 0
failed = 0

for code, name in all_updates.items():
    # SQLインジェクション対策：シングルクォートをエスケープ
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
logger.info(f"成功: {success}件")
logger.info(f"失敗: {failed}件")

# 確認
logger.info(f"\n=== 反映確認 ===")
codes_str = ",".join(f"'{c}'" for c in all_updates.keys())
verify_query = f"""
SELECT purojiekutokoodo, bukkenmei, chousa_bukkenmei
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo IN ({codes_str})
ORDER BY purojiekutokoodo
"""
results = bq.fetch_results(verify_query)
for row in results:
    logger.info(f"  {row.purojiekutokoodo}: {row.bukkenmei} → {row.chousa_bukkenmei}")

# 全体の進捗確認
logger.info(f"\n=== chousa_bukkenmei 全体進捗 ===")
progress_query = """
SELECT
    COUNT(*) as total,
    COUNTIF(chousa_bukkenmei IS NOT NULL AND chousa_bukkenmei != '') as filled
FROM `dj-ga4.scd.research_results`
"""
p = bq.fetch_results(progress_query)[0]
logger.info(f"総件数: {p.total}件")
logger.info(f"chousa_bukkenmei 入力済み: {p.filled}件")

logger.info("\n" + "=" * 70)
