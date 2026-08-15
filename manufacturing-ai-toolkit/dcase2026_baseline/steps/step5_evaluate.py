"""
Step 5: AUC-ROC評価

ファイル単位の異常スコアからAUC-ROCを算出し、
ROC曲線とスコア分布を可視化する
"""

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import auc, roc_auc_score, roc_curve

from dcase2026_baseline.config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def calc_auc(scores: list[float], labels: list[int]) -> float:
    """AUC-ROCを算出する

    Args:
        scores: 異常スコア（高いほど異常）
        labels: 0=正常, 1=異常

    Returns:
        AUC-ROC値
    """
    return float(roc_auc_score(labels, scores))


def calc_partial_auc(
    scores: list[float],
    labels: list[int],
    max_fpr: float = 0.1,
) -> float:
    """部分AUC（FPR <= 0.1 での AUC）を算出する

    DCASE Task 2の評価指標の1つ

    Args:
        scores: 異常スコア
        labels: ラベル
        max_fpr: FPRの上限

    Returns:
        部分AUC（正規化済み）
    """
    return float(roc_auc_score(labels, scores, max_fpr=max_fpr))


def plot_roc_curve(
    scores: list[float],
    labels: list[int],
    output_path: Path,
) -> None:
    """ROC曲線を描画する"""
    fpr, tpr, _ = roc_curve(labels, scores)
    roc_auc = auc(fpr, tpr)

    plt.figure(figsize=(7, 7))
    plt.plot(
        fpr, tpr, color="darkorange", linewidth=2,
        label=f"AUC = {roc_auc:.4f}",
    )
    plt.plot([0, 1], [0, 1], color="navy", linestyle="--", linewidth=1)
    plt.xlim(0, 1)
    plt.ylim(0, 1.02)
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("ROC Curve - DCASE 2026 Task 2 (Bearing) Baseline")
    plt.legend(loc="lower right")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=120)
    plt.close()
    logger.info(f"ROC曲線保存: {output_path}")


def plot_score_distribution(
    normal_scores: list[float],
    anomaly_scores: list[float],
    output_path: Path,
) -> None:
    """スコア分布のヒストグラムを描画する"""
    plt.figure(figsize=(10, 5))
    bins = 30
    plt.hist(
        normal_scores, bins=bins, alpha=0.6,
        color="steelblue", label="Normal", edgecolor="black",
    )
    plt.hist(
        anomaly_scores, bins=bins, alpha=0.6,
        color="crimson", label="Anomaly", edgecolor="black",
    )
    plt.xlabel("Anomaly Score (Reconstruction Error)")
    plt.ylabel("Frequency")
    plt.title("Anomaly Score Distribution")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=120)
    plt.close()
    logger.info(f"スコア分布保存: {output_path}")


def save_results_csv(
    scores: list[float],
    labels: list[int],
    output_path: Path,
) -> None:
    """スコアとラベルをCSV出力する"""
    import csv
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["score", "label"])
        for s, l in zip(scores, labels):
            writer.writerow([s, l])
    logger.info(f"結果CSV保存: {output_path}")


def run_step5(score_data: dict) -> dict:
    """Step 5を実行する

    Args:
        score_data: Step 4の出力

    Returns:
        評価指標辞書
    """
    logger.info("=" * 60)
    logger.info("Step 5: AUC-ROC評価")
    logger.info("=" * 60)

    scores = score_data["scores"]
    labels = score_data["labels"]
    normal_scores = score_data["normal_scores"]
    anomaly_scores = score_data["anomaly_scores"]

    # AUC算出
    auc_roc = calc_auc(scores, labels)
    p_auc = calc_partial_auc(scores, labels, max_fpr=0.1)

    logger.info(f"AUC-ROC:     {auc_roc:.4f}")
    logger.info(f"Partial AUC: {p_auc:.4f} (FPR <= 0.1)")

    # 可視化
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_roc_curve(scores, labels, OUTPUT_DIR / "step5_roc_curve.png")
    plot_score_distribution(
        normal_scores, anomaly_scores,
        OUTPUT_DIR / "step5_score_dist.png",
    )
    save_results_csv(scores, labels, OUTPUT_DIR / "step5_scores.csv")

    return {
        "auc_roc": auc_roc,
        "partial_auc": p_auc,
        "normal_mean": float(np.mean(normal_scores)),
        "anomaly_mean": float(np.mean(anomaly_scores)),
        "separation": float(
            np.mean(anomaly_scores) - np.mean(normal_scores),
        ),
    }
