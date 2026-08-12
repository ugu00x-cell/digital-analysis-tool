"""郵便番号の正確性を検証"""

import re
import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("🌙 甘雨より：郵便番号の正確性を検証させていただきます")
logger.info("=" * 70)

# 郵便番号のフォーマットをチェック
query = """
SELECT
    purojiekutokoodo,
    bukkenmei,
    yubinkodo1,
    yubinkodo2
FROM `dj-ga4.scd.research_results`
WHERE yubinkodo1 IS NOT NULL
ORDER BY RAND()
LIMIT 20
"""

results = bq.fetch_results(query)

logger.info(f"\n【郵便番号フォーマット検証】\n")

valid_count = 0
invalid_count = 0
samples = []

for row in results:
    zip1 = str(row.yubinkodo1) if row.yubinkodo1 else ""
    zip2 = str(row.yubinkodo2) if row.yubinkodo2 else ""

    # 郵便番号の形式チェック（上3桁-下4桁 or 上3桁-下2桁など）
    # 一般的には上3桁は数字、下4桁は数字
    if zip1.isdigit() and len(zip1) == 3 and zip2.isdigit() and len(zip2) in [2, 3, 4]:
        valid_count += 1
        status = "✅ 正常"
    else:
        invalid_count += 1
        status = "❌ 不正"

    samples.append({
        'code': row.purojiekutokoodo,
        'name': row.bukkenmei,
        'zip': f"{zip1}-{zip2}",
        'status': status,
        'zip1_len': len(zip1),
        'zip2_len': len(zip2)
    })

for s in samples:
    logger.info(f"{s['status']} {s['code']}: {s['name']}")
    logger.info(f"   郵便番号: {s['zip']} (上{s['zip1_len']}-下{s['zip2_len']})")

logger.info(f"\n【検証結果サマリー】")
logger.info(f"正常な郵便番号: {valid_count}件")
logger.info(f"不正な郵便番号: {invalid_count}件")
logger.info(f"検証率: {valid_count / (valid_count + invalid_count) * 100:.1f}%")

# project_info との照合サンプル
logger.info(f"\n【project_info との照合（サンプル）】\n")

cross_check = """
SELECT
    r.purojiekutokoodo,
    r.yubinkodo1 as research_zip1,
    r.yubinkodo2 as research_zip2,
    p.yuubinbangou1_ue3keta as project_zip1,
    p.yuubinbangou2_shita4keta as project_zip2,
    CASE
        WHEN r.yubinkodo1 = p.yuubinbangou1_ue3keta AND r.yubinkodo2 = p.yuubinbangou2_shita4keta THEN '✅ 一致'
        ELSE '❌ 不一致'
    END as match_status
FROM `dj-ga4.scd.research_results` r
LEFT JOIN `dj-ga4.scd.project_info` p
    ON r.purojiekutokoodo = p.purojiekutokoodo
WHERE r.yubinkodo1 IS NOT NULL
LIMIT 10
"""

matches = bq.fetch_results(cross_check)

match_count = 0
for row in matches:
    if '✅' in row.match_status:
        match_count += 1
    logger.info(f"{row.match_status} {row.purojiekutokoodo}: research({row.research_zip1}-{row.research_zip2}) vs project({row.project_zip1}-{row.project_zip2})")

logger.info(f"\n一致率: {match_count}/{len(matches)}")

logger.info("\n" + "=" * 70)
logger.info("🌙 甘雨より：検証完了いたしました")
logger.info("=" * 70)
