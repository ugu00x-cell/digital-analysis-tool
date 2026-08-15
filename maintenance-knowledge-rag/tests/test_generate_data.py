"""generate_data.py のテスト。"""

from __future__ import annotations

import random
from pathlib import Path

import pandas as pd
import pytest

from src.generate_data import (
    GenerationConfig,
    MACHINE_IDS,
    generate_inspection_reports,
    generate_maintenance_logs,
    generate_trouble_history,
    save_to_excel,
)


@pytest.fixture
def rng() -> random.Random:
    """再現性のある乱数生成器を返す。"""
    return random.Random(0)


# ---- 正常系 ----

def test_maintenance_logs_basic_columns(rng: random.Random) -> None:
    """保全記録：必要カラムと件数が正しく出力されること。"""
    df = generate_maintenance_logs(50, rng)
    expected = {"date", "machine_id", "operator", "work_content",
                "parts_replaced", "work_hours", "result"}
    assert set(df.columns) == expected
    assert len(df) == 50
    assert df["machine_id"].isin(MACHINE_IDS).all()


def test_trouble_history_default_count_matches_spec(rng: random.Random) -> None:
    """トラブル履歴：仕様書のデフォルト100件で出力されること。"""
    df = generate_trouble_history(100, rng)
    assert len(df) == 100
    assert df["occurred_at"].str.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}").all()


# ---- 異常系 ----

def test_maintenance_logs_zero_count_raises(rng: random.Random) -> None:
    """保全記録：count=0 は ValueError。"""
    with pytest.raises(ValueError):
        generate_maintenance_logs(0, rng)


def test_inspection_reports_negative_count_raises(rng: random.Random) -> None:
    """点検日報：負の件数は ValueError。"""
    with pytest.raises(ValueError):
        generate_inspection_reports(-1, rng)


# ---- 境界値 ----

def test_inspection_reports_count_one(rng: random.Random) -> None:
    """点検日報：1件のみ生成できること（境界値）。"""
    df = generate_inspection_reports(1, rng)
    assert len(df) == 1
    assert df.iloc[0]["result"] in {"正常", "異常"}


# ---- save_to_excel ----

def test_save_to_excel_roundtrip(tmp_path: Path) -> None:
    """save_to_excel：保存→再読込で内容が一致すること。"""
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    out = tmp_path / "out.xlsx"
    save_to_excel(df, out)
    assert out.exists()
    reloaded = pd.read_excel(out)
    pd.testing.assert_frame_equal(df, reloaded)


def test_generation_config_defaults() -> None:
    """GenerationConfig：仕様書通りのデフォルト件数が設定されていること。"""
    cfg = GenerationConfig()
    assert cfg.maintenance_count == 200
    assert cfg.inspection_count == 300
    assert cfg.trouble_count == 100
