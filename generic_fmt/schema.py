"""汎用FMT（縦持ち）の列名・指標名・種類の定義。

1行に数字を1つ。項目1〜10の意味は、指標ごとに「指標定義」シートで決める。
Link up の次回予約: 項目1=店舗 / 項目2=スタッフ / 項目3=媒体 / 項目4=新規・再来 / 項目5〜10=空
kind: count（件数など）/ ratio（比率。0〜1。80% は 0.8）。BigQuery で軽くするため短い値にする。
source_file / loaded_at: 取り込み元のファイル名と取り込み日時（UTC）。
"""
from __future__ import annotations

from typing import Any

N_ITEMS = 10
BASE_COLUMNS = ["date", "company", "metric"] + [f"item{i}" for i in range(1, N_ITEMS + 1)] + ["kind", "value"]
# 取り込みの記録（どのファイルを、いつ取り込んだか）。再取り込みの洗い替えの単位に使う
COLUMNS = BASE_COLUMNS + ["source_file", "loaded_at"]

KIND_ABS = "count"
KIND_PCT = "ratio"

METRIC_VISITS = "来店客数"
METRIC_BOOKED = "次回予約数"
METRIC_NOMINATED = "指名数"
METRIC_RATE = "次回予約率"

ALL = "全体"


def make_row(date: str, company: str, metric: str, items: tuple[str, ...], kind: str,
             value: float | int) -> dict[str, Any]:
    """汎用FMTの1行を作る（項目は10個まで。足りない分は空文字で埋める）。"""
    if len(items) > N_ITEMS:
        raise ValueError(f"項目は{N_ITEMS}個までです")
    padded = list(items) + [""] * (N_ITEMS - len(items))
    row: dict[str, Any] = {"date": date, "company": company, "metric": metric}
    row.update({f"item{i + 1}": v for i, v in enumerate(padded)})
    row.update({"kind": kind, "value": value})
    return row
