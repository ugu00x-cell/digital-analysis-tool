"""
NASA IMS Bearing Dataset — FFT解析
初期・中期・末期のスナップショットでFFTスペクトルを比較し、
ベアリング劣化の周波数変化を可視化する
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
SAMPLING_RATE = 20000  # 20kHz
DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def compute_fft(signal: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    """FFTを計算し、片側スペクトル（周波数・振幅）を返す"""
    n = len(signal)
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
    max_freq: float = 5000.0,
) -> None:
    """FFTスペクトルをグラフ出力する"""
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


def analyze_phase_snapshots() -> None:
    """初期・中期・末期のBearing1 FFTスペクトルを個別に出力する"""
    phases = ['early', 'mid', 'late']
    phase_labels = {'early': '初期 (Early)', 'mid': '中期 (Mid)', 'late': '末期 (Late)'}

    for phase in phases:
        csv_path = DATA_DIR / f"snapshot_{phase}.csv"
        if not csv_path.exists():
            logger.warning(f"スナップショットなし: {csv_path}")
            continue

        df = pd.read_csv(csv_path)
        signal = df['bearing1'].values

        freqs, amplitude = compute_fft(signal, SAMPLING_RATE)
        title = f"FFT Spectrum - Bearing1 {phase_labels[phase]}"
        output_path = OUTPUT_DIR / f"fft_{phase}.png"
        plot_fft_spectrum(freqs, amplitude, title, output_path)


def plot_degradation_comparison() -> None:
    """初期→中期→末期のFFTスペクトルを重ねて劣化進行を可視化する"""
    phases = ['early', 'mid', 'late']
    colors = {'early': '#4CAF50', 'mid': '#FF9800', 'late': '#F44336'}
    labels = {'early': 'Early (Normal)', 'mid': 'Mid', 'late': 'Late (Near Failure)'}

    fig, ax = plt.subplots(figsize=(14, 6))
    max_freq = 5000.0

    for phase in phases:
        csv_path = DATA_DIR / f"snapshot_{phase}.csv"
        if not csv_path.exists():
            continue

        df = pd.read_csv(csv_path)
        signal = df['bearing1'].values
        freqs, amplitude = compute_fft(signal, SAMPLING_RATE)

        mask = freqs <= max_freq
        ax.plot(
            freqs[mask], amplitude[mask],
            linewidth=0.8, color=colors[phase],
            label=labels[phase], alpha=0.8
        )

    ax.set_xlabel('Frequency [Hz]', fontsize=12)
    ax.set_ylabel('Amplitude', fontsize=12)
    ax.set_title(
        'FFT Spectrum Degradation - Bearing1 (Outer Race Fault)',
        fontsize=14, fontweight='bold'
    )
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, max_freq)

    plt.tight_layout()
    output_path = OUTPUT_DIR / "fft_degradation.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"劣化比較グラフ保存: {output_path.name}")


def plot_bearing_comparison() -> None:
    """末期スナップショットで4ベアリングのFFTを比較する"""
    csv_path = DATA_DIR / "snapshot_late.csv"
    if not csv_path.exists():
        logger.warning("末期スナップショットが見つかりません")
        return

    df = pd.read_csv(csv_path)
    bearing_cols = [c for c in df.columns if c.startswith('bearing')]

    colors = ['#F44336', '#2196F3', '#4CAF50', '#9C27B0']
    max_freq = 5000.0

    fig, axes = plt.subplots(len(bearing_cols), 1, figsize=(14, 3.5 * len(bearing_cols)))
    if len(bearing_cols) == 1:
        axes = [axes]

    for i, col in enumerate(bearing_cols):
        signal = df[col].values
        freqs, amplitude = compute_fft(signal, SAMPLING_RATE)
        mask = freqs <= max_freq

        axes[i].plot(
            freqs[mask], amplitude[mask],
            linewidth=0.5, color=colors[i % len(colors)]
        )
        axes[i].set_title(f'{col.title()} - Late Phase', fontsize=12, fontweight='bold')
        axes[i].set_ylabel('Amplitude', fontsize=10)
        axes[i].grid(True, alpha=0.3)
        axes[i].set_xlim(0, max_freq)

    axes[-1].set_xlabel('Frequency [Hz]', fontsize=12)
    plt.tight_layout()

    output_path = OUTPUT_DIR / "fft_bearing_comparison.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"ベアリング比較グラフ保存: {output_path.name}")


def main() -> None:
    """FFT解析の全工程を実行する"""
    logger.info("=== NASA Bearing FFT解析開始 ===")

    # 初期・中期・末期の個別FFT
    analyze_phase_snapshots()

    # 劣化進行のオーバーレイ比較
    plot_degradation_comparison()

    # 4ベアリング比較（末期）
    plot_bearing_comparison()

    logger.info("=== FFT解析完了 ===")


if __name__ == "__main__":
    main()
