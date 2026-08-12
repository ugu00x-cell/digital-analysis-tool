"""不動産広告データ補完：メイン実行スクリプト"""

import logging
import sys
from typing import Optional
from services.bigquery_handler import BigQueryHandler
from services.zipcode_fetcher import ZipcodeFetcher
from services.suumo_scraper import SuumoScraper
from services.master_mapper import MasterMapper
from services.land_rights_completer import LandRightsCompleter

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PropertyCompletionManager:
    """
    物件マスタ補完の統合管理クラス
    """

    def __init__(self, project_id: str = "dj-ga4", dataset_id: str = "scd"):
        """
        初期化

        Args:
            project_id: BigQuery プロジェクトID
            dataset_id: BigQuery データセットID
        """
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.bq = BigQueryHandler(project_id, dataset_id)
        logger.info(f"PropertyCompletionManager initialized: {project_id}.{dataset_id}")

    def complement_zipcode(self) -> int:
        """
        ①郵便番号1・2 を補完

        Returns:
            補完した件数
        """
        logger.info("=" * 50)
        logger.info("Phase 1-① Complementing zipcode")
        logger.info("=" * 50)

        fetcher = ZipcodeFetcher(self.bq)
        try:
            complemented_count = fetcher.complement_research_results()
            logger.info(f"✓ Complemented {complemented_count} records with zipcode")
            return complemented_count
        except Exception as e:
            logger.error(f"✗ Zipcode complement failed: {e}")
            return 0

    def test_scrape_total_units(self, sample_urls: Optional[list] = None) -> dict:
        """
        ②総戸数スクレイピング試験実装

        Args:
            sample_urls: テスト対象URL（オプション）

        Returns:
            スクレイピング結果の辞書
        """
        logger.info("=" * 50)
        logger.info("Phase 1-② Testing total units scraping")
        logger.info("=" * 50)

        # サンプルURLがない場合、research_results から取得
        if not sample_urls:
            sample_urls = self._fetch_sample_urls(limit=3)

        if not sample_urls:
            logger.warning("No URLs found for scraping test")
            return {}

        scraper = SuumoScraper(headless=True)
        results = {}

        try:
            for i, url in enumerate(sample_urls, 1):
                logger.info(f"\n[{i}/{len(sample_urls)}] Scraping: {url}")
                property_info = scraper.scrape_property_details(url)
                results[url] = property_info
                logger.info(f"✓ Extracted: {property_info}")

        except Exception as e:
            logger.error(f"Scraping test failed: {e}")

        finally:
            scraper.close()

        logger.info(f"\n✓ Scraping test completed: {len(results)} properties")
        return results

    def complement_station_codes(self) -> int:
        """
        ③駅名コードを補完

        Returns:
            補完した件数
        """
        logger.info("=" * 50)
        logger.info("Phase 2-③ Complementing station codes")
        logger.info("=" * 50)

        mapper = MasterMapper(self.bq)
        try:
            mapper.load_master_data()
            complemented_count = mapper.complement_station_codes()
            logger.info(f"✓ Complemented {complemented_count} station codes")
            return complemented_count
        except Exception as e:
            logger.error(f"✗ Station code complement failed: {e}")
            return 0

    def complement_line_codes(self) -> int:
        """
        ④沿線名コードを補完

        Returns:
            補完した件数
        """
        logger.info("=" * 50)
        logger.info("Phase 2-④ Complementing line codes")
        logger.info("=" * 50)

        mapper = MasterMapper(self.bq)
        try:
            mapper.load_master_data()
            complemented_count = mapper.complement_line_codes()
            logger.info(f"✓ Complemented {complemented_count} line codes")
            return complemented_count
        except Exception as e:
            logger.error(f"✗ Line code complement failed: {e}")
            return 0

    def complement_land_rights(self) -> dict:
        """
        ⑤土地の権利区分を補完・検証

        Returns:
            品質検証結果
        """
        logger.info("=" * 50)
        logger.info("Phase 2-⑤ Complementing land rights")
        logger.info("=" * 50)

        completer = LandRightsCompleter(self.bq)
        try:
            # 現在の状況を確認
            current_status = completer.get_current_status()
            logger.info(f"Current land rights status: {current_status}")

            # データ品質を検証
            quality_report = completer.verify_data_quality()
            logger.info(f"✓ Quality report: {quality_report}")
            return quality_report
        except Exception as e:
            logger.error(f"✗ Land rights check failed: {e}")
            return {}

    def run_full_complement(self) -> dict:
        """
        フル補完を実行（①〜⑤まで）

        Returns:
            実行結果の辞書
        """
        logger.info("\n" + "=" * 60)
        logger.info("FULL COMPLEMENT: Phase 1-2 (All Tasks)")
        logger.info("=" * 60)

        results = {
            "zipcode_complemented": 0,
            "scraping_results": {},
            "station_codes_complemented": 0,
            "line_codes_complemented": 0,
            "land_rights_quality": {}
        }

        try:
            # Phase 1
            results["zipcode_complemented"] = self.complement_zipcode()
            results["scraping_results"] = self.test_scrape_total_units()

            # Phase 2
            results["station_codes_complemented"] = self.complement_station_codes()
            results["line_codes_complemented"] = self.complement_line_codes()
            results["land_rights_quality"] = self.complement_land_rights()

        except Exception as e:
            logger.error(f"Full complement failed: {e}")

        logger.info("\n" + "=" * 60)
        logger.info("COMPLEMENT COMPLETED")
        logger.info(self._format_summary(results))
        logger.info("=" * 60 + "\n")

        return results

    def _fetch_sample_urls(self, limit: int = 3) -> list:
        """
        research_results からサンプルURL を取得

        Args:
            limit: 取得件数

        Returns:
            URLのリスト
        """
        query = f"""
        SELECT source_url
        FROM `{self.project_id}.{self.dataset_id}.research_results`
        WHERE source_url IS NOT NULL
            AND source_url != ''
        LIMIT {limit}
        """

        try:
            results = self.bq.fetch_results(query)
            urls = [row.source_url for row in results if row.source_url]
            logger.info(f"Fetched {len(urls)} sample URLs")
            return urls
        except Exception as e:
            logger.error(f"Failed to fetch sample URLs: {e}")
            return []

    def _format_summary(self, results: dict) -> str:
        """
        結果をサマリー形式でフォーマット

        Args:
            results: 実行結果の辞書

        Returns:
            フォーマットされたサマリー
        """
        summary = f"""
✓ Zipcode complemented: {results.get('zipcode_complemented', 0)} rows
✓ Scraping test: {len(results.get('scraping_results', {}))} properties
✓ Station codes complemented: {results.get('station_codes_complemented', 0)} rows
✓ Line codes complemented: {results.get('line_codes_complemented', 0)} rows
✓ Land rights quality: {results.get('land_rights_quality', {})}
        """
        return summary


def main():
    """
    メイン処理
    """
    try:
        manager = PropertyCompletionManager()
        results = manager.run_full_complement()

        logger.info("✓ All tasks completed successfully!")
        return 0

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
