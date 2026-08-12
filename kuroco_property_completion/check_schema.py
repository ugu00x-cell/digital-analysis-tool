"""BigQuery テーブルスキーマ確認スクリプト"""

import logging
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_table_schema(project_id: str, dataset_id: str, table_name: str):
    """
    テーブルのスキーマを確認・表示

    Args:
        project_id: GCP プロジェクトID
        dataset_id: データセットID
        table_name: テーブル名
    """
    client = bigquery.Client(project=project_id)
    table_id = f"{project_id}.{dataset_id}.{table_name}"

    try:
        table = client.get_table(table_id)
        print(f"\n{'='*70}")
        print(f"Table: {table_id}")
        print(f"Rows: {table.num_rows}")
        print(f"{'='*70}\n")

        print(f"{'Column Name':<30} {'Type':<15} {'Nullable':<10}")
        print("-" * 55)

        for field in table.schema:
            print(f"{field.name:<30} {field.field_type:<15} {'✓' if field.is_nullable else '✗':<10}")

        print(f"\n{'='*70}")

    except Exception as e:
        logger.error(f"Failed to get schema: {e}")
        raise


def check_zipcode_master_schema(project_id: str, dataset_id: str):
    """zipcode_master テーブルのスキーマ確認"""
    print("\n\n📋 Checking zipcode_master schema:")
    try:
        check_table_schema(project_id, dataset_id, "zipcode_master")
    except Exception as e:
        print(f"⚠️  zipcode_master not found or error: {e}")


def check_research_results_schema(project_id: str, dataset_id: str):
    """research_results テーブルのスキーマ確認"""
    print("\n\n📋 Checking research_results schema:")
    try:
        check_table_schema(project_id, dataset_id, "research_results")
    except Exception as e:
        print(f"⚠️  research_results not found or error: {e}")


def main():
    project_id = "dj-ga4"
    dataset_id = "scd"

    print("\n🔍 BigQuery Table Schema Checker\n")

    try:
        check_research_results_schema(project_id, dataset_id)
        check_zipcode_master_schema(project_id, dataset_id)

    except Exception as e:
        logger.error(f"Fatal error: {e}")


if __name__ == "__main__":
    main()
