"""製造業 初期不良分類POC のエントリポイント。

合成データ20件をClaude APIで分類し、正解率を出力する。
"""
import logging
import sys
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

from classifier import classify_defect, get_client
from data import SAMPLES, DefectSample

# ログ設定（CLAUDE.md 指定フォーマット）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """1件分の分類結果。

    Attributes:
        sample: 元の不良サンプル
        predicted: LLMの分類結果（失敗時はNone）
        is_correct: 正解と一致したか（正解ラベル未設定時はNone）
    """
    sample: DefectSample
    predicted: Optional[str]
    is_correct: Optional[bool]


def evaluate_result(sample: DefectSample, predicted: Optional[str]) -> Optional[bool]:
    """分類結果を正解ラベルと比較する。

    Args:
        sample: 元の不良サンプル
        predicted: LLMの分類結果

    Returns:
        一致ならTrue、不一致ならFalse、正解ラベル未設定・予測失敗ならNone
    """
    if sample.correct_label is None or predicted is None:
        return None
    return sample.correct_label == predicted


def run_classification() -> list[ClassificationResult]:
    """全サンプルを分類して結果リストを返す。

    Returns:
        各サンプルに対する分類結果のリスト
    """
    client = get_client()
    results: list[ClassificationResult] = []

    for i, sample in enumerate(SAMPLES, start=1):
        logger.info("[%d/%d] 分類中: %s", i, len(SAMPLES), sample.text)
        predicted = classify_defect(client, sample.text)
        is_correct = evaluate_result(sample, predicted)
        results.append(ClassificationResult(
            sample=sample,
            predicted=predicted,
            is_correct=is_correct,
        ))

    return results


def print_results(results: list[ClassificationResult]) -> None:
    """分類結果を表形式で標準出力に表示する。

    Args:
        results: 分類結果のリスト
    """
    # ヘッダ
    print("=" * 90)
    print(f"{'No':>3} | {'入力テキスト':<30} | {'LLM分類':<16} | {'正解ラベル':<16} | 判定")
    print("-" * 90)

    # 各行を出力
    for i, r in enumerate(results, start=1):
        predicted = r.predicted or "（失敗）"
        correct = r.sample.correct_label or "（未設定）"
        if r.is_correct is True:
            judge = "○"
        elif r.is_correct is False:
            judge = "×"
        else:
            judge = "-"
        print(f"{i:>3} | {r.sample.text:<30} | {predicted:<16} | {correct:<16} | {judge}")

    print("=" * 90)


def print_accuracy(results: list[ClassificationResult]) -> None:
    """正解率を標準出力に表示する（正解ラベル設定済みのサンプルのみ対象）。

    Args:
        results: 分類結果のリスト
    """
    # 正解ラベルが設定されかつ予測も成功したサンプルを評価対象とする
    evaluated = [r for r in results if r.is_correct is not None]
    total = len(evaluated)
    correct_count = sum(1 for r in evaluated if r.is_correct)

    # 評価対象が0件の場合は警告のみ
    if total == 0:
        print("\n評価対象データがありません（正解ラベル未設定 or 全件API失敗）")
        return

    accuracy = correct_count / total
    print(f"\n正解率: {correct_count}/{total} = {accuracy:.1%}")

    # 参考情報：API失敗件数
    failed = sum(1 for r in results if r.predicted is None)
    if failed > 0:
        print(f"（API失敗: {failed}件）")


def main() -> int:
    """メイン処理。

    Returns:
        終了コード（0=成功、1=失敗）
    """
    load_dotenv()
    logger.info("製造業 初期不良分類POC を開始します")

    try:
        results = run_classification()
    except RuntimeError as e:
        # APIキー未設定などの致命的エラー
        logger.error("実行を中断しました: %s", e)
        return 1

    print_results(results)
    print_accuracy(results)
    logger.info("POC完了")
    return 0


if __name__ == "__main__":
    sys.exit(main())
