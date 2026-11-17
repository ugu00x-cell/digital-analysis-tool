"""汎用FMT: Link up の店舗シート → 縦持ち（count/ratio）、比率の行、タブ探し。シートはテスト用に作る。"""
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent.parent / "generic_fmt"
sys.path.insert(0, str(ROOT))
import extract_linkup as ex  # noqa: E402
import schema as sc  # noqa: E402
from add_percent_rows import add_percent_rows  # noqa: E402
from store_layouts import STORES  # noqa: E402


def book(title="2026.09"):
    """空のブックとシートを作る。"""
    wb = Workbook()
    wb.active.title = title
    wb.active.cell(row=3, column=4, value="新規")  # sofa型の1人目の見出し
    return wb, wb.active


def key(r):
    """行を比べやすい形にする。"""
    return (r["metric"], r["item1"], r["item2"], r["item3"], r["item4"], r["kind"], r["value"])


# ---- 読み取り（正常系）-----------------------------------------------------------
def test_sofa_layout_reads_four_segments_and_nominated():
    wb, ws = book()
    ws.cell(row=2, column=3, value="漆原未来")
    day1 = 5
    for col, v in {6: 5, 7: 5, 8: 3, 9: 0, 12: 4}.items():  # 再来 5/5、ミニモ新規 3/0、指名 4
        ws.cell(row=day1, column=col, value=v)
    rows, issues = ex.extract_sheet(ws, "sofa国分寺", STORES["sofa国分寺"], 2026, 9)
    assert [key(r) for r in rows] == [
        ("来店客数", "sofa国分寺", "漆原未来", "通常", "再来", "count", 5),
        ("次回予約数", "sofa国分寺", "漆原未来", "通常", "再来", "count", 5),
        ("来店客数", "sofa国分寺", "漆原未来", "ミニモ", "新規", "count", 3),
        ("次回予約数", "sofa国分寺", "漆原未来", "ミニモ", "新規", "count", 0),
        ("指名数", "sofa国分寺", "漆原未来", "全体", "全体", "count", 4)]
    assert rows[0]["date"] == "2026-09-01" and rows[0]["company"] == "link_up" and rows[0]["item5"] == "" and rows[0]["item10"] == "" and issues == []
    assert list(rows[0]) == sc.BASE_COLUMNS and len(sc.COLUMNS) == 3 + 10 + 2 + 2


def test_shell_layout_maps_existing_first_then_new_and_strips_san():
    wb, ws = book("2026_9")
    ws.cell(row=3, column=2, value="既存"), ws.cell(row=3, column=6, value="既存")  # 見出し
    ws.cell(row=2, column=2, value="武藤さん")  # 1人目
    ws.cell(row=2, column=6, value="賢治さん")  # 2人目（日付列を共用）
    for col, v in {2: 6, 3: 6, 4: 1, 5: 0}.items():  # 既存 6/6、新規 1/0
        ws.cell(row=4, column=col, value=v)
    ws.cell(row=4, column=6, value=5), ws.cell(row=4, column=7, value=3)  # 2人目の既存 5/3
    rows, _ = ex.extract_sheet(ws, "shell国分寺", STORES["shell国分寺"], 2026, 9)
    got = [(r["item2"], r["item4"], r["metric"], r["value"]) for r in rows]
    assert ("武藤", "再来", "来店客数", 6) in got and ("武藤", "新規", "次回予約数", 0) in got
    assert ("賢治", "再来", "次回予約数", 3) in got


def test_percent_rows_are_added_with_one_decimal_and_skip_zero_visits():
    rows = [sc.make_row("2026-09-01", "link_up", sc.METRIC_VISITS, ("s", "a", "通常", "再来"), sc.KIND_ABS, 3),
            sc.make_row("2026-09-01", "link_up", sc.METRIC_BOOKED, ("s", "a", "通常", "再来"), sc.KIND_ABS, 2),
            sc.make_row("2026-09-01", "link_up", sc.METRIC_VISITS, ("s", "a", "通常", "新規"), sc.KIND_ABS, 0),
            sc.make_row("2026-09-01", "link_up", sc.METRIC_BOOKED, ("s", "a", "通常", "新規"), sc.KIND_ABS, 0)]
    out = add_percent_rows(rows)
    pct = [r for r in out if r["kind"] == "ratio"]
    assert len(out) == 5 and len(pct) == 1  # 来店客数 0 の行には率を作らない
    assert pct[0]["metric"] == "次回予約率" and pct[0]["value"] == 0.667 and pct[0]["item4"] == "再来"
    assert len(rows) == 4  # 元のリストは変えない


# ---- 読み取り（異常系）-----------------------------------------------------------
def test_bad_cells_are_skipped_with_issues_and_booked_over_visits_is_flagged():
    wb, ws = book()
    ws.cell(row=2, column=3, value="漆原未来")
    ws.cell(row=5, column=4, value="休")  # 数字でない
    ws.cell(row=5, column=6, value=2), ws.cell(row=5, column=7, value=3)  # 取得 > 入客
    rows, issues = ex.extract_sheet(ws, "sofa国分寺", STORES["sofa国分寺"], 2026, 9)
    assert any("数字でない" in m for m in issues) and any("取得が入客より多い" in m for m in issues)
    assert [r["value"] for r in rows] == [2, 3]  # 値はそのまま出る


