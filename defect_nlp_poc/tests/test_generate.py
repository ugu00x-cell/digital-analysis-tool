"""generate_synthetic_data.py のテスト。

正常系2・異常系2・境界値1の最低構成を満たす。
"""
import random
from pathlib import Path

import pytest

from generate_synthetic_data import (
    PHRASES,
    build_samples,
    random_date_in_2024,
    write_csv,
)
from labels import label_keys


# 正常系1: 100件生成で件数が合う
def test_build_samples_produces_exact_count():
    samples = build_samples(100, seed=42)
    assert len(samples) == 100


# 正常系2: 全サンプルが必須キーを持つ
def test_build_samples_has_required_keys():
    samples = build_samples(16, seed=1)
    required = {"id", "date", "product_category", "defect_description", "true_label"}
    for s in samples:
        assert required.issubset(s.keys())
    # 同じseedで再実行すると結果が一致する（再現性）
    assert build_samples(16, seed=1) == samples


# 異常系1: true_labelが分類体系の外に出ていないこと
def test_build_samples_labels_are_all_valid():
    samples = build_samples(50, seed=7)
    valid = set(label_keys())
    for s in samples:
        assert s["true_label"] in valid


# 異常系2: defect_descriptionが対応するラベルのフレーズから選ばれている
def test_build_samples_description_matches_label():
    samples = build_samples(80, seed=3)
    for s in samples:
        assert s["defect_description"] in PHRASES[s["true_label"]]


# 境界値: 0件指定は空リストを返す
def test_build_samples_zero_total():
    assert build_samples(0, seed=0) == []


# 追加: 2024年内の日付生成
def test_random_date_in_2024_within_year():
    rng = random.Random(0)
    for _ in range(100):
        d = random_date_in_2024(rng)
        assert d.year == 2024


# 追加: CSV書き出しが成功する（tmp_pathで副作用を隔離）
def test_write_csv_roundtrip(tmp_path: Path):
    samples = build_samples(5, seed=0)
    output = tmp_path / "out.csv"
    write_csv(samples, output)
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    # ヘッダと5件の行（+ヘッダ1行）
    assert content.count("\n") >= 5
    assert "id,date,product_category,defect_description,true_label" in content
