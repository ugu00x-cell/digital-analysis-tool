"""Link up の店舗シート（xlsx）を読んで、汎用FMT（縦持ち）の CSV にする。

使い方:
  py extract_linkup.py --store sofa国分寺 --file 次回予約集計表.xlsx --year 2026 --month 9 --out out.csv

読み方は store_layouts.py の対応表どおり。入力の乱れは止めずに issues として集めて表示する
（空欄は休み、数字でない文字は読み飛ばす、取得が入客より多い日は印をつけるが値はそのまま出す）。
"""
from __future__ import annotations

import argparse
import csv
import datetime
import logging
import re
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from add_percent_rows import add_percent_rows
from schema import (ALL, COLUMNS, KIND_ABS, METRIC_BOOKED, METRIC_NOMINATED, METRIC_VISITS, make_row)
from store_layouts import COMPANY, SKIP_NAMES, STORES, Block, Layout

logger = logging.getLogger(__name__)

MEDIUM_ITEM = {"new": ("通常", "新規"), "repeat": ("通常", "再来"),
               "minimo_new": ("ミニモ", "新規"), "minimo_repeat": ("ミニモ", "再来")}
EXCLUDE_TAB_WORDS = ("キャンセル", "ミニモ", "コピー", "テンプレート", "数字報告", "集計表コピー")
TAB_RE = re.compile(r"(20\d\d)\D{0,3}(\d{1,2})")


def find_month_sheet(wb: Workbook, year: int, month: int) -> Worksheet:
    """タブ名（2026.09 / 2026/9 / 2026年9月 / 【2026/9】... ）から、指定の年月のタブを1枚探す。"""
    hits = []
    for ws in wb.worksheets:
        if any(w in ws.title for w in EXCLUDE_TAB_WORDS):
            continue
        m = TAB_RE.search(ws.title)
        if m and int(m.group(1)) == year and int(m.group(2)) == month:
            hits.append(ws)
    if len(hits) != 1:
        raise ValueError(f"{year}年{month}月のタブが{len(hits)}枚見つかりました: {[w.title for w in wb.worksheets]}")
    return hits[0]


def _num(ws: Worksheet, row: int, col: int, issues: list[str]) -> int | None:
    """セルを 0 以上の整数として読む。空欄は None。数字でない文字は読み飛ばして issues に書く。"""
    cell = ws.cell(row=row, column=col)
    v = cell.value
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        issues.append(f"{cell.coordinate}: 数字でないため読み飛ばしました ({v!r})")
        return None
    if n < 0 or n != int(n):
        issues.append(f"{cell.coordinate}: 0以上の整数ではないため読み飛ばしました ({v!r})")
        return None
    return int(n)


def _clean_name(value: Any) -> str | None:
    """名前を整える（前後の空白と、末尾の「さん」を除く）。空・集計ブロックは None。"""
    if not isinstance(value, str):
        return None
    name = re.sub(r"さん$", "", value.strip())
    return None if not name or name in SKIP_NAMES else name


def _has_header(ws: Worksheet, layout: Layout, block: Block) -> bool:
    """名前の下の見出し（新規・既存など）があるか。ないブロック（HPB・Google だけの別集計など）は読まない。"""
    visits_col = next(iter(block.cols.values()))[0]
    v = ws.cell(row=layout.name_row + 1, column=visits_col).value
    return isinstance(v, str) and bool(v.strip())


def _day_rows(ws: Worksheet, block: Block, row: int, issues: list[str]) -> dict[str, tuple[int | None, int | None]]:
    """1人1日の {区分: (入客, 取得)}。入客も取得も空欄の区分は含めない。"""
    out = {}
    for seg, (vc, bc) in block.cols.items():
        v, b = _num(ws, row, vc, issues), _num(ws, row, bc, issues)
        if v is None and b is None:
            continue
        if v is not None and b is not None and b > v:
            issues.append(f"{ws.cell(row=row, column=bc).coordinate}: 取得が入客より多いです ({b}>{v})")
        out[seg] = (v, b)
    return out


