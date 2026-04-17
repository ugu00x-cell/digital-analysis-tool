"""matcher モジュールのテスト。

最低構成:
  正常系2: 手打ち値で消込 / 再計算値で消込
  異常系2: バク楽のみ（要確認）/ 発注のみ（グレー）
  境界値1: 日付の許容範囲の端（±2日）
"""
from __future__ import annotations

from datetime import date

import pytest

from card_reconciliation import config
from card_reconciliation.models.transaction import Order, Transaction
from card_reconciliation.services.matcher import match_transactions


# --- ヘルパ ---
def _tx(idx: int, used_at: date, amount: int, store: str = "AMAZON CO JP") -> Transaction:
    """テスト用にTransactionを簡潔に作る。"""
    return Transaction(
        row_index=idx,
        used_at=used_at,
        amount=amount,
        store=store,
        status="確定",
    )


def _order(
    idx: int,
    ordered_at: date,
    unit_price: int,
    quantity: int,
    total: int,
    product: str = "テスト商品",
) -> Order:
    """テスト用にOrderを簡潔に作る。"""
    return Order(
        row_index=idx,
        ordered_at=ordered_at,
        product=product,
        unit_price=unit_price,
        quantity=quantity,
        total=total,
    )


# --- 正常系1: 仕入れ総額（手打ち値）が一致 → ✅ 消込済み ---
def test_matched_by_total_amount() -> None:
    """手打ち総額とクレカ金額が一致した場合に✅消込済みになる。"""
    tx = _tx(0, date(2026, 3, 26), 1500)
    order = _order(0, date(2026, 3, 25), 500, 3, 1500)

    results = match_transactions([tx], [order])

    assert len(results) == 1
    assert results[0].status_label == config.STATUS_MATCHED
    assert results[0].order is order


# --- 正常系2: 手打ち値はズレてるが、単価×個数でなら一致 → ✅⚠️ ---
def test_matched_by_recalculated_amount() -> None:
    """手打ち総額がズレていても、単価×個数で一致すれば手打ちミス疑いで消込される。"""
    tx = _tx(0, date(2026, 3, 26), 1500)
    # 手打ち総額は間違って1400になっているが、500×3=1500で合う
    order = _order(0, date(2026, 3, 26), 500, 3, 1400)

    results = match_transactions([tx], [order])

    assert len(results) == 1
    assert results[0].status_label == config.STATUS_MATCHED_RECALC
    assert "差額" in results[0].note


# --- 異常系1: クレカにあるが発注表に無い → 🚨 要確認 ---
def test_transaction_without_order_is_suspicious() -> None:
    """クレカ明細に対応する発注が無ければ要確認扱いになる。"""
    tx = _tx(0, date(2026, 3, 26), 9999)

    results = match_transactions([tx], [])

    assert len(results) == 1
    assert results[0].status_label == config.STATUS_SUSPICIOUS


# --- 異常系2: 発注表にあるがクレカに無い → ⚠️ グレー ---
def test_order_without_transaction_is_gray() -> None:
    """発注はあるがクレカ明細に無ければグレー扱いになる。"""
    order = _order(0, date(2026, 3, 25), 500, 3, 1500)

    results = match_transactions([], [order])

    assert len(results) == 1
    assert results[0].status_label == config.STATUS_GRAY
    assert results[0].order is order


# --- 境界値: 日付差が許容値ちょうど（±2日）と、その外側（±3日） ---
@pytest.mark.parametrize(
    "tx_date,expected_label",
    [
        # ちょうど+2日: マッチする
        (date(2026, 3, 27), config.STATUS_MATCHED),
        # ちょうど-2日: マッチする（対称モード時）
        (date(2026, 3, 23), config.STATUS_MATCHED),
        # +3日: マッチしない → 要確認
        (date(2026, 3, 28), config.STATUS_SUSPICIOUS),
    ],
)
def test_date_tolerance_boundary(tx_date: date, expected_label: str) -> None:
    """日付の±2日許容の境界値で挙動が切り替わることを確認する。"""
    # このテストは対称マッチ前提で設計されている
    assert config.USE_SYMMETRIC_DATE_MATCH is True
    assert config.DATE_TOLERANCE_DAYS == 2

    tx = _tx(0, tx_date, 1500)
    order = _order(0, date(2026, 3, 25), 500, 3, 1500)

    results = match_transactions([tx], [order])

    # 要確認のときは、発注が残るのでグレーも1件付く
    labels = [r.status_label for r in results]
    assert expected_label in labels


# --- 追加: 1対1マッチング確認 ---
def test_one_to_one_matching() -> None:
    """同額の発注が2つあっても、バク楽1件は1発注としか消し込まない。"""
    tx = _tx(0, date(2026, 3, 26), 1500)
    order1 = _order(0, date(2026, 3, 25), 500, 3, 1500)
    order2 = _order(1, date(2026, 3, 25), 500, 3, 1500)

    results = match_transactions([tx], [order1, order2])

    matched = [r for r in results if r.status_label == config.STATUS_MATCHED]
    gray = [r for r in results if r.status_label == config.STATUS_GRAY]
    # 消込済みは1件、余った発注がグレーで1件
    assert len(matched) == 1
    assert len(gray) == 1
