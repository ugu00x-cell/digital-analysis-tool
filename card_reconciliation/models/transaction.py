"""消込ツールで使うデータクラス定義。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Transaction:
    """
    バク楽クレカ明細の1行分を表すデータクラス。

    Attributes:
        row_index: 元CSVの行番号（トレース用）
        used_at: 利用日時から日付部分だけ取り出したもの
        amount: 金額（円、整数）
        store: 当初取引内容（店名）
        status: ステータス（確定/返品 など）
    """

    row_index: int
    used_at: date
    amount: int
    store: str
    status: str


@dataclass
class Order:
    """
    発注表の1行分を表すデータクラス。

    Attributes:
        row_index: 元CSVの行番号（トレース用）
        ordered_at: 注文日
        product: 商品名A
        unit_price: 仕入れ値A（単価）
        quantity: 個数
        total: 仕入れ総額（手打ち値）
    """

    row_index: int
    ordered_at: date
    product: str
    unit_price: int
    quantity: int
    total: int

    @property
    def recalculated_total(self) -> int:
        """単価×個数で再計算した金額（手打ちミス検出用）。"""
        return self.unit_price * self.quantity


@dataclass
class MatchResult:
    """
    消込の1件分の結果を表すデータクラス。

    Attributes:
        transaction: 対象のクレカ明細（バク楽側。グレー時はNone）
        order: マッチした発注（無ければNone）
        status_label: 出力ステータス文言（config.STATUS_* のいずれか）
        note: 備考（手打ちミスの差額メモなど）
    """

    transaction: Optional[Transaction]
    order: Optional[Order]
    status_label: str
    note: str = ""
