"""駅・沿線マスタとのマッピング処理"""

import logging
from typing import Optional, Dict, List
from utils.text_matcher import TextMatcher
from services.bigquery_handler import BigQueryHandler

logger = logging.getLogger(__name__)


class MasterMapper:
    """
    project_info テーブルの既存駅・沿線コード対応を活用して、
    research_results の駅名・沿線名にコードを補完するクラス
    """

    def __init__(self, bigquery_handler: BigQueryHandler, threshold: float = 0.75):
        """
        初期化

        Args:
            bigquery_handler: BigQueryHandler インスタンス
            threshold: Fuzzy matching の閾値（0.0-1.0）
        """
        self.bq = bigquery_handler
        self.text_matcher = TextMatcher(threshold=threshold)
        self.station_code_map: Dict[str, str] = {}
        self.line_code_map: Dict[str, str] = {}
        logger.info(f"MasterMapper initialized with threshold={threshold}")

    def load_master_data(self) -> None:
        """
        project_info テーブルから既存の駅・沿線コード対応をロード
        """
        logger.info("Loading master data from project_info...")

        # 駅コード対応を取得
        station_query = """
        SELECT DISTINCT ekimei, ekikoodo
        FROM `dj-ga4.scd.project_info`
        WHERE ekimei IS NOT NULL AND ekikoodo IS NOT NULL
        """

        try:
            results = self.bq.fetch_results(station_query)
            for row in results:
                if row.ekimei and row.ekikoodo:
                    self.station_code_map[row.ekimei] = row.ekikoodo
            logger.info(f"Loaded {len(self.station_code_map)} station mappings")
        except Exception as e:
            logger.error(f"Failed to load station mappings: {e}")

        # 沿線コード対応を取得
        line_query = """
        SELECT DISTINCT ensenmei, ensenkoodo
        FROM `dj-ga4.scd.project_info`
        WHERE ensenmei IS NOT NULL AND ensenkoodo IS NOT NULL
        """

        try:
            results = self.bq.fetch_results(line_query)
            for row in results:
                if row.ensenmei and row.ensenkoodo:
                    self.line_code_map[row.ensenmei] = row.ensenkoodo
            logger.info(f"Loaded {len(self.line_code_map)} line mappings")
        except Exception as e:
            logger.error(f"Failed to load line mappings: {e}")

    def complement_station_codes(self, target_table: str = "research_results") -> int:
        """
        research_results テーブルの駅名に対応するコードを補完

        Args:
            target_table: 対象テーブル名

        Returns:
            補完された件数
        """
        if not self.station_code_map:
            logger.warning("Station code map is empty. Load master data first.")
            return 0

        logger.info("Complementing station codes...")

        # 駅名が入っているが、コードが無いレコードを取得
        query = f"""
        SELECT purojiekutokoodo, ekimei
        FROM `dj-ga4.scd.{target_table}`
        WHERE ekimei IS NOT NULL AND ekimei != ''
        """

        try:
            results = self.bq.fetch_results(query)
            complemented_count = 0

            for row in results:
                ekikoodo = self._find_best_station_code(row.ekimei)
                if ekikoodo:
                    # UPDATE 実行（現在は dry-run）
                    logger.debug(f"Update: {row.ekimei} -> {ekikoodo}")
                    complemented_count += 1

            logger.info(f"Complemented {complemented_count} station codes")
            return complemented_count

        except Exception as e:
            logger.error(f"Complement operation failed: {e}")
            raise

    def complement_line_codes(self, target_table: str = "research_results") -> int:
        """
        research_results テーブルの沿線名に対応するコードを補完

        Args:
            target_table: 対象テーブル名

        Returns:
            補完された件数
        """
        if not self.line_code_map:
            logger.warning("Line code map is empty. Load master data first.")
            return 0

        logger.info("Complementing line codes...")

        # 沿線名が入っているが、コードが無いレコードを取得
        query = f"""
        SELECT purojiekutokoodo, ensenmei
        FROM `dj-ga4.scd.{target_table}`
        WHERE ensenmei IS NOT NULL AND ensenmei != ''
        """

        try:
            results = self.bq.fetch_results(query)
            complemented_count = 0

            for row in results:
                ensenkoodo = self._find_best_line_code(row.ensenmei)
                if ensenkoodo:
                    # UPDATE 実行（現在は dry-run）
                    logger.debug(f"Update: {row.ensenmei} -> {ensenkoodo}")
                    complemented_count += 1

            logger.info(f"Complemented {complemented_count} line codes")
            return complemented_count

        except Exception as e:
            logger.error(f"Complement operation failed: {e}")
            raise

    def _find_best_station_code(self, station_name: str) -> Optional[str]:
        """
        駅名から最適なコードを検索

        Args:
            station_name: 駅名

        Returns:
            駅コード。見つからない場合は None
        """
        if not station_name:
            return None

        # 正確な一致を優先
        if station_name in self.station_code_map:
            return self.station_code_map[station_name]

        # Fuzzy matching で最適なコードを検索
        candidates = list(self.station_code_map.keys())
        match_result = self.text_matcher.find_best_match(station_name, candidates)

        if match_result:
            best_match, score = match_result
            code = self.station_code_map[best_match]
            logger.debug(f"Fuzzy matched: '{station_name}' -> '{best_match}' (code={code}, score={score:.2f})")
            return code

        return None

    def _find_best_line_code(self, line_name: str) -> Optional[str]:
        """
        沿線名から最適なコードを検索

        Args:
            line_name: 沿線名

        Returns:
            沿線コード。見つからない場合は None
        """
        if not line_name:
            return None

        # 正確な一致を優先
        if line_name in self.line_code_map:
            return self.line_code_map[line_name]

        # Fuzzy matching で最適なコードを検索
        candidates = list(self.line_code_map.keys())
        match_result = self.text_matcher.find_best_match(line_name, candidates)

        if match_result:
            best_match, score = match_result
            code = self.line_code_map[best_match]
            logger.debug(f"Fuzzy matched: '{line_name}' -> '{best_match}' (code={code}, score={score:.2f})")
            return code

        return None
