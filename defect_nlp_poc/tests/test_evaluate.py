"""evaluate.py のテスト。

正常系2・異常系2・境界値1の最低構成を満たす。
"""
from pathlib import Path

import pytest

from evaluate import (
    compute_accuracy,
    compute_confusion_matrix,
    compute_per_label_accuracy,
    find_top_confusions,
    save_confusion_matrix,
)


# 正常系1: 全正解で一致率100%
def test_compute_accuracy_all_correct():
    rows = [
        {"true_label": "bearing_noise", "predicted_label": "bearing_noise"},
        {"true_label": "surface_rust", "predicted_label": "surface_rust"},
    ]
    correct, total, accuracy = compute_accuracy(rows)
    assert correct == 2
    assert total == 2
    assert accuracy == 1.0


# 正常系2: Confusion matrixが正しく集計される
def test_compute_confusion_matrix_counts_pairs():
    rows = [
        {"true_label": "bearing_noise", "predicted_label": "bearing_noise"},
        {"true_label": "bearing_noise", "predicted_label": "motion_alarm"},
        {"true_label": "bearing_noise", "predicted_label": "motion_alarm"},
    ]
    matrix = compute_confusion_matrix(rows)
    assert matrix[("bearing_noise", "bearing_noise")] == 1
    assert matrix[("bearing_noise", "motion_alarm")] == 2


# 異常系1: predicted_labelが空の行は評価対象外
def test_compute_accuracy_skips_empty_predictions():
    rows = [
        {"true_label": "bearing_noise", "predicted_label": ""},
        {"true_label": "bearing_noise", "predicted_label": "bearing_noise"},
    ]
    correct, total, accuracy = compute_accuracy(rows)
    # 空行は除外されるので total=1, correct=1
    assert total == 1
    assert correct == 1


# 異常系2: 全件空でも0割りにならない
def test_compute_accuracy_all_empty_returns_zero():
    rows = [{"true_label": "bearing_noise", "predicted_label": ""}]
    correct, total, accuracy = compute_accuracy(rows)
    assert correct == 0
    assert total == 0
    assert accuracy == 0.0


# 境界値: 空リストで0割りしない
def test_compute_accuracy_empty_list():
    correct, total, accuracy = compute_accuracy([])
    assert (correct, total, accuracy) == (0, 0, 0.0)


# 追加: Top confusionsは同じラベル同士を除外する
def test_find_top_confusions_excludes_correct_pairs():
    matrix = {
        ("bearing_noise", "bearing_noise"): 10,
        ("bearing_noise", "motion_alarm"): 3,
    }
    top = find_top_confusions(matrix, top_n=5)
    assert len(top) == 1
    assert top[0] == ("bearing_noise", "motion_alarm", 3)


# 追加: Confusion MatrixのCSV保存が成功する
def test_save_confusion_matrix_writes_csv(tmp_path: Path):
    matrix = {("bearing_noise", "motion_alarm"): 2}
    output = tmp_path / "matrix.csv"
    save_confusion_matrix(matrix, output)
    content = output.read_text(encoding="utf-8")
    assert "bearing_noise" in content
    assert "motion_alarm" in content


# 追加: per_label_accuracyが空行を除外
def test_per_label_accuracy_excludes_empty():
    rows = [
        {"true_label": "bearing_noise", "predicted_label": "bearing_noise"},
        {"true_label": "bearing_noise", "predicted_label": ""},
    ]
    per_label = compute_per_label_accuracy(rows)
    assert per_label["bearing_noise"] == (1, 1, 1.0)