def test_find_month_sheet_handles_name_variants_and_rejects_missing_or_ambiguous():
    wb = Workbook()
    wb.active.title = "数字報告"
    for t in ("2026.08", "【2026_9】次回予約集計表", "2026.6ミニモ", "10キャンセル"):
        wb.create_sheet(t)
    assert ex.find_month_sheet(wb, 2026, 9).title == "【2026_9】次回予約集計表"
    assert ex.find_month_sheet(wb, 2026, 8).title == "2026.08"
    with pytest.raises(ValueError, match="0枚"):
        ex.find_month_sheet(wb, 2026, 6)  # ミニモのタブは対象外
    wb.create_sheet("2026年9月")
    with pytest.raises(ValueError, match="2枚"):
        ex.find_month_sheet(wb, 2026, 9)


def test_unknown_store_is_rejected(tmp_path):
    wb, _ = book()
    p = tmp_path / "a.xlsx"
    wb.save(p)
    with pytest.raises(ValueError, match="未登録"):
        ex.extract_store(p, "存在しない店", 2026, 9)


# ---- 境界値 ------------------------------------------------------------------
def test_shell_total_block_named_sosu_is_not_read_as_a_stylist():
    wb, ws = book()
    ws.cell(row=2, column=29, value="総数"), ws.cell(row=3, column=29, value="既存")  # shell の集計ブロック
    ws.cell(row=4, column=29, value=99), ws.cell(row=4, column=30, value=50)
    rows, _ = ex.extract_sheet(ws, "shell立川", STORES["shell立川"], 2026, 9)
    assert rows == []


def test_total_block_blank_block_and_nonexistent_day_are_not_read():
    wb, ws = book()
    ws.cell(row=2, column=3, value="漆原未来")
    ws.cell(row=2, column=14, value="合計"), ws.cell(row=3, column=15, value="新規")  # 2つ目の位置に合計（読まない）
    ws.cell(row=5, column=15, value=9), ws.cell(row=5, column=16, value=9)
    ws.cell(row=35, column=4, value=2), ws.cell(row=35, column=5, value=1)  # 31日。9月にはない
    rows, _ = ex.extract_sheet(ws, "sofa国分寺", STORES["sofa国分寺"], 2026, 9)
    assert rows == []
    rows, _ = ex.extract_sheet(ws, "sofa国分寺", STORES["sofa国分寺"], 2026, 10)  # 10月なら31日を読む
    assert [r["date"] for r in rows] == ["2026-10-31", "2026-10-31"]


def test_named_block_without_header_is_skipped_with_issue():
    """Ada立川の右側にある HPB・Google だけのブロック（名前はあるが見出しがない）は読まない。"""
    wb, ws = book()
    ws.cell(row=2, column=23, value="さら")  # 2つ目の位置（stride 20）。見出しなし
    ws.cell(row=5, column=24, value=4), ws.cell(row=5, column=25, value=2)
    rows, issues = ex.extract_sheet(ws, "Ada立川", STORES["Ada立川"], 2026, 9)
    assert rows == [] and any("見出しがない" in m and "さら" in m for m in issues)


def test_sofa_5col_layout_name_is_in_the_day_column_and_maps_new_then_existing():
    """sofa八王子・吉祥寺: 名前は日付列(B2)、新規/取得/既存/取得/指名の順。"""
    wb, ws = book()
    ws.cell(row=2, column=2, value="福田"), ws.cell(row=3, column=3, value="新規")
    for col, v in {3: 1, 4: 1, 5: 4, 6: 3, 7: 2}.items():  # 新規 1/1、既存 4/3、指名 2
        ws.cell(row=4, column=col, value=v)
    rows, _ = ex.extract_sheet(ws, "sofa八王子", STORES["sofa八王子"], 2026, 9)
    assert [(r["item4"], r["metric"], r["value"]) for r in rows] == [
        ("新規", "来店客数", 1), ("新規", "次回予約数", 1), ("再来", "来店客数", 4), ("再来", "次回予約数", 3), ("全体", "指名数", 2)]


def test_extract_store_stamps_source_file_and_loaded_at(tmp_path):
    """source_file（店舗ごとの固定名）と取り込み日時が全行に付き、列は COLUMNS と一致する。"""
    wb, ws = book()
    ws.cell(row=2, column=3, value="漆原未来")
    ws.cell(row=5, column=6, value=5), ws.cell(row=5, column=7, value=4)
    path = tmp_path / "次回予約集計表(sofa国分寺).xlsx"
    wb.save(path)
    rows, _ = ex.extract_store(path, "sofa国分寺", 2026, 9)
    assert rows and all(r["source_file"] == "linkup_sofa国分寺" for r in rows)
    assert all(list(r) == sc.COLUMNS for r in rows) and all(r["loaded_at"].endswith("+00:00") for r in rows)
    assert sorted({r["kind"] for r in rows}) == ["count", "ratio"]


def test_source_file_is_stable_even_if_download_name_changes(tmp_path):
    """ダウンロード名が変わっても source_file は同じ（洗い替えで古い行が残らない）。"""
    names = set()
    for fname in ("次回予約集計表.xlsx", "次回予約集計表 (1).xlsx"):
        wb, ws = book()
        ws.cell(row=2, column=3, value="漆原未来")
        ws.cell(row=5, column=6, value=5), ws.cell(row=5, column=7, value=4)
        path = tmp_path / fname
        wb.save(path)
        rows, _ = ex.extract_store(path, "sofa国分寺", 2026, 9)
        names |= {r["source_file"] for r in rows}
    assert names == {"linkup_sofa国分寺"}
