"""
合成音声データ生成モジュール

dev_Bearingの実データが無い場合のフォールバック
正常音: 定常な低周波振動音
異常音: 高周波成分 + 衝撃波を含む音
"""

import logging
from pathlib import Path

import numpy as np
import soundfile as sf

from dcase2026_baseline.config import (
    DURATION_SEC,
    N_SAMPLES,
    RANDOM_SEED,
    SAMPLE_RATE,
    SYNTHETIC_DIR,
)

logger = logging.getLogger(__name__)


def _generate_normal_sound(rng: np.random.Generator) -> np.ndarray:
    """正常ベアリング音を生成する（定常な回転音）

    Returns:
        音声波形 (N_SAMPLES,)
    """
    t = np.linspace(0, DURATION_SEC, N_SAMPLES, endpoint=False)
    # 回転基本周波数 50Hz + 倍音
    base_freq = 50.0 + rng.normal(0, 2.0)
    signal = (
        0.3 * np.sin(2 * np.pi * base_freq * t)
        + 0.1 * np.sin(2 * np.pi * base_freq * 2 * t)
        + 0.05 * np.sin(2 * np.pi * base_freq * 3 * t)
    )
    # 背景ノイズ
    signal += rng.normal(0, 0.02, N_SAMPLES)
    return signal.astype(np.float32)


def _generate_anomaly_sound(rng: np.random.Generator) -> np.ndarray:
    """異常ベアリング音を生成する（衝撃波+高周波）

    Returns:
        音声波形 (N_SAMPLES,)
    """
    t = np.linspace(0, DURATION_SEC, N_SAMPLES, endpoint=False)
    base_freq = 50.0 + rng.normal(0, 2.0)
    signal = (
        0.3 * np.sin(2 * np.pi * base_freq * t)
        + 0.1 * np.sin(2 * np.pi * base_freq * 2 * t)
    )
    # 高周波異常音（2kHz付近）
    anomaly_freq = 2000.0 + rng.normal(0, 100)
    signal += 0.15 * np.sin(2 * np.pi * anomaly_freq * t)
    # 周期的な衝撃波（BPFO想定）
    impact_period = int(SAMPLE_RATE * 0.1)  # 10Hz
    for i in range(0, N_SAMPLES, impact_period):
        end = min(i + 100, N_SAMPLES)
        signal[i:end] += rng.normal(0, 0.3, end - i) * np.exp(
            -np.arange(end - i) / 20,
        )
    signal += rng.normal(0, 0.03, N_SAMPLES)
    return signal.astype(np.float32)


def generate_synthetic_dataset(
    n_train_normal: int = 100,
    n_test_normal: int = 20,
    n_test_anomaly: int = 20,
) -> Path:
    """合成データセット全体を生成する

    Args:
        n_train_normal: 学習用正常データ数
        n_test_normal: テスト用正常データ数
        n_test_anomaly: テスト用異常データ数

    Returns:
        生成先ディレクトリのパス
    """
    rng = np.random.default_rng(RANDOM_SEED)
    train_dir = SYNTHETIC_DIR / "train"
    test_dir = SYNTHETIC_DIR / "test"
    train_dir.mkdir(parents=True, exist_ok=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"合成データ生成開始: {SYNTHETIC_DIR}")

    # 学習用正常データ
    for i in range(n_train_normal):
        wav = _generate_normal_sound(rng)
        sf.write(
            train_dir / f"normal_id_00_{i:06d}.wav",
            wav, SAMPLE_RATE,
        )

    # テスト用正常データ
    for i in range(n_test_normal):
        wav = _generate_normal_sound(rng)
        sf.write(
            test_dir / f"normal_id_00_{i:06d}.wav",
            wav, SAMPLE_RATE,
        )

    # テスト用異常データ
    for i in range(n_test_anomaly):
        wav = _generate_anomaly_sound(rng)
        sf.write(
            test_dir / f"anomaly_id_00_{i:06d}.wav",
            wav, SAMPLE_RATE,
        )

    logger.info(
        f"合成データ生成完了: "
        f"train={n_train_normal}, "
        f"test={n_test_normal + n_test_anomaly}"
    )
    return SYNTHETIC_DIR
