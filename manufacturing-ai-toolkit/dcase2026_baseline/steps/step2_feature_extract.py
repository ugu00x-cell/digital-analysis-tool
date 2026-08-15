"""
Step 2: 特徴量抽出（メルスペクトログラム）

音声波形から対数メルスペクトログラムを算出し、
連続N_FRAMESフレームを結合した特徴ベクトルに変換する
"""

import logging
from pathlib import Path

import librosa
import numpy as np
from tqdm import tqdm

from dcase2026_baseline.config import (
    FMAX,
    HOP_LENGTH,
    INPUT_DIM,
    N_FFT,
    N_FRAMES,
    N_MELS,
    PATCH_FRAMES,
    PATCH_MELS,
    PATCH_STRIDE,
    SAMPLE_RATE,
)
from dcase2026_baseline.steps.step1_load_visualize import load_audio

logger = logging.getLogger(__name__)


def wav_to_log_melspec(wav: np.ndarray) -> np.ndarray:
    """音声波形を対数メルスペクトログラムに変換する

    Args:
        wav: 音声波形 (n_samples,)

    Returns:
        log_mel (n_mels, n_time_frames)
    """
    mel = librosa.feature.melspectrogram(
        y=wav, sr=SAMPLE_RATE,
        n_fft=N_FFT, hop_length=HOP_LENGTH,
        n_mels=N_MELS, fmax=FMAX, power=2.0,
    )
    # 対数変換（0除算を避ける）
    log_mel = 20.0 / np.log(10) * np.log(np.maximum(mel, 1e-10))
    return log_mel.astype(np.float32)


def frames_to_vectors(
    log_mel: np.ndarray, n_frames: int = N_FRAMES,
) -> np.ndarray:
    """対数メルスペクトログラムを連続フレームベクトルに変換する

    DCASE 2026標準: 連続n_framesフレームを結合して1ベクトル化
    ベクトル次元 = n_mels * n_frames

    Args:
        log_mel: (n_mels, n_time) のスペクトログラム
        n_frames: 結合するフレーム数

    Returns:
        vectors (n_vectors, n_mels * n_frames)
    """
    n_mels, n_time = log_mel.shape
    n_vectors = n_time - n_frames + 1
    if n_vectors <= 0:
        raise ValueError(
            f"時間フレーム数({n_time})がn_frames({n_frames})未満"
        )

    vectors = np.zeros((n_vectors, n_mels * n_frames), dtype=np.float32)
    for i in range(n_frames):
        # 各フレームオフセットを横方向に結合
        vectors[:, n_mels * i: n_mels * (i + 1)] = (
            log_mel[:, i: i + n_vectors].T
        )
    return vectors


def extract_features(file_path: Path) -> np.ndarray:
    """1ファイルから特徴ベクトル群を抽出する

    Args:
        file_path: .wavファイルのパス

    Returns:
        特徴ベクトル配列 (n_vectors, INPUT_DIM)
    """
    wav = load_audio(file_path)
    log_mel = wav_to_log_melspec(wav)
    vectors = frames_to_vectors(log_mel)
    return vectors


def extract_features_batch(file_paths: list[Path]) -> np.ndarray:
    """複数ファイルから特徴ベクトルをまとめて抽出する

    Args:
        file_paths: ファイルパスのリスト

    Returns:
        全ファイルの特徴ベクトルを結合した配列
    """
    all_vectors = []
    for fp in tqdm(file_paths, desc="特徴量抽出"):
        try:
            vectors = extract_features(fp)
            all_vectors.append(vectors)
        except Exception as e:
            logger.warning(f"抽出失敗 {fp.name}: {e}")
    return np.vstack(all_vectors)


def extract_per_file(
    file_paths: list[Path],
) -> list[np.ndarray]:
    """ファイルごとに特徴ベクトルを抽出する（異常スコア計算用）

    Args:
        file_paths: ファイルパスのリスト

    Returns:
        [ファイル1の特徴ベクトル, ファイル2の特徴ベクトル, ...]
    """
    per_file = []
    for fp in tqdm(file_paths, desc="ファイル別特徴量抽出"):
        per_file.append(extract_features(fp))
    return per_file


# ════════════════════════════════════════════════════════════
# CNN用2Dパッチ抽出（MobileNetV2向け）
# ════════════════════════════════════════════════════════════


