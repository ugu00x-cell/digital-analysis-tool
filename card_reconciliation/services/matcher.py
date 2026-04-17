"""
2段階マッチングで消込を行うモジュール。

処理の流れ：
  ① 仕入れ総額（手打ち値）と利用金額で突き合わせ
  ② ①でダメなら、単価×個数で再計算した金額で突き合わせ
  ③ それでもダメなら、バク楽側は「要確認」

マッチ済みの発注は二度使わない（1対1マッチング）。
"""
from __future__ import annotations

import logging
from datetime import date

from card_reconciliation import config
from card_reconciliation.models.transaction import MatchResult, Order, Transaction

logger = logging.getLogger(__name__)


def _is_date_within_tolerance(tx_date: date, order_date: date) -> bool:
    """
    バク楽の利用日と発注日が許容範囲内かを判定する。

    config.USE_SYMMETRIC_DATE_MATCH が True なら左右対称（±）、
    False なら「発注日 ≤ 利用日 ≤ 発注日+tolerance」の片側のみ。
    """
    diff_days = (tx_date - order_date).days

    if config.USE_SYMMETRIC_DATE_MATCH:
        return abs(diff_days) <= config.DATE_TOLERANCE_DAYS

    # 発注→請求のラグを前提にした片側マッチ
    return 0 <= diff_days <= config.DATE_TOLERANCE_DAYS


def _is_amount_match(tx_amount: int, order_amount: int) -> bool:
    """金額が許容誤差以内で一致しているかを判定する。"""
    return abs(tx_amount - order_amount) <= config.AMOUNT_TOLERANCE


def _find_matching_order(
    tx: Transaction,
    orders: list[Order],
    used_ids: set[int],
    use_recalculated: bool,
) -> Order | None:
    """
    1件のクレカ明細に対してマッチする発注を探す。

    Args:
        tx: 対象のクレカ明細
        orders: 発注のリスト
        used_ids: 既にマッチ済みの Order.row_index の集合（再利用防止）
        use_recalculated: True なら単価×個数の再計算値で突き合わせる

    Returns:
        マッチした Order。無ければ None。
    """
    for order in orders:
        # 既にマッチ済みの発注は使わない（1対1）
        if order.row_index in used_ids:
            continue

        order_amount = order.recalculated_total if use_recalculated else order.total

        if not _is_amount_match(tx.amount, order_amount):
            continue
        if not _is_date_within_tolerance(tx.used_at, order.ordered_at):
            continue

        return order

    return None


def match_transactions(
    transactions: list[Transaction],
    orders: list[Order],
) -> list[MatchResult]:
    """
    バク楽明細と発注表を突き合わせて消込結果を返す。

    処理順：
      1. 全バク楽明細について、まず仕入れ総額（手打ち値）でマッチを試みる
      2. ダメだったものは、単価×個数の再計算値で再度マッチを試みる
      3. それでもダメなら「要確認（不正疑い）」
      4. 最後に、消し込まれなかった発注を「グレー」として結果に追加

    Args:
        transactions: バク楽の確定明細リスト
        orders: 発注表の行リスト

    Returns:
        MatchResult のリスト（バク楽全件 + 未消込の発注）
    """
    used_order_ids: set[int] = set()
    results: list[MatchResult] = []
    unresolved: list[Transaction] = []

    # ① 手打ち値（仕入れ総額）でマッチ
    for tx in transactions:
        order = _find_matching_order(tx, orders, used_order_ids, use_recalculated=False)
        if order is not None:
            used_order_ids.add(order.row_index)
            results.append(
                MatchResult(transaction=tx, order=order, status_label=config.STATUS_MATCHED)
            )
        else:
            unresolved.append(tx)

    # ② 再計算値（単価×個数）でマッチ
    still_unresolved: list[Transaction] = []
    for tx in unresolved:
        order = _find_matching_order(tx, orders, used_order_ids, use_recalculated=True)
        if order is not None:
            used_order_ids.add(order.row_index)
            diff = order.total - order.recalculated_total
            note = f"仕入れ総額の手打ち差額: {diff:+,}円"
            results.append(
                MatchResult(
                    transaction=tx,
                    order=order,
                    status_label=config.STATUS_MATCHED_RECALC,
                    note=note,
                )
            )
        else:
            still_unresolved.append(tx)

    # ③ それでもマッチしなかったバク楽明細は「要確認」
    for tx in still_unresolved:
        results.append(
            MatchResult(
                transaction=tx,
                order=None,
                status_label=config.STATUS_SUSPICIOUS,
                note="発注表に該当無し（担当者の不正 or 別セラー）",
            )
        )

    # ④ 消し込まれなかった発注は「グレー」として追加
    for order in orders:
        if order.row_index in used_order_ids:
            continue
        results.append(
            MatchResult(
                transaction=None,
                order=order,
                status_label=config.STATUS_GRAY,
                note="クレカ明細に該当無し（別セラー購入の可能性）",
            )
        )

    logger.info(
        "マッチング完了: 消込%d / 再計算%d / 要確認%d / グレー%d",
        sum(1 for r in results if r.status_label == config.STATUS_MATCHED),
        sum(1 for r in results if r.status_label == config.STATUS_MATCHED_RECALC),
        sum(1 for r in results if r.status_label == config.STATUS_SUSPICIOUS),
        sum(1 for r in results if r.status_label == config.STATUS_GRAY),
    )
    return results
