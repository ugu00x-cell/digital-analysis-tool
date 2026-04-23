"""defects_classified.csv を読んで精度を検証する。

- 全体一致率（accuracy）
- ラベル別の一致率とConfusion Matrix
- 誤分類Top10パターン
"""
import csv
import logging
from collections import Counter, defaultdict
from pathlib import Path

from labels import label_keys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = BASE_DIR / "data" / "defects_classified.csv"
CONFUSION_MATRIX_PATH = BASE_DIR / "data" / "confusion_matrix.csv"


def read_rows(input_path: Path) -> list[dict]:
    """分類結果CSVを読み込む。

    Raises:
        FileNotFoundError: 入力ファイルが存在しない場合
    """
    if not input_path.exists():
        raise FileNotFoundError(
            f"分類結果ファイルが見つかりません: {input_path}。"
            "先に classifier.py を実行してください。"
        )
    with input_path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def compute_accuracy(rows: list[dict]) -> tuple[int, int, float]:
    """全体の一致率を計算する。

    Args:
        rows: true_label / predicted_label を持つ行データ

    Returns:
        (正解数, 評価対象数, 一致率)。評価対象0件の場合は0.0
    """
    # predicted_labelが空の行は評価対象外（API失敗）
    evaluated = [r for r in rows if r.get("predicted_label")]
    correct = sum(1 for r in evaluated if r["true_label"] == r["predicted_label"])
    total = len(evaluated)
    accuracy = correct / total if total else 0.0
    return correct, total, accuracy


def compute_per_label_accuracy(rows: list[dict]) -> dict[str, tuple[int, int, float]]:
    """ラベル別の一致率を計算する。

    Returns:
        {true_label: (正解数, 件数, 一致率)} の辞書
    """
    by_label: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("predicted_label"):
            by_label[row["true_label"]].append(row)

    result: dict[str, tuple[int, int, float]] = {}
    for label, subset in by_label.items():
        correct = sum(1 for r in subset if r["true_label"] == r["predicted_label"])
        total = len(subset)
        result[label] = (correct, total, correct / total if total else 0.0)
    return result


def compute_confusion_matrix(rows: list[dict]) -> dict[tuple[str, str], int]:
    """Confusion Matrix（(true, predicted) → 件数）を計算する。"""
    matrix: Counter = Counter()
    for row in rows:
        if row.get("predicted_label"):
            matrix[(row["true_label"], row["predicted_label"])] += 1
    return dict(matrix)


def find_top_confusions(matrix: dict[tuple[str, str], int], top_n: int = 10) -> list[tuple[str, str, int]]:
    """誤分類パターンを件数降順でTop Nまで返す。

    Args:
        matrix: Confusion Matrix
        top_n: 返す件数上限

    Returns:
        (true_label, predicted_label, 件数) のリスト
    """
    errors = [(t, p, c) for (t, p), c in matrix.items() if t != p]
    errors.sort(key=lambda x: x[2], reverse=True)
    return errors[:top_n]


def print_accuracy(correct: int, total: int, accuracy: float) -> None:
    """全体の一致率を表示する。"""
    print("=" * 60)
    print(f"全体一致率: {correct}/{total} = {accuracy:.1%}")
    print("=" * 60)


def print_per_label(per_label: dict[str, tuple[int, int, float]]) -> None:
    """ラベル別の一致率を表示する。"""
    print("\n[ラベル別一致率]")
    print(f"{'label':<22} | {'correct/total':<15} | rate")
    print("-" * 55)
    for label in label_keys():
        if label in per_label:
            correct, total, rate = per_label[label]
            print(f"{label:<22} | {correct}/{total:<13} | {rate:.1%}")
        else:
            print(f"{label:<22} | 0/0             | N/A")


def print_top_confusions(top_confusions: list[tuple[str, str, int]]) -> None:
    """誤分類Top10を表示する。"""
    print("\n[間違えやすいパターン Top10]")
    if not top_confusions:
        print("（誤分類なし）")
        return
    print(f"{'true_label':<22} -> {'predicted_label':<22} | count")
    print("-" * 60)
    for true_label, pred_label, count in top_confusions:
        print(f"{true_label:<22} -> {pred_label:<22} | {count}")


def save_confusion_matrix(matrix: dict[tuple[str, str], int], output_path: Path) -> None:
    """Confusion MatrixをCSVに保存する（true_label × predicted_labelの表形式）。"""
    labels = label_keys()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["true \\ predicted", *labels])
        for true_label in labels:
            row = [true_label] + [matrix.get((true_label, p), 0) for p in labels]
            writer.writerow(row)


def main() -> None:
    """分類結果を読み込んで精度を集計・表示する。"""
    rows = read_rows(INPUT_PATH)
    logger.info("分類結果%d件を読み込みました", len(rows))

    correct, total, accuracy = compute_accuracy(rows)
    per_label = compute_per_label_accuracy(rows)
    matrix = compute_confusion_matrix(rows)
    top_confusions = find_top_confusions(matrix)

    print_accuracy(correct, total, accuracy)
    print_per_label(per_label)
    print_top_confusions(top_confusions)

    save_confusion_matrix(matrix, CONFUSION_MATRIX_PATH)
    logger.info("Confusion Matrix保存: %s", CONFUSION_MATRIX_PATH)


if __name__ == "__main__":
    main()
