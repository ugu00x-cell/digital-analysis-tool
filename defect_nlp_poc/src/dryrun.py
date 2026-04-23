"""ドライラン：Claude APIを呼ばずに分類パイプライン全体を検証する。

- 入力CSVのtrue_labelを擬似予測として使い、20%だけ別ラベルに置換して誤分類を再現
- merge_predictions / CSV出力まで本番と同じコードパスを通す
- 開発中・分類体系変更時の動作確認に使用
"""
import logging
import random
from pathlib import Path

from classifier import OUTPUT_PATH, merge_predictions, read_rows, write_rows
from labels import label_keys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = BASE_DIR / "data" / "defects_raw.csv"

# 擬似誤分類率（動作確認用。0.0なら全件正解、1.0なら全件誤分類）
MISCLASSIFY_RATE = 0.2
DRY_RUN_SEED = 42


def fake_predict(rows: list[dict], rate: float, seed: int) -> list[dict]:
    """true_labelベースで擬似的な分類結果を作る。

    Args:
        rows: id/true_labelを持つ入力行
        rate: 別ラベルに置換する確率（0.0〜1.0）
        seed: 乱数シード

    Returns:
        classifier.merge_predictions が期待する形式の辞書リスト
    """
    rng = random.Random(seed)
    labels = label_keys()
    results: list[dict] = []
    for row in rows:
        predicted = row["true_label"]
        # 一定確率で別ラベルに置換して誤分類パターンを作る
        if rng.random() < rate:
            others = [lbl for lbl in labels if lbl != predicted]
            predicted = rng.choice(others)
        results.append({
            "id": int(row["id"]),
            "predicted_label": predicted,
            "confidence": "high",
            "sub_category": "(dry-run)",
            "estimated_cause": "(dry-run)",
            "countermeasure": "(dry-run)",
        })
    return results


def main() -> None:
    """ドライラン：擬似予測で defects_classified.csv を生成する。"""
    rows = read_rows(INPUT_PATH)
    logger.info("入力%d件を読み込み", len(rows))

    predictions = fake_predict(rows, MISCLASSIFY_RATE, DRY_RUN_SEED)
    merged = merge_predictions(rows, predictions)

    write_rows(merged, OUTPUT_PATH)
    logger.info("ドライラン結果を出力: %s", OUTPUT_PATH)
    logger.info("続けて evaluate.py を実行すると精度表示されます")


if __name__ == "__main__":
    main()
