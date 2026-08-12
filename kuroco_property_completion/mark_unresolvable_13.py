"""特定不可の13件を「biko空欄・chousa_bukkenmei空欄」で確定させる
（鬼塚さんのご判断に基づく処理。既にNULLだが、確認ログを残すため明示的にUPDATEする）
"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("特定不可13件の確定処理（chousa_bukkenmei空欄・biko空欄で確定）")
logger.info("=" * 70)

# 特定不可と判断された13件のプロジェクトコード（鬼塚さんの判断・8/11報告分）
unresolvable_codes = [
    '34210011', '35110035', '38101000', '41102900', '41103600',
    '41103900', '41108100', '42107400', '42107800', '42108800',
    '43100900', '43101900', '43102000',
]

logger.info(f"\n対象件数: {len(unresolvable_codes)}件")

# 重複行の存在を先に確認（34210011, 35110035 で重複が見つかっている）
dup_check_query = f"""
SELECT purojiekutokoodo, COUNT(*) as cnt
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo IN ({",".join(f"'{c}'" for c in unresolvable_codes)})
GROUP BY purojiekutokoodo
HAVING COUNT(*) > 1
"""
dups = bq.fetch_results(dup_check_query)
if dups:
    logger.warning(f"\n⚠️ 重複行が見つかりました（先に確認が必要）:")
    for d in dups:
        logger.warning(f"  {d.purojiekutokoodo}: {d.cnt}行")
    logger.warning("重複解消は別途対応が必要です。今回のUPDATEは全ての重複行に適用されます。")

# chousa_bukkenmei と biko をNULLに確定（既にNULLの場合も明示的に処理）
update_query = f"""
UPDATE `dj-ga4.scd.research_results`
SET
    chousa_bukkenmei = NULL,
    biko = NULL
WHERE purojiekutokoodo IN ({",".join(f"'{c}'" for c in unresolvable_codes)})
"""

logger.info(f"\n=== UPDATE実行中 ===")
try:
    bq.execute_query(update_query)
    logger.info("✓ 実行完了")
except Exception as e:
    logger.error(f"✗ エラー: {e}")

# 確認
logger.info(f"\n=== 確認 ===")
verify_query = f"""
SELECT purojiekutokoodo, bukkenmei, chousa_bukkenmei, biko
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo IN ({",".join(f"'{c}'" for c in unresolvable_codes)})
ORDER BY purojiekutokoodo
"""
results = bq.fetch_results(verify_query)
logger.info(f"該当レコード数: {len(results)}件（重複除けば期待値13件）")
for row in results:
    logger.info(f"  {row.purojiekutokoodo}: chousa_bukkenmei={row.chousa_bukkenmei!r} biko={row.biko!r}")

logger.info("\n" + "=" * 70)
