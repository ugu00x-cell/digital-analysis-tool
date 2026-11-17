"""件数(count)の行から、比率(ratio)の行（次回予約率）を作る。

次回予約率 = 次回予約数 ÷ 来店客数（比率。0〜1、小数第3位まで。80% は 0.8）。
来店客数が 0 または片方がないときは行を作らない。比率(ratio)の行は表示用で、集計は件数(count)から計算し直す。
"""
from __future__ import annotations

import logging
from typing import Any

from schema import (COLUMNS, KIND_ABS, KIND_PCT, METRIC_BOOKED, METRIC_RATE, METRIC_VISITS, N_ITEMS, make_row)

logger = logging.getLogger(__name__)


def _key(row: dict[str, Any]) -> tuple[Any, ...]:
    """同じ人・日・媒体・項目をまとめるキー（指標と種類は除く）。"""
    return tuple(row[c] for c in ["date", "company"] + [f"item{i}" for i in range(1, N_ITEMS + 1)])


def add_percent_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """count の行に、次回予約率（ratio）の行を足して返す（元のリストは変えない）。"""
    visits: dict[tuple[Any, ...], float] = {}
    booked: dict[tuple[Any, ...], float] = {}
    for r in rows:
        if r["kind"] != KIND_ABS:
            continue
        if r["metric"] == METRIC_VISITS:
            visits[_key(r)] = r["value"]
        elif r["metric"] == METRIC_BOOKED:
            booked[_key(r)] = r["value"]
    out = list(rows)
    for k, v in visits.items():
        if v and k in booked:
            items = tuple(k[2:]) if k[2:] else ()
            out.append(make_row(k[0], k[1], METRIC_RATE, items, KIND_PCT, round(booked[k] / v, 3)))
    logger.info("比率(ratio)の行: %d 行を追加", len(out) - len(rows))
    return out


__all__ = ["add_percent_rows", "COLUMNS"]
