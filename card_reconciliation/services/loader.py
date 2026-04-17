"""CSVを読み込んで Transaction / Order のリストに変換するモジュール。"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from card_reconciliation import config
from card_reconciliation.models.transaction import Order, Transaction

logger = logging.getLogger(__name__)


def _to_int_amount(value: object) -> int:
    """
    金額の値（文字列や数値）を整数に変換する。

    カンマ・円記号・全角記号・空白を除去してから int に変換。
    変換できない場合は ValueError を送出。
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ValueError("金額が空です")

    text = str(value).strip()
    # カンマ・円記号（半角/全角）・通貨記号・空白を除去
    cleaned = re.sub(r"[,¥￥\s]", "", text)

    if cleaned == "" or cleaned == "-":
        raise ValueError(f"金額が不正です: {value!r}")

    try:
        return int(float(cleaned))
    except ValueError as exc:
        raise ValueError(f"金額を数値に変換できません: {value!r}") from exc


def _to_date(value: object) -> date:
    """
    日付らしき値を date 型に変換する。

    pandas の Timestamp、datetime、'YYYY-MM-DD HH:MM:SS'、'YYYY/MM/DD' 等に対応。
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ValueError("日付が空です")

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    # pandas に任せると多くのフォーマットを吸収してくれる
    try:
        return pd.to_datetime(text).date()
    except (ValueError, TypeError) as exc:
        raise ValueError(f"日付を変換できません: {value!r}") from exc


def load_bakuraku_csv(path: Path) -> list[Transaction]:
    """
    バク楽クレカ明細CSVを読み込んで Transaction のリストを返す。

    「確定」ステータスのみを対象にする（返品等は除外）。

    Args:
        path: バク楽CSVのパス

    Returns:
        確定済み Transaction のリスト

    Raises:
        FileNotFoundError: CSVが存在しない場合
        KeyError: 必要な列が無い場合
    """
    logger.info("バク楽CSVを読み込みます: %s", path)
    df = pd.read_csv(path, encoding=config.BAKURAKU_ENCODING, dtype=str)

    required = [
        config.BAKURAKU_COL_DATETIME,
        config.BAKURAKU_COL_AMOUNT,
        config.BAKURAKU_COL_STORE,
        config.BAKURAKU_COL_STATUS,
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"バク楽CSVに必要な列がありません: {missing}")

    transactions: list[Transaction] = []
    for idx, row in df.iterrows():
        status = str(row[config.BAKURAKU_COL_STATUS]).strip()
        # 確定以外や除外ステータスはスキップ
        if status != config.BAKURAKU_VALID_STATUS:
            continue
        if status in config.BAKURAKU_EXCLUDED_STATUSES:
            continue

        try:
            tx = Transaction(
                row_index=int(idx),
                used_at=_to_date(row[config.BAKURAKU_COL_DATETIME]),
                amount=_to_int_amount(row[config.BAKURAKU_COL_AMOUNT]),
                store=str(row[config.BAKURAKU_COL_STORE]).strip(),
                status=status,
            )
        except ValueError as exc:
            # 1行だけ壊れていてもスキップして続行
            logger.warning("バク楽CSV %s行目をスキップ: %s", idx, exc)
            continue
        transactions.append(tx)

    logger.info("バク楽: %d件の確定明細を読み込みました", len(transactions))
    return transactions


def _should_keep_order_row(row: pd.Series) -> bool:
    """
    発注表の1行を採用するかどうか判定する（カード・ステータスでフィルタ）。

    config.ORDER_CARD_FILTER が空文字ならカード絞り込みなし。
    config.ORDER_VALID_STATUSES が空タプルならステータス絞り込みなし。
    """
    # カード番号フィルタ（Amazon CSVは '="4521"' 形式で来るので部分一致）
    if config.ORDER_CARD_FILTER:
        card_col = config.ORDER_COL_CARD
        if card_col in row.index:
            card_value = str(row[card_col]) if row[card_col] is not None else ""
            if config.ORDER_CARD_FILTER not in card_value:
                return False

    # 注文状況フィルタ
    if config.ORDER_VALID_STATUSES:
        status_col = config.ORDER_COL_STATUS
        if status_col in row.index:
            status_value = str(row[status_col]).strip() if row[status_col] is not None else ""
            if status_value not in config.ORDER_VALID_STATUSES:
                return False

    return True


def load_order_csv(path: Path) -> list[Order]:
    """
    発注表CSVを読み込んで Order のリストを返す。

    config.ORDER_CARD_FILTER で指定されたカードのみ、
    config.ORDER_VALID_STATUSES に含まれるステータスのみを対象にする。

    Args:
        path: 発注表CSVのパス

    Returns:
        Order のリスト

    Raises:
        FileNotFoundError: CSVが存在しない場合
        KeyError: 必要な列が無い場合
    """
    logger.info("発注表CSVを読み込みます: %s", path)
    df = pd.read_csv(path, encoding=config.ORDER_ENCODING, dtype=str)

    required = [
        config.ORDER_COL_DATE,
        config.ORDER_COL_PRODUCT,
        config.ORDER_COL_UNIT_PRICE,
        config.ORDER_COL_QUANTITY,
        config.ORDER_COL_TOTAL,
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"発注表CSVに必要な列がありません: {missing}")

    orders: list[Order] = []
    skipped_filtered = 0
    for idx, row in df.iterrows():
        # カード・ステータスフィルタ
        if not _should_keep_order_row(row):
            skipped_filtered += 1
            continue

        try:
            order = Order(
                row_index=int(idx),
                ordered_at=_to_date(row[config.ORDER_COL_DATE]),
                product=str(row[config.ORDER_COL_PRODUCT]).strip(),
                unit_price=_to_int_amount(row[config.ORDER_COL_UNIT_PRICE]),
                quantity=int(_to_int_amount(row[config.ORDER_COL_QUANTITY])),
                total=_to_int_amount(row[config.ORDER_COL_TOTAL]),
            )
        except ValueError as exc:
            logger.warning("発注表CSV %s行目をスキップ: %s", idx, exc)
            continue
        orders.append(order)

    logger.info(
        "発注表: %d件の発注を読み込みました（フィルタで除外: %d件）",
        len(orders),
        skipped_filtered,
    )
    return orders
