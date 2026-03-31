"""
FFT解析 — 周波数スペクトルの可視化
CWRUベアリング振動データにFFTを適用し、周波数成分を可視化する
"""

import logging
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # GUI不要のバックエンド
import matplotlib.pyplot as plt

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 定数
SAMPLING_RATE = 12000  # 12kHz
DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def compute_fft(signal: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    """FFTを計算し、片側スペクトル（周波数・振幅）を返す"""
    n = len(signal)
    # FFT実行
    fft_vals = np.fft.fft(signal)
    # 片側スペクトル（正の周波数のみ）
    freqs = np.fft.fftfreq(n, d=1.0 / fs)[:n // 2]
    amplitude = 2.0 / n * np.abs(fft_vals[:n // 2])
    return freqs, amplitude


def plot_fft_spectrum(
    freqs: np.ndarray,
    amplitude: np.ndarray,
    title: str,
    output_path: Path,
    max_freq: float = 3000.0,
) -> None:
    """FFTスペクトルをグラフ出力する"""
    # 表示範囲を制限（max_freq Hz まで）
    mask = freqs <= max_freq

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(freqs[mask], amplitude[mask], linewidth=0.5, color='#2196F3')
    ax.set_xlabel('Frequency [Hz]', fontsize=12)
    ax.set_ylabel('Amplitude', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, max_freq)

    plt.tight_layout()
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"グラフ保存: {output_path.name}")


def analyze_single_file(csv_path: Path, label: str) -> None:
    """1ファイル分のFFT解析を実行する"""
    logger.info(f"FFT解析: {label}")

    df = pd.read_csv(csv_path)
    signal = df['acceleration'].values

    # 先頭2秒分（24,000サンプル）を使用
    n_samples = min(len(signal), SAMPLING_RATE * 2)
    signal_segment = signal[:n_samples]

    # FFT計算
    freqs, amplitude = compute_fft(signal_segment, SAMPLING_RATE)

    # グラフ出力
    output_path = OUTPUT_DIR / f"fft_{label}.png"
    plot_fft_spectrum(freqs, amplitude, f"FFT Spectrum - {label}", output_path)


def main() -> None:
    """全データのFFT解析を実行する"""
    logger.info("=== FFT解析開始 ===")

    labels = ["normal", "inner_race", "outer_race"]
    for label in labels:
        csv_path = DATA_DIR / f"{label}.csv"
        if csv_path.exists():
            analyze_single_file(csv_path, label)
        else:
            logger.warning(f"ファイルが見つかりません: {csv_path}")

    logger.info("=== FFT解析完了 ===")


if __name__ == "__main__":
    main()
