"""excel_parser.py のテスト。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.excel_parser import (
    MISSING_VALUE,
    fill_missing,
    load_synonyms,
    normalize_text,
    parse_excel,
    parse_all,
)


# ---- normalize_text 正常系 ----

def test_normalize_text_replaces_synonyms() -> None:
    """軸受/bearing/Bearing が「ベアリング」に統一されること。"""
    syn = {"ベアリング": ["軸受", "bearing", "Bearing"]}
    assert normalize_text("軸受交換", syn) == "ベアリング交換"
    assert normalize_text("bearing wear", syn) == "ベアリング wear"
    assert normalize_text("Bearing 確認", syn) == "ベアリング 確認"


def test_normalize_text_preserves_already_canonical() -> None:
    """既に統一表記の場合はそのまま返すこと。"""
    syn = {"ベアリング": ["軸受", "bearing"]}
    assert normalize_text("ベアリング交換", syn) == "ベアリング交換"


# ---- normalize_text 異常系 / 境界値 ----

def test_normalize_text_empty_string() -> None:
    """空文字列はそのまま返すこと（境界値）。"""
    assert normalize_text("", {"a": ["b"]}) == ""


def test_normalize_text_non_string_passthrough() -> None:
    """文字列以外（数値など）はそのまま返すこと。"""
    assert normalize_text(123, {"a": ["b"]}) == 123  # type: ignore[arg-type]


# ---- fill_missing ----

def test_fill_missing_handles_nan_and_none() -> None:
    """NaN/None/空文字 が「記録なし」に補完されること。"""
    assert fill_missing(None) == MISSING_VALUE
    assert fill_missing(float("nan")) == MISSING_VALUE
    assert fill_missing("") == MISSING_VALUE
    assert fill_missing("   ") == MISSING_VALUE


def test_fill_missing_preserves_value() -> None:
    """非欠損値はそのまま文字列化されること。"""
    assert fill_missing("MC003") == "MC003"
    assert fill_missing(42) == "42"


# ---- load_synonyms ----

def test_load_synonyms_excludes_comment_keys() -> None:
    """_comment などアンダースコア始まりキーは除外されること。"""
    syn = load_synonyms()
    assert "_comment" not in syn
    assert "ベアリング" in syn


# ---- parse_excel 正常系 ----

def test_parse_excel_maintenance(tmp_path: Path) -> None:
    """保全記録Excelを Document に変換できること。"""
    df = pd.DataFrame([{
        "date": "2024-03-15", "machine_id": "MC003", "operator": "田中さん",
        "work_content": "軸受交換", "parts_replaced": "ベアリング6206",
        "work_hours": "2.5h", "result": "正常復旧",
    }])
    p = tmp_path / "m.xlsx"
    df.to_excel(p, index=False)
    docs = parse_excel(p, "保全記録")
    assert len(docs) == 1
    assert "【保全記録】" in docs[0].page_content
    # 表記ゆれ統一が効いていること
    assert "軸受交換" not in docs[0].page_content
    assert "ベアリング交換" in docs[0].page_content
    assert docs[0].metadata == {
        "source": "保全記録", "machine_id": "MC003", "date": "2024-03-15",
    }


def test_parse_excel_trouble_uses_occurred_at(tmp_path: Path) -> None:
    """トラブル履歴は occurred_at をメタデータの date に使うこと。"""
    df = pd.DataFrame([{
        "occurred_at": "2024-04-01 10:30", "machine_id": "MC005",
        "symptom": "異音発生", "cause": "ベアリング摩耗",
        "action": "交換", "downtime_hours": "3.0h",
        "recurrence_prevention": "予防交換",
    }])
    p = tmp_path / "t.xlsx"
    df.to_excel(p, index=False)
    docs = parse_excel(p, "トラブル履歴")
    assert docs[0].metadata["date"] == "2024-04-01 10:30"
    assert docs[0].metadata["source"] == "トラブル履歴"


# ---- parse_excel 異常系 ----

def test_parse_excel_missing_file(tmp_path: Path) -> None:
    """存在しないファイルは FileNotFoundError。"""
    with pytest.raises(FileNotFoundError):
        parse_excel(tmp_path / "nope.xlsx", "保全記録")


def test_parse_excel_unknown_source(tmp_path: Path) -> None:
    """未知のソース種別は ValueError。"""
    df = pd.DataFrame([{"machine_id": "MC001"}])
    p = tmp_path / "x.xlsx"
    df.to_excel(p, index=False)
    with pytest.raises(ValueError):
        parse_excel(p, "未知のソース")


# ---- 境界値: 空ファイル ----

def test_parse_excel_empty_dataframe(tmp_path: Path) -> None:
    """空のDataFrame（0行）でも空リストが返ること。"""
    df = pd.DataFrame(columns=["date", "machine_id", "operator",
                               "work_content", "parts_replaced",
                               "work_hours", "result"])
    p = tmp_path / "empty.xlsx"
    df.to_excel(p, index=False)
    docs = parse_excel(p, "保全記録")
    assert docs == []


# ---- parse_all（生成済みファイルに対する結合テスト） ----

def test_parse_all_with_generated_data() -> None:
    """生成済み3ファイルを総合的に Document に変換できること。"""
    raw = Path(__file__).resolve().parent.parent / "data" / "raw"
    if not (raw / "maintenance_logs.xlsx").exists():
        pytest.skip("合成データ未生成のためスキップ")
    docs = parse_all(raw)
    # 200 + 300 + 100 = 600件
    assert len(docs) == 600
    sources = {d.metadata["source"] for d in docs}
    assert sources == {"保全記録", "点検日報", "トラブル履歴"}
