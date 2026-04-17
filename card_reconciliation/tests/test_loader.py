"""loader モジュールのテスト（CSV読み込みの健全性確認）。"""
from __future__ import annotations

from pathlib import Path

import pytest

from card_reconciliation.services.loader import load_bakuraku_csv, load_order_csv


# --- バク楽CSVの読み込み ---
def test_load_bakuraku_filters_non_confirmed(tmp_path: Path) -> None:
    """「確定」以外のステータス行は除外されることを確認する。"""
    csv_path = tmp_path / "bakuraku.csv"
    csv_path.write_text(
        "利用日時,金額,当初取引内容,ステータス\n"
        "2026-03-26 10:00:00,1500,AMAZON CO JP,確定\n"
        "2026-03-27 10:00:00,3000,AMAZON CO JP,返品\n"
        "2026-03-28 10:00:00,2000,SOUNDHOUSE,確定\n",
        encoding="utf-8-sig",
    )

    txs = load_bakuraku_csv(csv_path)

    assert len(txs) == 2
    assert txs[0].amount == 1500
    assert txs[1].store == "SOUNDHOUSE"


def test_load_bakuraku_handles_amount_with_comma(tmp_path: Path) -> None:
    """金額にカンマや円記号が入っていても数値化できる。"""
    csv_path = tmp_path / "bakuraku.csv"
    csv_path.write_text(
        "利用日時,金額,当初取引内容,ステータス\n"
        "2026-03-26 10:00:00,\"1,500\",AMAZON CO JP,確定\n"
        "2026-03-27 10:00:00,¥2000,AMAZON CO JP,確定\n",
        encoding="utf-8-sig",
    )

    txs = load_bakuraku_csv(csv_path)

    assert len(txs) == 2
    assert txs[0].amount == 1500
    assert txs[1].amount == 2000


def test_load_bakuraku_missing_column_raises(tmp_path: Path) -> None:
    """必要な列が欠けているとKeyErrorが出る。"""
    csv_path = tmp_path / "bakuraku.csv"
    # 「ステータス」列を意図的に欠落
    csv_path.write_text(
        "利用日時,金額,当初取引内容\n"
        "2026-03-26 10:00:00,1500,AMAZON CO JP\n",
        encoding="utf-8-sig",
    )

    with pytest.raises(KeyError):
        load_bakuraku_csv(csv_path)


# --- 発注表CSVの読み込み ---
def test_load_order_basic(tmp_path: Path) -> None:
    """発注表CSVが正しく読み込まれ、再計算プロパティも計算できる。"""
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text(
        "注文日,商品名A,仕入れ値A,個数,仕入れ総額\n"
        "2026-03-25,テスト商品,500,3,1500\n",
        encoding="utf-8-sig",
    )

    orders = load_order_csv(csv_path)

    assert len(orders) == 1
    order = orders[0]
    assert order.unit_price == 500
    assert order.quantity == 3
    assert order.total == 1500
    assert order.recalculated_total == 1500


def test_load_order_skips_broken_row(tmp_path: Path) -> None:
    """数値化できない壊れた行はスキップされ、他の行は読める。"""
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text(
        "注文日,商品名A,仕入れ値A,個数,仕入れ総額\n"
        "2026-03-25,OK商品,500,3,1500\n"
        "2026-03-26,壊れた,abc,3,1500\n",
        encoding="utf-8-sig",
    )

    orders = load_order_csv(csv_path)

    assert len(orders) == 1
    assert orders[0].product == "OK商品"
