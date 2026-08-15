"""Excelファイル読み込み・クレンジング・テキスト化モジュール

3種類の保全系Excel（保全記録・点検日報・トラブル履歴）を読み込み、
RAG投入用の LangChain Document リストに変換する。

処理内容:
    - 欠損値の補完（空欄/NaN → 「記録なし」）
    - 表記ゆれの統一（synonyms.json で管理）
    - 各行を1ドキュメントとしてテキスト化（メタデータ付き）

実行例:
    from src.excel_parser import parse_all
    docs = parse_all(Path("data/raw"))
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

import pandas as pd
from langchain_core.documents import Document

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

MISSING_VALUE = "記録なし"
SYNONYMS_PATH = Path(__file__).resolve().parent / "synonyms.json"


def load_synonyms(path: Path = SYNONYMS_PATH) -> dict[str, list[str]]:
    """表記ゆれ辞書をJSONから読み込む。

    Args:
        path: 辞書ファイルパス

    Returns:
        {統一後表記: [置換対象リスト]} の辞書（コメントキーは除外）

    Raises:
        FileNotFoundError: 辞書ファイルが存在しない場合
    """
    if not path.exists():
        raise FileNotFoundError(f"表記ゆれ辞書が見つかりません: {path}")
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    # アンダースコア始まりのキー（コメント）は除外
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def normalize_text(text: str, synonyms: dict[str, list[str]]) -> str:
    """テキスト中の表記ゆれを統一表記に置換する。

    Args:
        text: 入力テキスト
        synonyms: 表記ゆれ辞書

    Returns:
        統一表記に置換されたテキスト
    """
    if not isinstance(text, str):
        return text
    result = text
    for canonical, variants in synonyms.items():
        for v in variants:
            if v and v != canonical:
                result = result.replace(v, canonical)
    return result


def fill_missing(value: object) -> str:
    """欠損値を統一表記「記録なし」で補完する。

    Args:
        value: セル値

    Returns:
        欠損なら MISSING_VALUE、それ以外は文字列化した値
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return MISSING_VALUE
    s = str(value).strip()
    return s if s else MISSING_VALUE


def _row_to_maintenance_text(row: pd.Series) -> str:
    """保全記録1行を仕様書フォーマットのテキストに整形する。"""
    return (
        f"【保全記録】{fill_missing(row.get('date'))} "
        f"/ 設備：{fill_missing(row.get('machine_id'))} "
        f"/ 担当：{fill_missing(row.get('operator'))}\n"
        f"作業内容：{fill_missing(row.get('work_content'))}\n"
        f"交換部品：{fill_missing(row.get('parts_replaced'))} "
        f"/ 作業時間：{fill_missing(row.get('work_hours'))} "
        f"/ 結果：{fill_missing(row.get('result'))}"
    )


def _row_to_inspection_text(row: pd.Series) -> str:
    """点検日報1行を仕様書フォーマットのテキストに整形する。"""
    return (
        f"【点検日報】{fill_missing(row.get('date'))} "
        f"/ 設備：{fill_missing(row.get('machine_id'))} "
        f"/ 点検者：{fill_missing(row.get('inspector'))}\n"
        f"点検項目：{fill_missing(row.get('check_item'))} "
        f"/ 結果：{fill_missing(row.get('result'))}\n"
        f"異常内容：{fill_missing(row.get('abnormality'))} "
        f"/ 処置：{fill_missing(row.get('action_taken'))}"
    )


def _row_to_trouble_text(row: pd.Series) -> str:
    """トラブル履歴1行を仕様書フォーマットのテキストに整形する。"""
    return (
        f"【トラブル履歴】{fill_missing(row.get('occurred_at'))} "
        f"/ 設備：{fill_missing(row.get('machine_id'))}\n"
        f"症状：{fill_missing(row.get('symptom'))}\n"
        f"原因：{fill_missing(row.get('cause'))} "
        f"/ 対処：{fill_missing(row.get('action'))}\n"
        f"停止時間：{fill_missing(row.get('downtime_hours'))} "
        f"/ 再発防止：{fill_missing(row.get('recurrence_prevention'))}"
    )


# ソース種別 → (テキスト整形関数, 日付カラム名)
_SOURCE_HANDLERS: dict[str, tuple[Callable[[pd.Series], str], str]] = {
    "保全記録": (_row_to_maintenance_text, "date"),
    "点検日報": (_row_to_inspection_text, "date"),
    "トラブル履歴": (_row_to_trouble_text, "occurred_at"),
}


def _df_to_documents(
    df: pd.DataFrame,
    source: str,
    synonyms: dict[str, list[str]],
) -> list[Document]:
    """DataFrame を Document リストに変換する。

    Args:
        df: 入力DataFrame
        source: ソース種別（保全記録/点検日報/トラブル履歴）
        synonyms: 表記ゆれ辞書

    Returns:
        Document のリスト（page_content とメタデータ付き）

    Raises:
        ValueError: 未知のソース種別が指定された場合
    """
    if source not in _SOURCE_HANDLERS:
        raise ValueError(f"未知のソース種別です: {source}")
    formatter, date_col = _SOURCE_HANDLERS[source]
    docs: list[Document] = []
    for _, row in df.iterrows():
        text = normalize_text(formatter(row), synonyms)
        metadata = {
            "source": source,
            "machine_id": fill_missing(row.get("machine_id")),
            "date": fill_missing(row.get(date_col)),
        }
        docs.append(Document(page_content=text, metadata=metadata))
    return docs


def parse_excel(
    path: Path,
    source: str,
    synonyms: dict[str, list[str]] | None = None,
) -> list[Document]:
    """単一のExcelファイルを Document リストに変換する。

    Args:
        path: Excelファイルパス
        source: ソース種別（保全記録/点検日報/トラブル履歴）
        synonyms: 表記ゆれ辞書。Noneの場合は既定の synonyms.json を読み込む。

    Returns:
        Document のリスト

    Raises:
        FileNotFoundError: Excelファイルが存在しない場合
    """
    if not path.exists():
        raise FileNotFoundError(f"Excelファイルが見つかりません: {path}")
    syn = synonyms if synonyms is not None else load_synonyms()
    df = pd.read_excel(path, engine="openpyxl")
    docs = _df_to_documents(df, source, syn)
    logger.info("%s を %d ドキュメントに変換 (%s)", path.name, len(docs), source)
    return docs


def parse_all(raw_dir: Path) -> list[Document]:
    """raw_dir 配下の3ファイルをまとめて Document リストに変換する。

    Args:
        raw_dir: 生データディレクトリ（maintenance_logs.xlsx など）

    Returns:
        全ドキュメントの結合リスト
    """
    synonyms = load_synonyms()
    mapping = [
        ("maintenance_logs.xlsx",  "保全記録"),
        ("inspection_reports.xlsx", "点検日報"),
        ("trouble_history.xlsx",    "トラブル履歴"),
    ]
    all_docs: list[Document] = []
    for filename, source in mapping:
        path = raw_dir / filename
        all_docs.extend(parse_excel(path, source, synonyms))
    logger.info("総ドキュメント数: %d", len(all_docs))
    return all_docs


if __name__ == "__main__":
    raw = Path(__file__).resolve().parent.parent / "data" / "raw"
    docs = parse_all(raw)
    logger.info("先頭ドキュメント例:\n%s", docs[0].page_content)
    logger.info("メタデータ例: %s", docs[0].metadata)
