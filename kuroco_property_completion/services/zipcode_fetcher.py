"""郵便番号補完ロジック"""

import logging
from typing import Optional, Tuple
from services.bigquery_handler import BigQueryHandler

logger = logging.getLogger(__name__)


class ZipcodeFetcher:
    """
    zipcode_master テーブルを参照して、
    research_results テーブルの郵便番号を補完するクラス
    """

    def __init__(self, bigquery_handler: BigQueryHandler):
        """
        初期化

        Args:
            bigquery_handler: BigQueryHandler インスタンス
        """
        self.bq = bigquery_handler
        logger.info("ZipcodeFetcher initialized")

    def fetch_zipcode_by_address(self, address_key: str) -> Optional[Tuple[str, str]]:
        """
        住所キーから郵便番号を検索（zipcode_master テーブル参照）

        Args:
            address_key: 住所キー（例：東京都渋谷区）

        Returns:
            (郵便番号1, 郵便番号2) のタプル。見つからない場合は None
        """
        if not address_key:
            logger.debug(f"Invalid address_key: {address_key}")
            return None

        # zipcode_master の構造に合わせた SQL
        # 実際のカラム名に基づいて実行
        query = f"""
        SELECT DISTINCT
            SUBSTR(yubinkodo, 1, 3) AS yubinkodo1,
            SUBSTR(yubinkodo, 4, 4) AS yubinkodo2
        FROM `dj-ga4.scd.zipcode_master`
        WHERE todofuken_shikuchoson LIKE '%{address_key}%'
           OR CONCAT(todofuken, shikuchoson) LIKE '%{address_key}%'
        LIMIT 1
        """

        try:
            results = self.bq.fetch_results(query)
            if results:
                row = results[0]
                zipcode1 = str(row.yubinkodo1) if row.yubinkodo1 else None
                zipcode2 = str(row.yubinkodo2) if row.yubinkodo2 else None
                logger.info(f"Found zipcode for {address_key}: {zipcode1}-{zipcode2}")
                return (zipcode1, zipcode2)
            else:
                logger.debug(f"No zipcode found for {address_key}")
                return None
        except Exception as e:
            logger.error(f"Zipcode lookup failed for {address_key}: {e}")
            return None

    def complement_research_results(self, target_table: str = "research_results") -> int:
        """
        research_results テーブルの郵便番号未入力レコードを一括補完

        Args:
            target_table: 対象テーブル名（デフォルト："research_results"）

        Returns:
            補完された件数
        """
        # 郵便番号が NULL で、住所情報がある行を取得
        # 注：カラム名は実際のBigQueryテーブルに合わせて調整必要
        query = f"""
        SELECT
            purojiekutokoodo AS id,
            todofuken,
            shikuchoson,
            yubinkodo1,
            yubinkodo2
        FROM `dj-ga4.scd.{target_table}`
        WHERE (yubinkodo1 IS NULL OR yubinkodo1 = '')
            AND todofuken IS NOT NULL
            AND shikuchoson IS NOT NULL
        ORDER BY purojiekutokoodo
        LIMIT 1000
        """

        try:
            results = self.bq.fetch_results(query)
            complemented_count = 0

            for row in results:
                zipcode_result = self.fetch_zipcode_by_address(
                    row.todofuken,
                    row.shikuchoson
                )

                if zipcode_result:
                    zipcode1, zipcode2 = zipcode_result
                    # UPDATE 実行
                    self._update_zipcode(target_table, row.id, zipcode1, zipcode2)
                    complemented_count += 1

            logger.info(f"Complemented {complemented_count} rows with zipcode")
            return complemented_count

        except Exception as e:
            logger.error(f"Complement operation failed: {e}")
            raise

    def _update_zipcode(self, table_id: str, record_id: int, zipcode1: str, zipcode2: str) -> None:
        """
        特定レコードの郵便番号を更新

        Args:
            table_id: テーブルID
            record_id: レコードID
            zipcode1: 郵便番号1
            zipcode2: 郵便番号2
        """
        full_table_id = f"dj-ga4.scd.{table_id}"

        # NULL 安全な値に変換
        z1_val = f"'{zipcode1}'" if zipcode1 else "NULL"
        z2_val = f"'{zipcode2}'" if zipcode2 else "NULL"

        update_query = f"""
        UPDATE {full_table_id}
        SET
            yubinkodo1 = {z1_val},
            yubinkodo2 = {z2_val}
        WHERE id = {record_id}
        """

        try:
            self.bq.execute_query(update_query)
            logger.debug(f"Updated zipcode for record {record_id}")
        except Exception as e:
            logger.error(f"Update failed for record {record_id}: {e}")
            raise
