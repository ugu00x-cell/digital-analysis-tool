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
    """テスト用にOrderを簡潔に作る（A単独、Bは0）。"""
    return Order(
        row_index=idx,
        ordered_at=ordered_at,
        product=product,
        unit_price_a=unit_price,
        quantity_a=quantity,
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


# --- 境界値: 日付差が許容値ちょうど（±3日）と、その外側（±4日） ---
@pytest.mark.parametrize(
    "tx_date,expected_label",
    [
        # ちょうど+3日: マッチする
        (date(2026, 3, 28), config.STATUS_MATCHED),
        # ちょうど-3日: マッチする（対称モード時）
        (date(2026, 3, 22), config.STATUS_MATCHED),
        # +4日: マッチしない → 要確認
        (date(2026, 3, 29), config.STATUS_SUSPICIOUS),
    ],
)
def test_date_tolerance_boundary(tx_date: date, expected_label: str) -> None:
    """日付の±3日許容の境界値で挙動が切り替わることを確認する。"""
    # このテストは対称マッチ前提で設計されている
    assert config.USE_SYMMETRIC_DATE_MATCH is True
    assert config.DATE_TOLERANCE_DAYS == 3

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


# --- Stage 3: マイナス差許容マッチのテスト ---
def test_negative_diff_tolerance_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    """JCB金額が発注表より50円少ない場合、マイナス差許容で消込される。"""
    # 設定で Stage 3 を有効化
    monkeypatch.setattr(config, "ENABLE_NEGATIVE_DIFF_TOLERANCE", True)
    # 発注 1500円、JCB 1450円 (-50円差)
    tx = _tx(0, date(2026, 3, 25), 1450)
    order = _order(0, date(2026, 3, 25), 500, 3, 1500)

    results = match_transactions([tx], [order])

    assert len(results) == 1
    assert results[0].status_label == config.STATUS_MATCHED_TOLERANCE
    assert "マイナス差 -50円" in results[0].note


def test_plus_diff_not_matched(monkeypatch: pytest.MonkeyPatch) -> None:
    """JCB金額が発注表より多い場合（プラス差）は消込されない（要確認/グレー or ペア候補）。"""
    # ペアマッチも無効化して、純粋に要確認/グレーに落ちることを確認
    monkeypatch.setattr(config, "ENABLE_PAIR_MATCHING", False)

    tx = _tx(0, date(2026, 3, 25), 1550)
    order = _order(0, date(2026, 3, 25), 500, 3, 1500)

    results = match_transactions([tx], [order])

    statuses = sorted(r.status_label for r in results)
    assert config.STATUS_SUSPICIOUS in statuses
    assert config.STATUS_GRAY in statuses


def test_negative_diff_over_100_not_matched(monkeypatch: pytest.MonkeyPatch) -> None:
    """マイナス差が100円超の場合は許容しない＝要確認/グレーになる。"""
    monkeypatch.setattr(config, "ENABLE_PAIR_MATCHING", False)

    tx = _tx(0, date(2026, 3, 25), 1399)
    order = _order(0, date(2026, 3, 25), 500, 3, 1500)

    results = match_transactions([tx], [order])

    statuses = sorted(r.status_label for r in results)
    assert config.STATUS_SUSPICIOUS in statuses
    assert config.STATUS_GRAY in statuses


def test_negative_diff_boundary_minus_100(monkeypatch: pytest.MonkeyPatch) -> None:
    """マイナス差ちょうど -100円 は許容範囲内（境界値）。"""
    monkeypatch.setattr(config, "ENABLE_NEGATIVE_DIFF_TOLERANCE", True)
    tx = _tx(0, date(2026, 3, 25), 1400)
    order = _order(0, date(2026, 3, 25), 500, 3, 1500)

    results = match_transactions([tx], [order])

    assert len(results) == 1
    assert results[0].status_label == config.STATUS_MATCHED_TOLERANCE


def test_negative_diff_disabled_via_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """設定で許容を無効化したらマイナス差マッチしない（要確認になる）。"""
    monkeypatch.setattr(config, "ENABLE_NEGATIVE_DIFF_TOLERANCE", False)
    # ペアマッチも無効化（純粋に Stage 3 の動作確認のため）
    monkeypatch.setattr(config, "ENABLE_PAIR_MATCHING", False)

    tx = _tx(0, date(2026, 3, 25), 1450)
    order = _order(0, date(2026, 3, 25), 500, 3, 1500)

    results = match_transactions([tx], [order])

    statuses = sorted(r.status_label for r in results)
    assert config.STATUS_SUSPICIOUS in statuses
    assert config.STATUS_MATCHED_TOLERANCE not in statuses


def test_pair_candidate_matches_on_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    """完全一致もマイナス差許容も無理だが、ペア候補として紐付く（プラス差±200円）。"""
    monkeypatch.setattr(config, "ENABLE_NEGATIVE_DIFF_TOLERANCE", False)

    # JCB 1700円 vs 発注 1500円 → +200円差（マイナス差許容では救えない）
    tx = _tx(0, date(2026, 3, 25), 1700)
    order = _order(0, date(2026, 3, 25), 500, 3, 1500)

    results = match_transactions([tx], [order])

    # 1件のペア候補として表現される（要確認・グレーは別個に出ない）
    assert len(results) == 1
    assert results[0].status_label == config.STATUS_PAIR_CANDIDATE
    assert "+200円" in results[0].note


def test_pair_candidate_disabled_via_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """ENABLE_PAIR_MATCHING=False ならペア候補化されず、要確認・グレーが別個に出る。"""
    monkeypatch.setattr(config, "ENABLE_NEGATIVE_DIFF_TOLERANCE", False)
    monkeypatch.setattr(config, "ENABLE_PAIR_MATCHING", False)

    tx = _tx(0, date(2026, 3, 25), 1700)
    order = _order(0, date(2026, 3, 25), 500, 3, 1500)

    results = match_transactions([tx], [order])

    statuses = sorted(r.status_label for r in results)
    assert config.STATUS_SUSPICIOUS in statuses
    assert config.STATUS_GRAY in statuses
    assert config.STATUS_PAIR_CANDIDATE not in statuses


def test_pair_excluded_when_diff_too_large(monkeypatch: pytest.MonkeyPatch) -> None:
    """PAIR_MAX_ABS_DIFF を超える差はペア候補にならない。"""
    monkeypatch.setattr(config, "ENABLE_NEGATIVE_DIFF_TOLERANCE", False)
    monkeypatch.setattr(config, "PAIR_MAX_ABS_DIFF", 200)

    # 差 +501円 → 上限200を超える
    tx = _tx(0, date(2026, 3, 25), 2001)
    order = _order(0, date(2026, 3, 25), 500, 3, 1500)

    results = match_transactions([tx], [order])

    statuses = sorted(r.status_label for r in results)
    # ペアにならず、別個に要確認・グレー
    assert config.STATUS_PAIR_CANDIDATE not in statuses
    assert config.STATUS_SUSPICIOUS in statuses
    assert config.STATUS_GRAY in statuses


def test_pair_one_to_one_uses_each_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """1つのJCBは1つの発注としかペアリングされない（1対1）。"""
    monkeypatch.setattr(config, "ENABLE_NEGATIVE_DIFF_TOLERANCE", False)

    tx = _tx(0, date(2026, 3, 25), 1700)
    order_a = _order(0, date(2026, 3, 25), 500, 3, 1500)
    order_b = _order(1, date(2026, 3, 25), 500, 3, 1500)

    results = match_transactions([tx], [order_a, order_b])

    pair_results = [r for r in results
                    if r.status_label == config.STATUS_PAIR_CANDIDATE]
    gray_results = [r for r in results if r.status_label == config.STATUS_GRAY]
    # 1件だけペア・もう1件はグレー
    assert len(pair_results) == 1
    assert len(gray_results) == 1


def test_exact_match_preferred_over_tolerance() -> None:
    """完全一致が可能なら、マイナス差許容より優先される。"""
    tx_exact = _tx(0, date(2026, 3, 25), 1500)  # 完全一致候補
    tx_tolerance = _tx(1, date(2026, 3, 25), 1450)  # マイナス差候補
    order = _order(0, date(2026, 3, 25), 500, 3, 1500)

    # 1つの発注に対し2つのTXが来る
    results = match_transactions([tx_exact, tx_tolerance], [order])

    matched_exact = [r for r in results
                     if r.status_label == config.STATUS_MATCHED]
    sus = [r for r in results if r.status_label == config.STATUS_SUSPICIOUS]
    assert len(matched_exact) == 1
    assert matched_exact[0].transaction == tx_exact
    # tx_tolerance は要確認に落ちる
    assert len(sus) == 1
    assert sus[0].transaction == tx_tolerance
