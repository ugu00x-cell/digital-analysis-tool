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

    AとBの2種類の仕入れ先をセットで記録できる（竹中さん発注表のA/B構造に対応）。
    Bが無い単純な注文の場合は unit_price_b=0, quantity_b=0 のまま使う。

    Attributes:
        row_index: 元CSVの行番号（トレース用）
        ordered_at: 注文日
        product: 商品名
        unit_price_a: A仕入れ値（単価）
        quantity_a: A個数
        total: 仕入れ総額（手打ち値・A+B合算）
        unit_price_b: B仕入れ値（単価・B仕入れが無ければ0）
        quantity_b: B個数（B仕入れが無ければ0）
    """

    row_index: int
    ordered_at: date
    product: str
    unit_price_a: int
    quantity_a: int
    total: int
    unit_price_b: int = 0
    quantity_b: int = 0

    @property
    def recalculated_total(self) -> int:
        """
        単価×個数で再計算した金額（手打ちミス検出用）。
        (A仕入れ値 × A個数) + (B仕入れ値 × B個数) を返す。
        """
        return (self.unit_price_a * self.quantity_a) + (
            self.unit_price_b * self.quantity_b
        )


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
