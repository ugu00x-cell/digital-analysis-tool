"""BigQuery テーブル操作ハンドラー"""

import logging
from typing import Optional, List, Dict, Any
from google.cloud import bigquery

logger = logging.getLogger(__name__)


class BigQueryHandler:
    """BigQueryの読み書き操作を担当するクラス"""

    def __init__(self, project_id: str, dataset_id: str):
        """
        初期化

        Args:
            project_id: BigQuery プロジェクトID
            dataset_id: BigQuery データセットID
        """
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.client = bigquery.Client(project=project_id)
        logger.info(f"BigQueryHandler initialized: {project_id}.{dataset_id}")

    def execute_query(self, query: str, job_config: Optional[bigquery.QueryJobConfig] = None) -> bigquery.QueryJob:
        """
        SQLクエリを実行（完了まで待機する）

        Args:
            query: 実行するSQL
            job_config: BigQuery ジョブ設定（オプション）

        Returns:
            QueryJob オブジェクト（実行完了済み）
        """
        try:
            job = self.client.query(query, job_config=job_config)
            job.result()  # ジョブの完了を待つ（これがないとUPDATE/MERGEが未反映のまま関数が返ってしまう）
            affected = getattr(job, "num_dml_affected_rows", None)
            logger.info(
                f"Query executed (affected rows: {affected}): {query[:100]}..."
            )
            return job
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

    def fetch_results(self, query: str) -> List[bigquery.table.Row]:
        """
        SQLクエリを実行して結果を取得

        Args:
            query: 実行するSQL

        Returns:
            クエリ結果のリスト
        """
        try:
            job = self.client.query(query)
            results = list(job.result())
            logger.info(f"Fetched {len(results)} rows")
            return results
        except Exception as e:
            logger.error(f"Fetch failed: {e}")
            raise

    def insert_rows(self, table_id: str, rows: List[Dict[str, Any]]) -> None:
        """
        テーブルに行を挿入

        Args:
            table_id: テーブルID（プロジェクト.データセット.テーブル）
            rows: 挿入する行のリスト
        """
        table = self.client.get_table(table_id)
        try:
            errors = self.client.insert_rows_json(table, rows)
            if errors:
                logger.error(f"Insert errors: {errors}")
                raise Exception(f"Insert failed: {errors}")
            logger.info(f"Inserted {len(rows)} rows to {table_id}")
        except Exception as e:
            logger.error(f"Insert operation failed: {e}")
            raise

    def update_column(self, table_id: str, column_name: str, value: Any, where_clause: str) -> None:
        """
        テーブルの特定カラムを更新（UPDATE文を実行）

        Args:
            table_id: テーブルID（project.dataset.table）
            column_name: 更新するカラム名
            value: 設定する値
            where_clause: WHERE句の条件（例："id = 123"）
        """
        full_table_id = f"{self.project_id}.{self.dataset_id}.{table_id}"

        # 値がNULL場合の処理
        if value is None:
            value_str = "NULL"
        elif isinstance(value, str):
            value_str = f"'{value}'"
        else:
            value_str = str(value)

        query = f"""
        UPDATE {full_table_id}
        SET {column_name} = {value_str}
        WHERE {where_clause}
        """

        try:
            self.execute_query(query)
            logger.info(f"Updated {column_name} in {table_id}")
        except Exception as e:
            logger.error(f"Update failed: {e}")
            raise