def _records(date: str, store: str, name: str, segs: dict[str, tuple[int | None, int | None]],
             nominated: int | None) -> list[dict[str, Any]]:
    """1人1日分を汎用FMTの行にする。"""
    rows: list[dict[str, Any]] = []
    for seg, (v, b) in segs.items():
        medium, item = MEDIUM_ITEM[seg]
        items = (store, name, medium, item)
        for metric, val in ((METRIC_VISITS, v), (METRIC_BOOKED, b)):
            if val is not None:
                rows.append(make_row(date, COMPANY, metric, items, KIND_ABS, val))
    if nominated is not None:
        rows.append(make_row(date, COMPANY, METRIC_NOMINATED, (store, name, ALL, ALL), KIND_ABS, nominated))
    return rows


def extract_sheet(ws: Worksheet, store: str, layout: Layout, year: int, month: int) -> tuple[list[dict[str, Any]], list[str]]:
    """1枚（1か月・1店舗）を読んで、件数(count)の行と issues を返す。"""
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    for block in layout.blocks:
        name = _clean_name(ws.cell(row=layout.name_row, column=block.name_col).value)
        if not name:
            continue
        if not _has_header(ws, layout, block):
            issues.append(f"{ws.cell(row=layout.name_row, column=block.name_col).coordinate}: 見出しがないため読み飛ばしました ({name})")
            continue
        for day in range(1, 32):
            row = layout.first_day_row + day - 1
            try:
                date = datetime.date(year, month, day).isoformat()
            except ValueError:
                continue  # その月にない日
            segs = _day_rows(ws, block, row, issues)
            nom = _num(ws, row, block.nominated_col, issues) if block.nominated_col else None
            rows += _records(date, store, name, segs, nom)
    return rows, issues


def stamp_rows(rows: list[dict[str, Any]], source_file: str, loaded_at: str) -> list[dict[str, Any]]:
    """各行に、取り込み元のファイル名と取り込み日時を付ける（元のリストは変えない）。"""
    return [{**r, "source_file": source_file, "loaded_at": loaded_at} for r in rows]


def source_file_name(store: str) -> str:
    """source_file に入れる固定名（例: linkup_sofa国分寺）。取込のたびに同じ名前になる。"""
    return f"linkup_{store}"


def extract_store(path: Path, store: str, year: int, month: int) -> tuple[list[dict[str, Any]], list[str]]:
    """xlsx を開き、店舗の対応表で読んで、比率(ratio)の行まで付けて返す。"""
    if store not in STORES:
        raise ValueError(f"未登録の店舗です: {store}（登録済み: {list(STORES)}）")
    wb = load_workbook(path, data_only=True)
    ws = find_month_sheet(wb, year, month)
    rows, issues = extract_sheet(ws, store, STORES[store], year, month)
    logger.info("%s %s: count %d 行、注意 %d 件", store, ws.title, len(rows), len(issues))
    loaded_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    # 洗い替えのキーになるので、ダウンロード名（「〜 (1).xlsx」など）ではなく店舗ごとの固定名にする
    return stamp_rows(add_percent_rows(rows), source_file_name(store), loaded_at), issues


def write_csv(rows: list[dict[str, Any]], out: Path) -> None:
    """CSV（UTF-8）に書く。BigQuery にそのまま読み込める。"""
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    logger.info("保存しました: %s（%d 行）", out, len(rows))


def main() -> int:
    """コマンドライン入口。"""
    ap = argparse.ArgumentParser(description="Link up の店舗シートを汎用FMTのCSVにする")
    ap.add_argument("--store", required=True)
    ap.add_argument("--file", required=True, type=Path)
    ap.add_argument("--year", required=True, type=int)
    ap.add_argument("--month", required=True, type=int)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    try:
        rows, issues = extract_store(a.file, a.store, a.year, a.month)
        write_csv(rows, a.out)
    except (OSError, ValueError):
        logger.exception("変換に失敗しました")
        return 1
    for msg in issues:
        logger.warning(msg)
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.FileHandler('app.log', encoding='utf-8'), logging.StreamHandler()],
    )
    raise SystemExit(main())
