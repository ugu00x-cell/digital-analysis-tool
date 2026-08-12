"""土地の権利区分補完ロジック"""

import logging
from typing import Optional, Dict, List
from services.bigquery_handler import BigQueryHandler

logger = logging.getLogger(__name__)


class LandRightsCompleter:
    """
    土地の権利区分を補完するクラス
    スクレイピングまたはマスタデータ参照で補完
    """

    # 権利区分の標準値
    STANDARD_RIGHTS = [
        "所有権",
        "所有権の共有",
        "借地権",
        "定期借地権",
        "不明",
    ]

    def __init__(self, bigquery_handler: BigQueryHandler):
        """
        初期化

        Args:
            bigquery_handler: BigQueryHandler インスタンス
        """
        self.bq = bigquery_handler
        logger.info("LandRightsCompleter initialized")

    def get_current_status(self, target_table: str = "research_results") -> Dict[str, int]:
        """
        研究対象テーブルの権利区分の現在状況を確認

        Args:
            target_table: 対象テーブル名

        Returns:
            権利区分ごとの件数
        """
        query = f"""
        SELECT
            tochinokenrikubun,
            COUNT(*) as count
        FROM `dj-ga4.scd.{target_table}`
        GROUP BY tochinokenrikubun
        ORDER BY count DESC
        """

        try:
            results = self.bq.fetch_results(query)
            status_dict = {}
            for row in results:
                status_dict[row.tochinokenrikubun or "NULL"] = row.count
            logger.info(f"Land rights status: {status_dict}")
            return status_dict
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return {}

    def standardize_rights(self, rights_text: str) -> str:
        """
        権利区分テキストを標準値に統一

        Args:
            rights_text: 入力テキスト

        Returns:
            標準化された権利区分
        """
        if not rights_text:
            return "不明"

        text = str(rights_text).strip()

        # 標準値との完全一致
        if text in self.STANDARD_RIGHTS:
            return text

        # よくある表記ゆれの補正
        corrections = {
            "所有": "所有権",
            "共有": "所有権の共有",
            "借地": "借地権",
            "定期借地": "定期借地権",
            "未確認": "不明",
            "確認中": "不明",
            "null": "不明",
            "": "不明",
        }

        for pattern, standard in corrections.items():
            if pattern.lower() in text.lower():
                logger.debug(f"Corrected: '{text}' -> '{standard}'")
                return standard

        # デフォルトは「不明」
        logger.debug(f"Could not standardize: '{text}' -> '不明'")
        return "不明"

    def complement_from_scraping_data(
        self, property_code: str, scraped_data: Dict
    ) -> Optional[str]:
        """
        スクレイピングデータから権利区分を抽出・補完

        Args:
            property_code: 物件コード
            scraped_data: スクレイピングで抽出したデータ

        Returns:
            標準化された権利区分。見つからない場合は None
        """
        if not scraped_data:
            return None

        # スクレイピングデータから権利区分を探す
        land_rights = scraped_data.get("land_rights")
        if land_rights:
            return self.standardize_rights(land_rights)

        return None

    def verify_data_quality(self, target_table: str = "research_results") -> Dict:
        """
        データ品質を検証

        Args:
            target_table: 対象テーブル名

        Returns:
            品質検証結果
        """
        query = f"""
        SELECT
            COUNT(*) as total_rows,
            COUNTIF(tochinokenrikubun IS NULL) as null_count,
            COUNTIF(tochinokenrikubun = '不明') as unknown_count,
            COUNTIF(tochinokenrikubun NOT IN ('所有権', '所有権の共有', '借地権', '定期借地権', '不明', NULL)) as invalid_count
        FROM `dj-ga4.scd.{target_table}`
        """

        try:
            results = self.bq.fetch_results(query)
            if results:
                row = results[0]
                quality_report = {
                    "total_rows": row.total_rows,
                    "null_count": row.null_count,
                    "unknown_count": row.unknown_count,
                    "invalid_count": row.invalid_count,
                    "completion_rate": (
                        (row.total_rows - row.null_count - row.unknown_count) / row.total_rows * 100
                        if row.total_rows > 0
                        else 0
                    ),
                }
                logger.info(f"Quality report: {quality_report}")
                return quality_report
        except Exception as e:
            logger.error(f"Quality check failed: {e}")

        return {}
