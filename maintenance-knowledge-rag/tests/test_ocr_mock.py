"""ocr_mock.py のテスト。"""

from __future__ import annotations

import random

import pytest

from src.ocr_mock import (
    DEFAULT_TYPO_RATE,
    PAPER_RECORDS,
    PaperInspection,
    _rejoin_lines,
    disturb_linebreaks,
    generate_paper_documents,
    inject_typos,
)


# ---- inject_typos 正常系 ----

def test_inject_typos_zero_rate_unchanged() -> None:
    """誤字率0なら入力と完全一致すること。"""
    rng = random.Random(0)
    text = "正常 軸 油 0 1"
    assert inject_typos(text, 0.0, rng) == text


def test_inject_typos_full_rate_replaces_known_chars() -> None:
    """誤字率1.0なら TYPO_TABLE のキーが全て置換されること。"""
    rng = random.Random(0)
    out = inject_typos("正常", 1.0, rng)
    # "正"→"圧", "常"→"當"
    assert out == "圧當"


# ---- inject_typos 異常系 ----

def test_inject_typos_invalid_rate() -> None:
    """範囲外の rate は ValueError。"""
    rng = random.Random(0)
    with pytest.raises(ValueError):
        inject_typos("正常", -0.1, rng)
    with pytest.raises(ValueError):
        inject_typos("正常", 1.5, rng)


# ---- inject_typos 境界値 ----

def test_inject_typos_empty_string() -> None:
    """空文字列はそのまま返すこと。"""
    rng = random.Random(0)
    assert inject_typos("", 0.5, rng) == ""


# ---- disturb_linebreaks ----

def test_disturb_linebreaks_preserves_chars() -> None:
    """行ズレを起こしても改行を除いた文字列は同じであること。"""
    rng = random.Random(0)
    text = "日付: 2024-02-03\n設備: MC003\n点検者: 田中さん"
    result = disturb_linebreaks(text, rng)
    assert result.replace("\n", "") == text.replace("\n", "")


# ---- _rejoin_lines ----

def test_rejoin_lines_extracts_fields_from_disturbed_text() -> None:
    """改行が崩れていても主要キーを抽出できること。"""
    text = "日付:\n2024-02-03 設備: MC003\n点検者: 田中さん 点検項目: 主軸 結果: 異常 異常: 異音 処置: 連絡"
    fields = _rejoin_lines(text)
    assert fields["日付"] == "2024-02-03"
    assert fields["設備"] == "MC003"
    assert fields["点検項目"] == "主軸"


# ---- generate_paper_documents（end-to-end） ----

def test_generate_paper_documents_end_to_end() -> None:
    """OCRモック → Document変換まで一気通貫で動くこと。"""
    docs = generate_paper_documents(seed=0)
    assert len(docs) == len(PAPER_RECORDS)
    for d in docs:
        assert d.metadata["source"] == "紙点検票OCR"
        assert d.metadata["machine_id"].startswith("MC")
        assert "【紙点検票OCR】" in d.page_content


def test_generate_paper_documents_with_custom_records() -> None:
    """カスタム records を渡せること。"""
    custom = [PaperInspection(
        "2024-07-01", "MC001", "山本さん", "主軸",
        "正常", "記録なし", "記録なし",
    )]
    docs = generate_paper_documents(records=custom, seed=1, typo_rate=0.0)
    assert len(docs) == 1
    # typo_rate=0 なら設備IDは MC001 のまま
    assert docs[0].metadata["machine_id"] == "MC001"


def test_default_typo_rate_matches_spec() -> None:
    """既定の誤字混入率は仕様書通り 5%。"""
    assert DEFAULT_TYPO_RATE == 0.05
