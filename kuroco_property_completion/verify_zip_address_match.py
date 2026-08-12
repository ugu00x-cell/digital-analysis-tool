"""郵便番号と住所（都道府県・市区町村）の整合性をzipcode_masterで検証"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("🌙 甘雨より：郵便番号と住所の整合性を検証いたします")
logger.info("=" * 70)

# research_results の郵便番号 + project_info の住所 + zipcode_master の正解 を突合
query = """
SELECT
    r.purojiekutokoodo,
    r.bukkenmei,
    r.yubinkodo1,
    r.yubinkodo2,
    p.todoufukenmei_kanji,
    p.shikuchousonmei_kanji,
    z.string_field_6 as master_pref,
    z.string_field_7 as master_city
FROM `dj-ga4.scd.research_results` r
LEFT JOIN `dj-ga4.scd.project_info` p
    ON r.purojiekutokoodo = p.purojiekutokoodo
LEFT JOIN `dj-ga4.scd.zipcode_master` z
    ON LPAD(CAST(z.int64_field_2 AS STRING), 7, '0') = LPAD(r.yubinkodo1, 3, '0') || LPAD(r.yubinkodo2, 4, '0')
WHERE r.yubinkodo1 IS NOT NULL AND r.yubinkodo1 != ''
"""

results = bq.fetch_results(query)
logger.info(f"\n検証対象: {len(results)}件\n")

match_count = 0
mismatch_count = 0
no_master_count = 0
mismatches = []

for row in results:
    if row.master_pref is None:
        no_master_count += 1
        continue

    pref_match = (row.todoufukenmei_kanji == row.master_pref)
    city_match = (row.shikuchousonmei_kanji == row.master_city)

    if pref_match and city_match:
        match_count += 1
    else:
        mismatch_count += 1
        mismatches.append({
            'code': row.purojiekutokoodo,
            'name': row.bukkenmei,
            'zip': f"{row.yubinkodo1}-{row.yubinkodo2}",
            'project_addr': f"{row.todoufukenmei_kanji}{row.shikuchousonmei_kanji}",
            'master_addr': f"{row.master_pref}{row.master_city}",
        })

logger.info(f"【検証結果サマリー】")
logger.info(f"完全一致: {match_count}件")
logger.info(f"不一致: {mismatch_count}件")
logger.info(f"郵便番号がzipcode_masterに存在しない: {no_master_count}件")

if mismatches:
    logger.info(f"\n【不一致の詳細】")
    for m in mismatches[:20]:
        logger.info(f"{m['code']}: {m['name']}")
        logger.info(f"  郵便番号: {m['zip']}")
        logger.info(f"  project_info住所: {m['project_addr']}")
        logger.info(f"  zipcode_master住所: {m['master_addr']}")

logger.info("\n" + "=" * 70)
logger.info("検証完了")
logger.info("=" * 70)
