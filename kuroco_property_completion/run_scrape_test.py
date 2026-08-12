"""総戸数スクレイピング試験実行スクリプト"""

import logging
from services.bigquery_handler import BigQueryHandler
from services.suumo_scraper import SuumoScraper

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')
scraper = SuumoScraper()

logger.info("=== 総戸数スクレイピング試験実行 ===")

# 1. source_url が入っているレコードを取得
query = """
SELECT purojiekutokoodo, bukkenmei, source_url, soukosuujuukyo
FROM `dj-ga4.scd.research_results`
WHERE source_url IS NOT NULL AND source_url != ''
ORDER BY RAND()
LIMIT 5
"""

results = bq.fetch_results(query)
logger.info(f"スクレイピング対象: {len(results)}件\n")

# 2. 各レコードについてスクレイピング試験
success = 0
failed = 0

for row in results:
    code = row.purojiekutokoodo
    name = row.bukkenmei
    url = row.source_url
    current_soukosuu = row.soukosuujuukyo

    logger.info(f"--- {code} | {name} ---")
    logger.info(f"URL: {url}")
    logger.info(f"現在値: {current_soukosuu}")

    try:
        # スクレイピング実行
        info = scraper.scrape_property_details(url)
        soukosuu = info.get("total_units") if info else None

        if soukosuu:
            logger.info(f"✓ スクレイピング成功: {soukosuu}戸")

            # BigQuery に UPDATE（試験なので実際には更新しない）
            logger.info(f"  → BigQuery UPDATE (試験中、実施なし)")
            success += 1
        else:
            logger.warning(f"⚠ 総戸数情報取得できず")
            failed += 1

    except Exception as e:
        logger.error(f"✗ スクレイピングエラー: {e}")
        failed += 1

logger.info(f"\n=== 試験実行結果 ===")
logger.info(f"成功: {success}件")
logger.info(f"失敗: {failed}件")
logger.info(f"成功率: {success / len(results) * 100:.1f}%")
