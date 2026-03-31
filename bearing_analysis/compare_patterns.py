"""
振動パターン比較 — 正常・内輪損傷・外輪損傷の違いを可視化
時間波形とFFTスペクトルを並べて3クラスを比較する
"""

import logging
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
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

SAMPLING_RATE = 12000
DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 表示用ラベルと色
LABELS = {
    "normal": {"name": "Normal", "color": "#4CAF50"},
    "inner_race": {"name": "Inner Race Fault", "color": "#F44336"},
    "outer_race": {"name": "Outer Race Fault", "color": "#FF9800"},
}


def compute_fft(signal: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    """FFTを計算し、片側スペクトルを返す"""
    n = len(signal)
    fft_vals = np.fft.fft(signal)
    freqs = np.fft.fftfreq(n, d=1.0 / fs)[:n // 2]
    amplitude = 2.0 / n * np.abs(fft_vals[:n // 2])
    return freqs, amplitude


def load_signals() -> dict[str, np.ndarray]:
    """3クラスの加速度信号を読み込む"""
    signals: dict[str, np.ndarray] = {}
    for label in LABELS:
        csv_path = DATA_DIR / f"{label}.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            signals[label] = df['acceleration'].values
            logger.info(f"読み込み: {label} ({len(signals[label])} サンプル)")
        else:
            logger.warning(f"ファイルなし: {csv_path}")
    return signals


def plot_time_comparison(signals: dict[str, np.ndarray]) -> None:
    """時間波形の3クラス比較グラフ"""
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    # 先頭0.1秒分を表示（細かい振動パターンが見える範囲）
    n_show = int(SAMPLING_RATE * 0.1)

    for ax, (label, signal) in zip(axes, signals.items()):
        info = LABELS[label]
        t = np.arange(n_show) / SAMPLING_RATE * 1000  # ミリ秒
        ax.plot(t, signal[:n_show], linewidth=0.5, color=info["color"])
        ax.set_ylabel('Accel [G]', fontsize=11)
        ax.set_title(info["name"], fontsize=13, fontweight='bold', color=info["color"])
        ax.grid(True, alpha=0.3)
        # 振幅の統計情報を表示
        seg = signal[:n_show]
        ax.text(0.98, 0.95, f'RMS={np.sqrt(np.mean(seg**2)):.4f}',
                transform=ax.transAxes, ha='right', va='top', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    axes[-1].set_xlabel('Time [ms]', fontsize=12)
    fig.suptitle('Time Domain Comparison - Bearing Vibration', fontsize=15, fontweight='bold')
    plt.tight_layout()

    output_path = OUTPUT_DIR / "compare_time_domain.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"時間波形比較グラフ保存: {output_path.name}")


def plot_fft_comparison(signals: dict[str, np.ndarray]) -> None:
    """FFTスペクトルの3クラス比較グラフ"""
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    # 先頭2秒分でFFT
    n_fft = SAMPLING_RATE * 2

    for ax, (label, signal) in zip(axes, signals.items()):
        info = LABELS[label]
        seg = signal[:n_fft]
        freqs, amp = compute_fft(seg, SAMPLING_RATE)

        # 3000Hz以下を表示
        mask = freqs <= 3000
        ax.plot(freqs[mask], amp[mask], linewidth=0.5, color=info["color"])
        ax.set_ylabel('Amplitude', fontsize=11)
        ax.set_title(info["name"], fontsize=13, fontweight='bold', color=info["color"])
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 3000)

    axes[-1].set_xlabel('Frequency [Hz]', fontsize=12)
    fig.suptitle('Frequency Domain Comparison - Bearing Vibration', fontsize=15, fontweight='bold')
    plt.tight_layout()

    output_path = OUTPUT_DIR / "compare_fft_spectrum.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"FFT比較グラフ保存: {output_path.name}")


def plot_overlay_fft(signals: dict[str, np.ndarray]) -> None:
    """FFTスペクトルを1つのグラフに重ねて表示"""
    fig, ax = plt.subplots(figsize=(14, 6))
    n_fft = SAMPLING_RATE * 2

    for label, signal in signals.items():
        info = LABELS[label]
        seg = signal[:n_fft]
        freqs, amp = compute_fft(seg, SAMPLING_RATE)
        mask = freqs <= 3000
        ax.plot(freqs[mask], amp[mask], linewidth=0.7,
                color=info["color"], label=info["name"], alpha=0.8)

    ax.set_xlabel('Frequency [Hz]', fontsize=12)
    ax.set_ylabel('Amplitude', fontsize=12)
    ax.set_title('FFT Overlay - Normal vs Inner Race vs Outer Race',
                 fontsize=14, fontweight='bold')
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 3000)
    plt.tight_layout()

    output_path = OUTPUT_DIR / "compare_fft_overlay.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"FFTオーバーレイグラフ保存: {output_path.name}")


def print_statistics(signals: dict[str, np.ndarray]) -> None:
    """3クラスの基本統計量を表示する"""
    logger.info("--- 基本統計量 ---")
    for label, signal in signals.items():
        info = LABELS[label]
        rms = np.sqrt(np.mean(signal ** 2))
        peak = np.max(np.abs(signal))
        std = np.std(signal)
        kurtosis = np.mean((signal - np.mean(signal)) ** 4) / std ** 4
        logger.info(
            f"  {info['name']:20s} | "
            f"RMS={rms:.4f} | Peak={peak:.4f} | "
            f"Std={std:.4f} | Kurtosis={kurtosis:.2f}"
        )


def main() -> None:
    """振動パターン比較を実行する"""
    logger.info("=== 振動パターン比較開始 ===")

    signals = load_signals()
    if len(signals) < 3:
        logger.error("3クラス分のデータが必要です。download_data.pyを先に実行してください。")
        return

    # 基本統計量の表示
    print_statistics(signals)

    # 時間波形比較
    plot_time_comparison(signals)

    # FFTスペクトル比較（個別）
    plot_fft_comparison(signals)

    # FFTオーバーレイ
    plot_overlay_fft(signals)

    logger.info("=== 振動パターン比較完了 ===")


if __name__ == "__main__":
    main()
