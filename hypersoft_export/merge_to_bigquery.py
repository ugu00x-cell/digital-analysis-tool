"""ダウンロード済みハイパーソフトExcelを、Drive経由を通さず直接BigQueryへMERGEするツール

pipeline.py の process_changed_files_from_drive はDrive上の全ファイルを毎回
逐次ダウンロード・解析するため、店舗あたり数百ファイルの環境では非常に遅い。
本スクリプトは同じ変換ロジック（FileProcessor.preprocess_hypersoft / POSMapper）を
再利用しつつ、ローカルに保存済みのExcelファイルを直接読み込むことで高速化する。
"""

import logging
import sys
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

sys.path.insert(0, str(Path(r"C:\Users\ugu00\salon-dashboard\GITHUB_POS_ETL\pos_data_pipeline-main")))
from app.core.file_processor import FileProcessor  # noqa: E402
from app.mapping.mapper import POSMapper  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("merge_to_bigquery.log", encoding="utf-8"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

PROJECT_ID = "salon-dashboard-452110"
DATASET_ID = "pos_data"
TABLE_ID = "hypersoft"
CREDENTIALS_PATH = r"C:\Users\ugu00\salon-dashboard\salon-dashboard-452110-7b0302fc02e1.json"

DOWNLOAD_DIR = Path(__file__).parent / "data" / "downloaded"

# フォルダ識別子 → 実店舗名
STORE_NAME_MAP: dict[str, str] = {
    "amuse_kannai": "AMUSE関内店",
    "eye_nail_lokahi": "Eye & nail LOKAHI",
    "luna_fukasawa": "LUNA深沢店",
    "luna_ofuna": "LUNA大船店",
    "tiara_sakuragicho": "TIARA 桜木町",
    "eclart_eye_laurel_ikebukuro": "ECLART eye＆Laurel 池袋",
    "eclart_eye_laurel_nakano": "ECLART eye＆Laurel 中野",
    "eclart_eye_laurel_travel_omiya": "ECLART eye＆laurel／Travel 大宮店",
    "laurel_by_horn_sapporo": "Laurel by HORN 札幌",
    "laurel_snowdrop_ogikubo": "Laurel by Snowdrop 荻窪",
    "laurel_snowdrop_koenji": "Laurel by Snowdrop 高円寺",
    "laurel_snowdrop_kichijoji": "Laurel by Snowdrop吉祥寺",
    "laurel_eye_sakae": "LAUREL EYE 栄店",
    "laurel_eye_kokura": "LAUREL EYE 小倉店",
    "laurel_eye_kawasaki": "LAUREL EYE 川崎",
    "laurel_yeux_fujisawa": "Laurel Yeux 藤沢店",
}


def load_and_transform_store(store_dir: Path, store_name: str) -> pd.DataFrame:
    """1店舗分のExcelファイル群を読み込み、既存の変換ロジックでスキーマ整形する

    Args:
        store_dir: 店舗フォルダのパス
        store_name: 実店舗名（store_name_Whereの補完に使用）

    Returns:
        POSMapper.transformで整形済みのDataFrame（全ファイル結合済み）
    """
    mapper = POSMapper()
    dfs: list[pd.DataFrame] = []

    for xlsx_path in sorted(store_dir.glob("*.xlsx")):
        try:
            df_raw = pd.read_excel(xlsx_path)
            df_preprocessed = FileProcessor.preprocess_hypersoft(df_raw)
            df_transformed = mapper.transform(df_preprocessed, "hypersoft", store_name=store_name)
            dfs.append(df_transformed)
            logger.info(f"読み込み完了: {xlsx_path.name} ({len(df_transformed)}行)")
        except Exception as e:
            logger.error(f"読み込み失敗: {xlsx_path.name}: {e}")

    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)


def merge_dataframe_to_bigquery(client: bigquery.Client, df: pd.DataFrame) -> None:
    """DataFrameを一時テーブル経由でpos_data.hypersoftへMERGEする

    Args:
        client: BigQueryクライアント
        df: MERGE対象のDataFrame（POSMapperで整形済み）
    """
    if df.empty:
        logger.warning("MERGE対象データが空のためスキップします")
        return

    temp_table_id = f"{TABLE_ID}_local_merge_temp"
    temp_table_ref = f"{PROJECT_ID}.{DATASET_ID}.{temp_table_id}"

    def field_type(col: str) -> str:
        """列名からBigQuery型を判定（本番テーブルと同じルール）"""
        if col.endswith("_date_When"):
            return "DATE"
        if col.endswith("_time_When"):
            return "TIME"
        return "STRING"

    for col in df.columns:
        col_type = field_type(col)
        if col_type == "DATE":
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
        elif col_type == "TIME":
            df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed").dt.time
        else:
            df[col] = df[col].astype(str).where(df[col].notna(), None)

    schema = [bigquery.SchemaField(col, field_type(col)) for col in df.columns]
    job_config = bigquery.LoadJobConfig(schema=schema, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
    load_job = client.load_table_from_dataframe(df, temp_table_ref, job_config=job_config)
    load_job.result()
    logger.info(f"一時テーブルへのロード完了: {len(df)}行")

    schema_fields = list(df.columns)
    key_columns = {"visit_date_When", "transaction_id_Who"}
    update_columns = [f for f in schema_fields if f not in key_columns]
    update_set = ", ".join([f"target.{col} = source.{col}" for col in update_columns])
    insert_columns = ", ".join(schema_fields)
    insert_values = ", ".join([f"source.{col}" for col in schema_fields])

    merge_sql = f"""
    MERGE `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}` AS target
    USING `{temp_table_ref}` AS source
    ON target.visit_date_When = source.visit_date_When
       AND target.transaction_id_Who = source.transaction_id_Who
    WHEN MATCHED THEN
        UPDATE SET {update_set}
    WHEN NOT MATCHED THEN
        INSERT ({insert_columns}) VALUES ({insert_values})
    """
    client.query(merge_sql).result()
    logger.info("MERGE完了")

    client.delete_table(temp_table_ref, not_found_ok=True)


def main() -> None:
    """全店舗のダウンロード済みExcelをBigQueryへMERGEする（--storeで1店舗のみに絞り込み可能）"""
    import argparse

    parser = argparse.ArgumentParser(description="ハイパーソフトExcelをBigQueryへMERGE")
    parser.add_argument("--store", help="特定の店舗フォルダ名のみ処理する場合に指定（例: amuse_kannai）")
    args = parser.parse_args()

    client = bigquery.Client.from_service_account_json(CREDENTIALS_PATH)

    for store_dir in sorted(DOWNLOAD_DIR.iterdir()):
        if not store_dir.is_dir():
            continue
        store_key = store_dir.name
        if args.store and store_key != args.store:
            continue
        store_name = STORE_NAME_MAP.get(store_key)
        if not store_name:
            logger.warning(f"店舗名マッピングが見つかりません: {store_key}（スキップ）")
            continue

        logger.info(f"=== {store_name}（{store_key}）の処理を開始 ===")
        df = load_and_transform_store(store_dir, store_name)
        merge_dataframe_to_bigquery(client, df)
        logger.info(f"=== {store_name} 完了 ===")


if __name__ == "__main__":
    main()
