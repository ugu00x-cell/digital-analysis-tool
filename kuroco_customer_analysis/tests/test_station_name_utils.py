"""
station_name_utils.pyのテスト
"""
from kuroco_customer_analysis.utils.station_name_utils import (
    build_directions_query,
    normalize_station_name,
)


def test_normalize_station_name_adds_suffix():
    """正常系: 「駅」が付いていない駅名にサフィックスが付与される"""
    assert normalize_station_name("東京") == "東京駅"


def test_normalize_station_name_keeps_existing_suffix():
    """正常系: 既に「駅」が付いている駅名はそのまま返る"""
    assert normalize_station_name("渋谷駅") == "渋谷駅"


def test_normalize_station_name_strips_whitespace():
    """境界値: 前後の空白は除去されてから正規化される"""
    assert normalize_station_name("  新宿  ") == "新宿駅"


def test_normalize_station_name_empty_string():
    """異常系: 空文字を渡すと空文字が返る"""
    assert normalize_station_name("") == ""


def test_normalize_station_name_whitespace_only():
    """異常系: 空白のみの文字列を渡すと空文字が返る"""
    assert normalize_station_name("   ") == ""


def test_build_directions_query_with_prefecture():
    """正常系: 都道府県名を付与したクエリ文字列が生成される"""
    assert build_directions_query("東京駅", "東京都") == "東京都東京駅"


def test_build_directions_query_without_prefecture():
    """正常系: 都道府県名省略時は駅名のみ返る"""
    assert build_directions_query("東京駅") == "東京駅"