def melspec_to_patches(
    log_mel: np.ndarray,
    patch_mels: int = PATCH_MELS,
    patch_frames: int = PATCH_FRAMES,
    stride: int = PATCH_STRIDE,
) -> np.ndarray:
    """対数メルスペクトログラムを2Dパッチに分割する

    時間方向にスライディングウィンドウでパッチ化する
    （周波数方向はパッチサイズと一致させる前提）

    Args:
        log_mel: (n_mels, n_time) のスペクトログラム
        patch_mels: パッチのメル次元（n_melsと同一推奨）
        patch_frames: パッチの時間フレーム数
        stride: パッチ間のフレームずらし幅

    Returns:
        パッチ配列 (n_patches, patch_mels, patch_frames)
    """
    n_mels, n_time = log_mel.shape
    if n_mels != patch_mels:
        raise ValueError(
            f"メル次元不一致: log_mel={n_mels}, patch_mels={patch_mels}"
        )
    if n_time < patch_frames:
        # データ短い場合はゼロパディング
        pad = patch_frames - n_time
        log_mel = np.pad(log_mel, ((0, 0), (0, pad)), mode="constant")
        n_time = patch_frames

    n_patches = max(1, (n_time - patch_frames) // stride + 1)
    patches = np.zeros(
        (n_patches, patch_mels, patch_frames), dtype=np.float32,
    )
    for i in range(n_patches):
        start = i * stride
        patches[i] = log_mel[:, start: start + patch_frames]
    return patches


def extract_patches(file_path: Path) -> np.ndarray:
    """1ファイルから2Dパッチを抽出する（CNN AE用）

    Args:
        file_path: .wavファイルのパス

    Returns:
        パッチ配列 (n_patches, PATCH_MELS, PATCH_FRAMES)
    """
    from dcase2026_baseline.steps.step1_load_visualize import load_audio

    wav = load_audio(file_path)
    log_mel = wav_to_log_melspec(wav)
    return melspec_to_patches(log_mel)


def extract_patches_batch(file_paths: list[Path]) -> np.ndarray:
    """複数ファイルから2Dパッチを一括抽出する

    Args:
        file_paths: ファイルパスのリスト

    Returns:
        全パッチ配列 (n_total_patches, PATCH_MELS, PATCH_FRAMES)
    """
    all_patches = []
    for fp in tqdm(file_paths, desc="2Dパッチ抽出"):
        try:
            patches = extract_patches(fp)
            all_patches.append(patches)
        except Exception as e:
            logger.warning(f"パッチ抽出失敗 {fp.name}: {e}")
    return np.vstack(all_patches)


def extract_patches_per_file(
    file_paths: list[Path],
) -> list[np.ndarray]:
    """ファイルごとに2Dパッチを抽出する（異常スコア計算用）

    Args:
        file_paths: ファイルパスのリスト

    Returns:
        [ファイル1のパッチ配列, ファイル2のパッチ配列, ...]
    """
    per_file = []
    for fp in tqdm(file_paths, desc="ファイル別パッチ抽出"):
        per_file.append(extract_patches(fp))
    return per_file


def run_step2_cnn(train_files: list[Path]) -> np.ndarray:
    """Step2をCNN AE用に実行する

    Args:
        train_files: 学習用ファイルリスト

    Returns:
        学習用パッチ配列 (n_patches, PATCH_MELS, PATCH_FRAMES)
    """
    logger.info("=" * 60)
    logger.info("Step 2: 2Dパッチ抽出（CNN用）")
    logger.info("=" * 60)
    logger.info(
        f"設定: patch_mels={PATCH_MELS}, "
        f"patch_frames={PATCH_FRAMES}, stride={PATCH_STRIDE}"
    )

    train_patches = extract_patches_batch(train_files)
    logger.info(f"学習用パッチshape: {train_patches.shape}")
    return train_patches


def run_step2(train_files: list[Path]) -> np.ndarray:
    """Step 2を実行する

    Args:
        train_files: 学習用ファイルリスト

    Returns:
        学習用特徴ベクトル (n_samples, INPUT_DIM)
    """
    logger.info("=" * 60)
    logger.info("Step 2: 特徴量抽出")
    logger.info("=" * 60)
    logger.info(
        f"設定: n_mels={N_MELS}, n_frames={N_FRAMES}, "
        f"input_dim={INPUT_DIM}"
    )

    train_features = extract_features_batch(train_files)
    logger.info(f"学習用特徴量shape: {train_features.shape}")

    return train_features
