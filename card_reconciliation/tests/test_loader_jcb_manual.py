"""JCB手動コピペ版（山中さん形式）ローダーのテスト。"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from card_reconciliation.services.loader import load_jcb_manual_csv


# --- 正常系1: 基本的な2ブロック ---
def test_jcb_manual_basic(tmp_path: Path) -> None:
    """4行1ブロック形式が正しくパースされる。"""
    path = tmp_path / "jcb.csv"
    path.write_text(
        "2026/04/15\n"
        "ＡＭＡＺＯＮ．ＣＯ．ＪＰ\n"
        "1回払い\n"
        '"28,539円"\n'
        "\n"
        "2026/04/14\n"
        "Ａｍａｚｏｎ　Ｍａｒｋｅｔ　Ｐｌａｃｅ\n"
        "1回払い\n"
        "3670円\n",
        encoding="utf-8-sig",
    )

    txs = load_jcb_manual_csv(path)

    assert len(txs) == 2
    assert txs[0].used_at == date(2026, 4, 15)
    assert txs[0].amount == 28539
    assert "ＡＭＡＺＯＮ" in txs[0].store
    assert txs[1].amount == 3670


# --- 正常系2: 末尾ブロック（空行なし）も読める ---
def test_jcb_manual_trailing_block_without_newline(tmp_path: Path) -> None:
    """ファイル末尾が空行で終わらなくても最後のブロックを取りこぼさない。"""
    path = tmp_path / "jcb.csv"
    path.write_text(
        "2026/04/15\n"
        "ＡＭＡＺＯＮ．ＣＯ．ＪＰ\n"
        "1回払い\n"
        "1,000円\n",  # 空行なしで終わる
        encoding="utf-8-sig",
    )

    txs = load_jcb_manual_csv(path)

    assert len(txs) == 1
    assert txs[0].amount == 1000


# --- 異常系1: 不完全ブロックはスキップされる ---
def test_jcb_manual_incomplete_block_skipped(tmp_path: Path) -> None:
    """4行揃わないブロックはスキップされ、他の正常ブロックは読める。"""
    path = tmp_path / "jcb.csv"
    path.write_text(
        "2026/04/15\n"
        "ＡＭＡＺＯＮ．ＣＯ．ＪＰ\n"
        "1回払い\n"
        "1,000円\n"
        "\n"
        # 3行しかない壊れたブロック
        "2026/04/14\n"
        "Ａｍａｚｏｎ\n"
        "1回払い\n"
        "\n"
        "2026/04/13\n"
        "ＡＭＡＺＯＮ．ＣＯ．ＪＰ\n"
        "1回払い\n"
        "2,000円\n",
        encoding="utf-8-sig",
    )

    txs = load_jcb_manual_csv(path)

    # 3行ブロックはスキップ、残り2件は採用
    assert len(txs) == 2
    assert txs[0].amount == 1000
    assert txs[1].amount == 2000


# --- 異常系2: 日付として壊れている行はスキップ ---
def test_jcb_manual_broken_date_skipped(tmp_path: Path) -> None:
    """日付がパースできないブロックはスキップされる。"""
    path = tmp_path / "jcb.csv"
    path.write_text(
        "XXXX/YY/ZZ\n"  # 壊れた日付
        "ＡＭＡＺＯＮ．ＣＯ．ＪＰ\n"
        "1回払い\n"
        "1,000円\n"
        "\n"
        "2026/04/14\n"
        "Ａｍａｚｏｎ\n"
        "1回払い\n"
        "2,000円\n",
        encoding="utf-8-sig",
    )

    txs = load_jcb_manual_csv(path)

    assert len(txs) == 1
    assert txs[0].amount == 2000


# --- 境界値: 金額の「円」と ", " 表記 ---
@pytest.mark.parametrize(
    "amount_text,expected",
    [
        ('"28,539円"', 28539),
        ("28539円", 28539),
        ("28,539", 28539),
        ("¥28,539", 28539),
    ],
)
def test_jcb_manual_amount_variants(
    tmp_path: Path, amount_text: str, expected: int
) -> None:
    """金額のカンマ・円記号・円文字などの表記ゆれに対応できる。"""
    path = tmp_path / "jcb.csv"
    path.write_text(
        f"2026/04/15\nＡＭＡＺＯＮ．ＣＯ．ＪＰ\n1回払い\n{amount_text}\n",
        encoding="utf-8-sig",
    )

    txs = load_jcb_manual_csv(path)

    assert len(txs) == 1
    assert txs[0].amount == expected
