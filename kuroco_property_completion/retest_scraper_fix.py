"""修正した抽出ロジックを朝と同じサンプルで再テスト"""

import logging
from services.bigquery_handler import BigQueryHandler
from services.suumo_scraper import SuumoScraper

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')
scraper = SuumoScraper()

# 朝テストした問題のあったURL（つくばグランヴィラ・ウエリス豊中桃山台・鎌ヶ谷市新鎌ヶ谷）を再確認
test_cases = [
    ("39100600", "つくばグランヴィラ", "https://www.mansion-review.jp/mansion/1433690.html", "203"),
    ("31210013", "ウエリス豊中桃山台", "https://www.mansion-review.jp/mansion/747100.html", "87"),
    ("39100400", "鎌ヶ谷市新鎌ヶ谷", "https://www.mansion-review.jp/mansion/1440086.html", "136"),
]

logger.info("=" * 70)
logger.info("修正後の抽出ロジック 再テスト")
logger.info("=" * 70)

for code, name, url, expected in test_cases:
    logger.info(f"\n--- {code}: {name} ---")
    logger.info(f"期待値: {expected}戸")
    try:
        info = scraper.scrape_property_details(url)
        result = info.get("total_units")
        if result == expected:
            logger.info(f"✅ 一致: {result}戸")
        elif result:
            logger.warning(f"⚠️ 不一致: 抽出値={result}戸 (期待値={expected}戸)")
        else:
            logger.warning(f"⚠️ 抽出できず")
    except Exception as e:
        logger.error(f"✗ エラー: {e}")

scraper.close()
logger.info("\n" + "=" * 70)
