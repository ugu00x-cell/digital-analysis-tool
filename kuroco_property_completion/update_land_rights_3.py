"""ブラウザ調査で判明した3件の情報を反映"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("土地権利未確認3件の調査結果を反映")
logger.info("=" * 70)

# 1. 38101000: 江戸川区松江 → イニシア新小岩ローレルコート（mansion-review.jpで詳細判明）
update1 = """
UPDATE `dj-ga4.scd.research_results`
SET
    chousa_bukkenmei = 'イニシア新小岩ローレルコート',
    tochinokenrikubun = '所有権',
    soukosuujuukyo = '122',
    chijoukaisuu = '14',
    ekimei = '新小岩',
    ensenmei = 'JR中央・総武線',
    toho_fun = '27',
    kakunin_status = '確認済',
    biko = 'mansion-review.jpで詳細確認。都営新宿線船堀駅(徒歩29分)も利用可'
WHERE purojiekutokoodo = '38101000'
"""
job1 = bq.execute_query(update1)
logger.info(f"✓ 38101000（イニシア新小岩ローレルコート）: 全項目反映 (affected: {job1.num_dml_affected_rows})")

# 2. 38102600: 久我山五丁目宅地分譲 → 土地権利=所有権（アーカイブ情報より）
update2 = """
UPDATE `dj-ga4.scd.research_results`
SET
    tochinokenrikubun = '所有権',
    kakunin_status = '確認済',
    biko = 'mansion-review.jpの掲載終了アーカイブより「杉並区久我山5丁目 売地 全3区画」の土地権利=所有権を確認。京王井の頭線 富士見ヶ丘駅徒歩5分/久我山駅徒歩8分'
WHERE purojiekutokoodo = '38102600'
"""
job2 = bq.execute_query(update2)
logger.info(f"✓ 38102600（久我山五丁目宅地分譲）: 土地権利確認 (affected: {job2.num_dml_affected_rows})")

# 3. 38104200: 仮称）グローイングスクエア練馬中村 → グローイングスクエア中村橋（名称・駅確定、権利は不明のまま）
update3 = """
UPDATE `dj-ga4.scd.research_results`
SET
    chousa_bukkenmei = 'グローイングスクエア中村橋',
    ekimei = '中村橋',
    ensenmei = '西武池袋線',
    toho_fun = '5',
    biko = 'マンションではなく戸建て分譲（全4邸）。細田工務店公式サイトで物件名・駅情報を確認。土地権利の明記はサイト上になく不明のまま'
WHERE purojiekutokoodo = '38104200'
"""
job3 = bq.execute_query(update3)
logger.info(f"✓ 38104200（グローイングスクエア中村橋）: 物件名・駅情報反映（権利は不明のまま） (affected: {job3.num_dml_affected_rows})")

# 確認
logger.info(f"\n=== 反映後の確認 ===")
codes = ['38101000', '38102600', '38104200']
codes_str = ",".join(f"'{c}'" for c in codes)
verify_query = f"""
SELECT purojiekutokoodo, bukkenmei, chousa_bukkenmei, tochinokenrikubun, kakunin_status,
       ekimei, ensenmei, toho_fun, soukosuujuukyo, chijoukaisuu
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo IN ({codes_str})
"""
results = bq.fetch_results(verify_query)
for row in results:
    logger.info(f"\n{row.purojiekutokoodo}: {row.bukkenmei}")
    logger.info(f"  chousa_bukkenmei: {row.chousa_bukkenmei}")
    logger.info(f"  土地権利: {row.tochinokenrikubun} / 確認状況: {row.kakunin_status}")
    logger.info(f"  駅: {row.ekimei}（{row.ensenmei}）徒歩{row.toho_fun}分")
    logger.info(f"  総戸数: {row.soukosuujuukyo} / 階建: {row.chijoukaisuu}")

logger.info("\n" + "=" * 70)
