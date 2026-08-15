"""
3段階マッチングで消込を行うモジュール。

処理の流れ：
  ① 仕入れ総額（手打ち値）と利用金額で完全一致マッチ
  ② ①でダメなら、単価×個数で再計算した金額で完全一致マッチ（手打ちミス検出）
  ③ ②でもダメなら、マイナス差（JCB < 発注表）で 1〜100円 のみ許容してマッチ
     （業務上の「未修正残」許容範囲）
     プラス差は許容しない（プロセス上ありえない＝担当ミス候補）
  ④ それでもダメなら、明細側は「要確認」、発注表側は「グレー」

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


def _find_best_pair_candidate(
    tx: Transaction,
    orders: list[Order],
    used_ids: set[int],
) -> tuple[Order, int] | None:
    """
    要確認JCBに対して、未マッチ発注からベストなペア候補を探す。

    完全一致ではないが「同日近辺・金額が一定範囲内に近い」発注を
    ペア候補として紐付ける。最近傍（日付差最小→金額差絶対値最小）を選ぶ。

    Args:
        tx: 対象のクレカ明細（要確認になっているもの）
        orders: 未マッチの発注リスト（グレーになる予定のもの）
        used_ids: 既にペアリング済みの Order.row_index 集合

    Returns:
        (マッチした Order, 差額) のタプル。候補なしなら None。
    """
    best: tuple[Order, int, tuple[int, int]] | None = None
    max_abs_diff = config.PAIR_MAX_ABS_DIFF

    for order in orders:
        if order.row_index in used_ids:
            continue
        if not _is_date_within_tolerance(tx.used_at, order.ordered_at):
            continue

        diff = tx.amount - order.total
        if abs(diff) > max_abs_diff:
            continue

        # スコア: 日付差最小 → 金額差絶対値最小
        score = (abs((tx.used_at - order.ordered_at).days), abs(diff))
        if best is None or score < best[2]:
            best = (order, diff, score)

    if best is None:
        return None
    order, diff, _ = best
    return order, diff


def _find_negative_diff_match(
    tx: Transaction,
    orders: list[Order],
    used_ids: set[int],
) -> tuple[Order, int] | None:
    """
    マイナス差（JCB < 発注表）の許容範囲内でベストマッチを探す。

    プラス差（JCB > 発注表）は絶対に許容しない（プロセス上ありえないため）。
    複数候補がある場合は、日付差が最小→金額差の絶対値が最小 を優先する。

    Args:
        tx: 対象のクレカ明細
        orders: 発注のリスト
        used_ids: マッチ済みの row_index 集合

    Returns:
        (マッチした Order, 差額) のタプル。マッチなしなら None。
    """
    diff_min, diff_max = config.NEGATIVE_DIFF_TOLERANCE_RANGE
    best: tuple[Order, int, tuple[int, int]] | None = None

    for order in orders:
        if order.row_index in used_ids:
            continue
        if not _is_date_within_tolerance(tx.used_at, order.ordered_at):
            continue

        diff = tx.amount - order.total
        # マイナス差の許容範囲のみ
        if not (diff_min <= diff <= diff_max):
            continue

        # スコア: 日付差最小 → 金額差絶対値最小
        score = (abs((tx.used_at - order.ordered_at).days), abs(diff))
        if best is None or score < best[2]:
            best = (order, diff, score)

    if best is None:
        return None
    order, diff, _ = best
    return order, diff


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

    # ② 再計算値（単価×個数）でマッチ（手打ちミス検出）
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

    # ③ マイナス差許容マッチ（プロセス上の「未修正残」を吸収）
    final_unresolved: list[Transaction] = []
    if config.ENABLE_NEGATIVE_DIFF_TOLERANCE:
        for tx in still_unresolved:
            match = _find_negative_diff_match(tx, orders, used_order_ids)
            if match is not None:
                order, diff = match
                used_order_ids.add(order.row_index)
                note = f"マイナス差 {diff:+,}円（未修正残として許容）"
                results.append(
                    MatchResult(
                        transaction=tx,
                        order=order,
                        status_label=config.STATUS_MATCHED_TOLERANCE,
                        note=note,
                    )
                )
            else:
                final_unresolved.append(tx)
    else:
        final_unresolved = still_unresolved

    # ④ ペア候補マッチ：未マッチJCB ↔ 未マッチ発注 を差額付きで紐付ける
    # （完全一致ではないので消込扱いではないが、業務側の確認工数を削減）
    paired_order_ids: set[int] = set()
    truly_unresolved: list[Transaction] = []
    if config.ENABLE_PAIR_MATCHING:
        # 未マッチ発注のリスト
        unmatched_orders = [
            o for o in orders if o.row_index not in used_order_ids
        ]
        for tx in final_unresolved:
            best = _find_best_pair_candidate(tx, unmatched_orders, paired_order_ids)
            if best is not None:
                order, diff = best
                paired_order_ids.add(order.row_index)
                results.append(
                    MatchResult(
                        transaction=tx,
                        order=order,
                        status_label=config.STATUS_PAIR_CANDIDATE,
                        note=f"差額 {diff:+,}円・同日±{config.DATE_TOLERANCE_DAYS}日内のペア候補",
                    )
                )
            else:
                truly_unresolved.append(tx)
    else:
        truly_unresolved = final_unresolved

    # ⑤ それでもマッチしなかったバク楽明細は「要確認」
    for tx in truly_unresolved:
        results.append(
            MatchResult(
                transaction=tx,
                order=None,
                status_label=config.STATUS_SUSPICIOUS,
                note="発注表に該当無し（担当者の不正 or 別セラー）",
            )
        )

    # ⑥ 消し込まれず、ペアにもならなかった発注は「グレー」として追加
    for order in orders:
        if order.row_index in used_order_ids:
            continue
        if order.row_index in paired_order_ids:
            continue  # Stage 4 でペアリング済み
        results.append(
            MatchResult(
                transaction=None,
                order=order,
                status_label=config.STATUS_GRAY,
                note="クレカ明細に該当無し（別セラー購入の可能性）",
            )
        )

    logger.info(
        "マッチング完了: 消込%d / 再計算%d / マイナス差許容%d / "
        "ペア候補%d / 要確認%d / グレー%d",
        sum(1 for r in results if r.status_label == config.STATUS_MATCHED),
        sum(1 for r in results if r.status_label == config.STATUS_MATCHED_RECALC),
        sum(1 for r in results if r.status_label == config.STATUS_MATCHED_TOLERANCE),
        sum(1 for r in results if r.status_label == config.STATUS_PAIR_CANDIDATE),
        sum(1 for r in results if r.status_label == config.STATUS_SUSPICIOUS),
        sum(1 for r in results if r.status_label == config.STATUS_GRAY),
    )
    return results
