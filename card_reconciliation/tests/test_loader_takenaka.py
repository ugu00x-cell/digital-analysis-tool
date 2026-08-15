"""竹中さん発注表ローダーのテスト。"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from card_reconciliation import config
from card_reconciliation.services.loader import load_takenaka_order_csv


def _takenaka_header() -> str:
    """竹中さん発注表の最小ヘッダ行を組み立てる。"""
    cols = [
        config.TAKENAKA_COL_DATE,
        config.TAKENAKA_COL_PRODUCT,
        config.TAKENAKA_COL_STATUS,
        config.TAKENAKA_COL_UNIT_PRICE_A,
        config.TAKENAKA_COL_QUANTITY_A,
        config.TAKENAKA_COL_UNIT_PRICE_B,
        config.TAKENAKA_COL_QUANTITY_B,
        config.TAKENAKA_COL_TOTAL,
    ]
    return ",".join(cols) + "\n"


# --- 正常系1: A単独注文 ---
def test_takenaka_a_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A仕入れのみの注文（Bは空欄）が読み込めること。"""
    monkeypatch.setattr(config, "DEFAULT_YEAR", 2026)

    csv_path = tmp_path / "takenaka.csv"
    csv_path.write_text(
        _takenaka_header() + "3/2,商品X,スマート配送 発送済み,500,3,,,1500\n",
        encoding="utf-8-sig",
    )

    orders = load_takenaka_order_csv(csv_path)

    assert len(orders) == 1
    o = orders[0]
    assert o.ordered_at == date(2026, 3, 2)
    assert o.product == "商品X"
    assert o.unit_price_a == 500
    assert o.quantity_a == 3
    assert o.unit_price_b == 0
    assert o.quantity_b == 0
    assert o.total == 1500
    assert o.recalculated_total == 1500


# --- 正常系2: A+Bセット注文 ---
def test_takenaka_a_and_b(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A+Bの両方がある場合に合算された再計算値になる。"""
    monkeypatch.setattr(config, "DEFAULT_YEAR", 2026)

    csv_path = tmp_path / "takenaka.csv"
    # A: 500×3=1500, B: 200×2=400, total=1900
    csv_path.write_text(
        _takenaka_header() + "3/5,セット商品,スマート配送 発送済み,500,3,200,2,1900\n",
        encoding="utf-8-sig",
    )

    orders = load_takenaka_order_csv(csv_path)

    assert len(orders) == 1
    o = orders[0]
    assert o.recalculated_total == 1900  # 500×3 + 200×2


# --- 異常系1: キャンセルステータスは除外 ---
def test_takenaka_skips_cancelled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """発送済み系以外のステータスはスキップされる。"""
    monkeypatch.setattr(config, "DEFAULT_YEAR", 2026)

    csv_path = tmp_path / "takenaka.csv"
    csv_path.write_text(
        _takenaka_header()
        + "3/2,OK商品,スマート配送 発送済み,500,1,,,500\n"
        + "3/3,キャンセル商品,注文前キャンセル（出品者都合　在庫切れ）,500,1,,,500\n",
        encoding="utf-8-sig",
    )

    orders = load_takenaka_order_csv(csv_path)

    assert len(orders) == 1
    assert orders[0].product == "OK商品"


# --- 異常系2: 壊れた金額はスキップ ---
def test_takenaka_skips_broken_amount(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """数値化できない仕入れ総額はスキップされる。"""
    monkeypatch.setattr(config, "DEFAULT_YEAR", 2026)

    csv_path = tmp_path / "takenaka.csv"
    csv_path.write_text(
        _takenaka_header()
        + "3/2,OK商品,スマート配送 発送済み,500,1,,,500\n"
        + "3/3,壊れた,スマート配送 発送済み,abc,1,,,xyz\n",
        encoding="utf-8-sig",
    )

    orders = load_takenaka_order_csv(csv_path)

    assert len(orders) == 1
    assert orders[0].product == "OK商品"


# --- 境界値: 年抜き日付の補完 ---
def test_takenaka_year_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """年抜きの日付（3/2など）に DEFAULT_YEAR が補われる。"""
    monkeypatch.setattr(config, "DEFAULT_YEAR", 2025)  # 意図的に2025に

    csv_path = tmp_path / "takenaka.csv"
    csv_path.write_text(
        _takenaka_header() + "3/2,商品,スマート配送 発送済み,500,1,,,500\n",
        encoding="utf-8-sig",
    )

    orders = load_takenaka_order_csv(csv_path)

    assert orders[0].ordered_at == date(2025, 3, 2)


# --- 列欠落はKeyError ---
def test_takenaka_missing_column_raises(tmp_path: Path) -> None:
    """必要な列が無ければKeyError。"""
    csv_path = tmp_path / "takenaka.csv"
    # ステータス列を意図的に欠落
    csv_path.write_text(
        "注文日,商品名,A仕入れ値,A個数,B仕入れ値,B個数,仕入れ総額\n"
        + "3/2,商品,500,1,,,500\n",
        encoding="utf-8-sig",
    )

    with pytest.raises(KeyError):
        load_takenaka_order_csv(csv_path)
