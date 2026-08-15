"""
BigQueryから駅名を抽出し、直線距離の算出結果を書き戻すクライアント
"""
import logging
from typing import List

from google.cloud import bigquery

from kuroco_customer_analysis.models.station_pair import StationLocation

logger = logging.getLogger(__name__)

SOURCE_TABLE = "dj-ga4.scd.customer_data"
STATION_MASTER_TABLE = "dj-ga4.scd.station_master"


class BigQueryStationClient:
    """customer_dataから駅名を抽出し、station_master・距離計算結果を書き戻すクライアント"""

    def __init__(self, project_id: str = "dj-ga4") -> None:
        """BigQueryクライアントを初期化する

        Args:
            project_id: 接続先のGCPプロジェクトID
        """
        self.client = bigquery.Client(project=project_id)

    def fetch_unique_station_names(self) -> List[str]:
        """住居・勤務地・購入物件の最寄駅名をまとめてユニーク抽出する

        Returns:
            駅名の文字列リスト（重複なし、null除外）
        """
        query = f"""
            SELECT ekimei AS station_name FROM `{SOURCE_TABLE}` WHERE ekimei IS NOT NULL
            UNION DISTINCT
            SELECT kinmusaki_moyoriekimei AS station_name FROM `{SOURCE_TABLE}`
            WHERE kinmusaki_moyoriekimei IS NOT NULL
            UNION DISTINCT
            SELECT project_ekimei AS station_name FROM `{SOURCE_TABLE}` WHERE project_ekimei IS NOT NULL
        """
        try:
            rows = self.client.query(query).result()
            return [row.station_name for row in rows]
        except Exception:
            logger.exception("ユニーク駅名抽出クエリの実行に失敗しました")
            raise

    def save_station_master(
        self, locations: List[StationLocation], table_id: str = STATION_MASTER_TABLE
    ) -> None:
        """駅名と緯度経度のマスタをBigQueryテーブルに保存する（テーブルは作り直す）

        Args:
            locations: 保存するStationLocationのリスト
            table_id: 保存先テーブルID（例："dj-ga4.scd.station_master"）
        """
        schema = [
            bigquery.SchemaField("station_name", "STRING"),
            bigquery.SchemaField("latitude", "FLOAT64"),
            bigquery.SchemaField("longitude", "FLOAT64"),
            bigquery.SchemaField("status", "STRING"),
        ]
        self.client.delete_table(table_id, not_found_ok=True)
        self.client.create_table(bigquery.Table(table_id, schema=schema))

        rows = [
            {
                "station_name": loc.station_name,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "status": loc.status,
            }
            for loc in locations
        ]
        errors = self.client.insert_rows_json(table_id, rows)
        if errors:
            logger.error("station_masterの書き込みでエラーが発生しました: %s", errors)
            raise RuntimeError(f"BigQuery書き込みエラー: {errors}")
        logger.info("%d件の駅マスタを%sに保存しました", len(rows), table_id)

    def compute_straight_line_distances(self, output_table_id: str) -> None:
        """customer_dataとstation_masterをJOINし、直線距離をBigQuery側で算出する

        購入前区間（住居→勤務地）・購入後区間（勤務地→物件）の直線距離（メートル）を、
        BigQueryのST_DISTANCE関数で計算し、結果テーブルとして保存する。

        Args:
            output_table_id: 出力先テーブルID（例："dj-ga4.scd.commute_distance_results"）
        """
        # station_masterのキーは正規化済み（「駅」サフィックス付与済み）のため、
        # customer_data側もSQL上で同じ正規化ロジックを適用してからJOINする
        normalize = lambda col: f"""
            CASE
              WHEN TRIM({col}) = '' THEN NULL
              WHEN ENDS_WITH(TRIM({col}), '駅') THEN TRIM({col})
              ELSE CONCAT(TRIM({col}), '駅')
            END
        """
        home_key = normalize("c.ekimei")
        work_key = normalize("c.kinmusaki_moyoriekimei")
        property_key = normalize("c.project_ekimei")

        query = f"""
            CREATE OR REPLACE TABLE `{output_table_id}` AS
            SELECT
              c.purojiekutokoodo,
              c.ekimei AS home_station,
              c.kinmusaki_moyoriekimei AS work_station,
              c.project_ekimei AS property_station,
              c.shiryouseikyuunichi,
              c.raihounichi1,
              c.kounyuumoushikomibi,
              c.keiyakunichi,
              ST_DISTANCE(
                ST_GEOGPOINT(s_home.longitude, s_home.latitude),
                ST_GEOGPOINT(s_work.longitude, s_work.latitude)
              ) AS home_to_work_distance_m,
              ST_DISTANCE(
                ST_GEOGPOINT(s_work.longitude, s_work.latitude),
                ST_GEOGPOINT(s_property.longitude, s_property.latitude)
              ) AS work_to_property_distance_m
            FROM `{SOURCE_TABLE}` c
            LEFT JOIN `{STATION_MASTER_TABLE}` s_home
              ON {home_key} = s_home.station_name AND s_home.status = 'OK'
            LEFT JOIN `{STATION_MASTER_TABLE}` s_work
              ON {work_key} = s_work.station_name AND s_work.status = 'OK'
            LEFT JOIN `{STATION_MASTER_TABLE}` s_property
              ON {property_key} = s_property.station_name AND s_property.status = 'OK'
        """
        try:
            self.client.query(query).result()
            logger.info("%sに直線距離の計算結果を保存しました", output_table_id)
        except Exception:
            logger.exception("直線距離の計算クエリの実行に失敗しました")
            raise
