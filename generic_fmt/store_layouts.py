"""Link up 各店舗のスプレッドシートの作り（列の位置・1日目の行・区分の呼び名）。

2026-11-10 に全10店舗の 2026/9 のタブを見て作成。列は 1 始まり（A=1）。
区分 id: new / repeat / minimo_new / minimo_repeat。各区分は (入客の列, 取得の列)。
店舗のシートは Link up のものをそのまま使う。作りが変わったらここを直す。
"""
from __future__ import annotations

from dataclasses import dataclass

COMPANY = "link_up"
# 人ではない集計ブロックの見出し（読まない）
SKIP_NAMES = {"合計", "計", "スタッフ合計", "集計", "トータル", "総計", "総数", "総客数", "総件数"}


@dataclass(frozen=True)
class Block:
    """スタイリスト1人分のブロック。"""
    name_col: int
    day_col: int
    cols: dict[str, tuple[int, int]]
    nominated_col: int | None = None


@dataclass(frozen=True)
class Layout:
    """1店舗のシートの作り。"""
    name_row: int
    first_day_row: int
    blocks: tuple[Block, ...]


def layout_sofa(first_day_row: int = 5, start: int = 3, stride: int = 11, n: int = 8) -> Layout:
    """sofa国分寺・sofa立川・Ada立川: 人ごとに日付列、新規/再来/ミニモ新規/ミニモ再来(各入客・取得)+指名。"""
    blocks = tuple(
        Block(c0, c0, {"new": (c0 + 1, c0 + 2), "repeat": (c0 + 3, c0 + 4),
                       "minimo_new": (c0 + 5, c0 + 6), "minimo_repeat": (c0 + 7, c0 + 8)}, c0 + 9)
        for c0 in (start + i * stride for i in range(n)))
    return Layout(2, first_day_row, blocks)


def layout_sofa_5col(n: int = 6) -> Layout:
    """sofa八王子・sofa吉祥寺: 日付列+新規/取得/既存/取得/指名の5列。日付列は B から7列おき。"""
    blocks = tuple(
        Block(d, d, {"new": (d + 1, d + 2), "repeat": (d + 3, d + 4)}, d + 5)  # 名前は日付列の位置（B2:G2 の結合）
        for d in (2 + i * 7 for i in range(n)))
    return Layout(2, 4, blocks)


def layout_tokute(first_day_row: int, n: int = 6) -> Layout:
    """tokute吉祥寺・高円寺・shell吉祥寺: 日付は A 列だけ、新規/新規取得/リビ/リビ取得の4列。名前は1行目。"""
    blocks = tuple(
        Block(c0, 1, {"new": (c0, c0 + 1), "repeat": (c0 + 2, c0 + 3)})
        for c0 in (2 + i * 4 for i in range(n)))
    return Layout(1, first_day_row, blocks)


def layout_shell(groups: int = 5) -> Layout:
    """shell国分寺・立川: 既存/既存件数/新規/新規件数の4列。日付列は2人ごと（A, J, S ...）。"""
    blocks = []
    for g in range(groups):
        day = 1 + g * 9
        for j in range(2):
            c0 = day + 1 + j * 4
            blocks.append(Block(c0, day, {"repeat": (c0, c0 + 1), "new": (c0 + 2, c0 + 3)}))
    return Layout(2, 4, tuple(blocks))


STORES: dict[str, Layout] = {
    "sofa国分寺": layout_sofa(),
    "sofa立川": layout_sofa(),
    "Ada立川": layout_sofa(stride=20),
    "sofa八王子": layout_sofa_5col(),
    "sofa吉祥寺": layout_sofa_5col(),
    "tokute吉祥寺": layout_tokute(first_day_row=3),
    "tokute高円寺": layout_tokute(first_day_row=4),
    "shell吉祥寺": layout_tokute(first_day_row=4),
    "shell国分寺": layout_shell(),
    "shell立川": layout_shell(),
}
