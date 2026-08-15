"""generate_date_chunksの単体テスト"""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from export_31day_chunks import generate_date_chunks


def test_generate_date_chunks_multiple_full_months() -> None:
    """複数月にまたがる場合は各月1日〜月末で分割される"""
    chunks = generate_date_chunks(date(2025, 1, 1), date(2025, 3, 31))
    assert chunks == [
        (date(2025, 1, 1), date(2025, 1, 31)),
        (date(2025, 2, 1), date(2025, 2, 28)),
        (date(2025, 3, 1), date(2025, 3, 31)),
    ]


def test_generate_date_chunks_single_day() -> None:
    """1日だけの期間は1区間になる"""
    chunks = generate_date_chunks(date(2025, 1, 15), date(2025, 1, 15))
    assert chunks == [(date(2025, 1, 15), date(2025, 1, 15))]


def test_generate_date_chunks_invalid_range() -> None:
    """開始日が終了日より後の場合はエラー"""
    with pytest.raises(ValueError):
        generate_date_chunks(date(2025, 2, 1), date(2025, 1, 1))


def test_generate_date_chunks_partial_first_and_last_month() -> None:
    """月の途中から始まり月の途中で終わる場合、端の区間は実際の日付に切り詰められる"""
    chunks = generate_date_chunks(date(2025, 1, 15), date(2025, 2, 10))
    assert chunks == [
        (date(2025, 1, 15), date(2025, 1, 31)),
        (date(2025, 2, 1), date(2025, 2, 10)),
    ]


def test_generate_date_chunks_leap_year_february() -> None:
    """うるう年の2月は29日まで正しく区切られる"""
    chunks = generate_date_chunks(date(2024, 2, 1), date(2024, 2, 29))
    assert chunks == [(date(2024, 2, 1), date(2024, 2, 29))]
