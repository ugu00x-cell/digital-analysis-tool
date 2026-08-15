"""
Step 4: 異常スコア計算（CNN版）

テストファイルごとに2Dパッチを抽出し、
MobileNetV2 AEで再構成誤差(MSE)を算出してファイル単位スコアにする
"""

import logging
from pathlib import Path

import numpy as np
import torch
from sklearn.preprocessing import StandardScaler

from dcase2026_baseline.config import BATCH_SIZE
from dcase2026_baseline.steps.step2_feature_extract import (
    extract_patches_per_file,
)
from dcase2026_baseline.steps.step3_autoencoder import (
    MobileNetAutoEncoder,
    apply_normalization,
)

logger = logging.getLogger(__name__)


def compute_reconstruction_error(
    model: MobileNetAutoEncoder,
    scaler: StandardScaler,
    patches: np.ndarray,
    batch_size: int = BATCH_SIZE,
) -> np.ndarray:
    """パッチごとの再構成誤差(MSE)を算出する

    Args:
        model: 学習済みCNN AE
        scaler: 学習済みスケーラー
        patches: パッチ配列 (n_patches, mels, frames)
        batch_size: バッチサイズ

    Returns:
        各パッチのMSE配列 (n_patches,)
    """
    if len(patches) == 0:
        return np.array([])

    # 標準化 → tensor化
    scaled = apply_normalization(patches, scaler)
    tensor = torch.FloatTensor(scaled).unsqueeze(1)
    device = next(model.parameters()).device

    model.eval()
    errors = []
    with torch.no_grad():
        for i in range(0, len(tensor), batch_size):
            batch = tensor[i:i + batch_size].to(device, non_blocking=True)
            reconstructed = model(batch)
            # パッチごとのMSE（チャネル・空間方向で平均）
            mse = torch.mean(
                (batch - reconstructed) ** 2, dim=(1, 2, 3),
            )
            errors.extend(mse.cpu().numpy())

    return np.array(errors)


def compute_file_score(
    model: MobileNetAutoEncoder,
    scaler: StandardScaler,
    file_patches: np.ndarray,
) -> float:
    """1ファイルの異常スコアを算出する

    全パッチの再構成誤差の平均をスコアとする
    （DCASE Task 2の標準アプローチ）

    Args:
        model: 学習済みモデル
        scaler: 学習済みスケーラー
        file_patches: 1ファイル分のパッチ配列

    Returns:
        ファイルの異常スコア（高いほど異常）
    """
    errors = compute_reconstruction_error(model, scaler, file_patches)
    if len(errors) == 0:
        return 0.0
    return float(np.mean(errors))


def compute_scores_for_files(
    model: MobileNetAutoEncoder,
    scaler: StandardScaler,
    files: list[Path],
    label: int,
) -> tuple[list[float], list[int]]:
    """ファイル群の異常スコアを算出する

    Args:
        model: 学習済みモデル
        scaler: 学習済みスケーラー
        files: ファイルリスト
        label: 0=正常, 1=異常

    Returns:
        (スコアリスト, ラベルリスト)
    """
    per_file = extract_patches_per_file(files)
    scores = [
        compute_file_score(model, scaler, patches)
        for patches in per_file
    ]
    labels = [label] * len(scores)
    return scores, labels


def run_step4(
    model: MobileNetAutoEncoder,
    scaler: StandardScaler,
    test_normal: list[Path],
    test_anomaly: list[Path],
) -> dict:
    """Step 4を実行する（CNN版）

    Args:
        model: 学習済みCNN AE
        scaler: 学習済みスケーラー
        test_normal: 正常テストファイル
        test_anomaly: 異常テストファイル

    Returns:
        {"scores", "labels", "normal_scores", "anomaly_scores"}
    """
    logger.info("=" * 60)
    logger.info("Step 4: 異常スコア計算（CNN版）")
    logger.info("=" * 60)

    logger.info(f"正常{len(test_normal)}件のスコア算出中...")
    normal_scores, normal_labels = compute_scores_for_files(
        model, scaler, test_normal, label=0,
    )

    logger.info(f"異常{len(test_anomaly)}件のスコア算出中...")
    anomaly_scores, anomaly_labels = compute_scores_for_files(
        model, scaler, test_anomaly, label=1,
    )

    scores = normal_scores + anomaly_scores
    labels = normal_labels + anomaly_labels

    logger.info(
        f"スコア算出完了: 正常平均={np.mean(normal_scores):.6f}, "
        f"異常平均={np.mean(anomaly_scores):.6f}"
    )

    return {
        "scores": scores,
        "labels": labels,
        "normal_scores": normal_scores,
        "anomaly_scores": anomaly_scores,
    }
