"""
Step 1: データ読み込みと可視化

DCASE 2026 Bearingデータを読み込み、正常/異常音の
波形とメルスペクトログラムを比較可視化する
"""

import logging
from pathlib import Path

import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np

from dcase2026_baseline.config import (
    DATA_ROOT,
    FMAX,
    HOP_LENGTH,
    N_FFT,
    N_MELS,
    OUTPUT_DIR,
    SAMPLE_RATE,
    TEST_DIR,
    TRAIN_DIR,
)
from dcase2026_baseline.utils.synthetic_data import (
    SYNTHETIC_DIR,
    generate_synthetic_dataset,
)

logger = logging.getLogger(__name__)


def find_data_root() -> tuple[Path, Path]:
    """データルートを検出する

    dev_Bearingが無い場合は合成データを自動生成する

    Returns:
        (train_dir, test_dir)
    """
    if TRAIN_DIR.exists() and TEST_DIR.exists():
        logger.info(f"実データを使用: {DATA_ROOT}")
        return TRAIN_DIR, TEST_DIR

    logger.warning(
        f"{DATA_ROOT} が見つかりません。合成データを生成します。"
    )
    generate_synthetic_dataset()
    return SYNTHETIC_DIR / "train", SYNTHETIC_DIR / "test"


def load_audio(file_path: Path, sr: int = SAMPLE_RATE) -> np.ndarray:
    """音声ファイルを読み込む

    Args:
        file_path: .wavファイルのパス
        sr: リサンプリング周波数

    Returns:
        音声波形
    """
    y, _ = librosa.load(str(file_path), sr=sr, mono=True)
    return y


def list_wav_files(
    directory: Path, pattern: str = "*.wav",
) -> list[Path]:
    """ディレクトリ内のwavファイルを列挙する

    Args:
        directory: 検索対象ディレクトリ
        pattern: globパターン

    Returns:
        ソート済みファイルパスリスト
    """
    return sorted(directory.glob(pattern))


def split_normal_anomaly(
    test_files: list[Path],
) -> tuple[list[Path], list[Path]]:
    """テストファイルを正常/異常に分離する

    DCASE 2026形式: "_normal_" / "_anomaly_" がファイル名に含まれる
    合成データ形式: "normal_" / "anomaly_" で始まる
    両方に対応する

    Args:
        test_files: テストファイルリスト

    Returns:
        (正常ファイル, 異常ファイル)
    """
    normal = [
        f for f in test_files
        if "_normal_" in f.name or f.name.startswith("normal")
    ]
    anomaly = [
        f for f in test_files
        if "_anomaly_" in f.name or f.name.startswith("anomaly")
    ]
    return normal, anomaly


def plot_comparison(
    normal_wav: np.ndarray,
    anomaly_wav: np.ndarray,
    output_path: Path,
) -> None:
    """正常/異常音の波形とメルスペクトログラムを比較プロット

    Args:
        normal_wav: 正常音波形
        anomaly_wav: 異常音波形
        output_path: 出力画像パス
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))

    # 波形比較
    t = np.arange(len(normal_wav)) / SAMPLE_RATE
    axes[0, 0].plot(t, normal_wav, linewidth=0.5, color="steelblue")
    axes[0, 0].set(title="Normal - Waveform",
                   xlabel="Time [s]", ylabel="Amplitude")
    axes[0, 0].grid(alpha=0.3)

    axes[0, 1].plot(t, anomaly_wav, linewidth=0.5, color="crimson")
    axes[0, 1].set(title="Anomaly - Waveform",
                   xlabel="Time [s]", ylabel="Amplitude")
    axes[0, 1].grid(alpha=0.3)

    # メルスペクトログラム比較
    for idx, (wav, title, ax) in enumerate([
        (normal_wav, "Normal - Mel Spectrogram", axes[1, 0]),
        (anomaly_wav, "Anomaly - Mel Spectrogram", axes[1, 1]),
    ]):
        mel = librosa.feature.melspectrogram(
            y=wav, sr=SAMPLE_RATE,
            n_fft=N_FFT, hop_length=HOP_LENGTH,
            n_mels=N_MELS, fmax=FMAX,
        )
        mel_db = librosa.power_to_db(mel, ref=np.max)
        img = librosa.display.specshow(
            mel_db, sr=SAMPLE_RATE,
            hop_length=HOP_LENGTH, x_axis="time", y_axis="mel",
            ax=ax, fmax=FMAX,
        )
        ax.set(title=title)
        fig.colorbar(img, ax=ax, format="%+2.0f dB")

    plt.tight_layout()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=120)
    plt.close()
    logger.info(f"比較プロット保存: {output_path}")


def run_step1() -> dict:
    """Step 1を実行する

    Returns:
        {"train_files": [...], "test_normal": [...], "test_anomaly": [...]}
    """
    logger.info("=" * 60)
    logger.info("Step 1: データ読み込みと可視化")
    logger.info("=" * 60)

    train_dir, test_dir = find_data_root()

    train_files = list_wav_files(train_dir)
    test_files = list_wav_files(test_dir)
    test_normal, test_anomaly = split_normal_anomaly(test_files)

    logger.info(f"学習ファイル数: {len(train_files)}")
    logger.info(f"テスト正常: {len(test_normal)}件")
    logger.info(f"テスト異常: {len(test_anomaly)}件")

    if not train_files:
        raise FileNotFoundError(
            f"学習データが見つかりません: {train_dir}"
        )

    # サンプルを1つずつ可視化
    if test_normal and test_anomaly:
        normal_wav = load_audio(test_normal[0])
        anomaly_wav = load_audio(test_anomaly[0])
        plot_comparison(
            normal_wav, anomaly_wav,
            OUTPUT_DIR / "step1_comparison.png",
        )

    return {
        "train_files": train_files,
        "test_normal": test_normal,
        "test_anomaly": test_anomaly,
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    run_step1()
