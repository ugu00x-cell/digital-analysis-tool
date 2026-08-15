"""
FEMTO/PRONOSTIA ベアリングデータ — 複数ベアリングの劣化パターン比較
Condition1の2本の訓練データを重ねてプロットし
「損傷モードが違うと劣化の形が違うか」を可視化する
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

# 定数
DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
FEATURE_DIR = DATA_DIR / "features"

CONDITION_INFO: dict[str, str] = {
    'Condition1': '1800rpm / 4kN',
    'Condition2': '1650rpm / 4.2kN',
    'Condition3': '1500rpm / 5kN',
}
BEARING_COLORS: dict[str, str] = {
    'Bearing1_1': '#4CAF50',
    'Bearing1_2': '#F44336',
    'Bearing2_1': '#2196F3',
    'Bearing2_2': '#FF9800',
    'Bearing3_1': '#9C27B0',
    'Bearing3_2': '#00BCD4',
}


def load_features(bearing_name: str) -> pd.DataFrame | None:
    """保存済み特徴量CSVを読み込む"""
    csv_path = FEATURE_DIR / f"features_{bearing_name}.csv"
    if not csv_path.exists():
        return None
    return pd.read_csv(csv_path)


def plot_condition1_comparison() -> None:
    """Condition1の2本の劣化パターンを重ねて比較する"""
    bearings = ['Bearing1_1', 'Bearing1_2']
    data: dict[str, pd.DataFrame] = {}
    for name in bearings:
        df = load_features(name)
        if df is not None:
            data[name] = df

    if len(data) < 2:
        logger.warning("Condition1の2本が揃いません")
        return

    features_to_plot = [
        ('h_rms', 'RMS'),
        ('h_kurtosis', 'Kurtosis'),
        ('h_envelope_rms', 'Envelope RMS'),
    ]

    fig, axes = plt.subplots(len(features_to_plot), 2, figsize=(16, 4 * len(features_to_plot)))

    for i, (col, label) in enumerate(features_to_plot):
        # 左列: 生のスナップショットインデックス
        for name, df in data.items():
            color = BEARING_COLORS.get(name, 'gray')
            axes[i, 0].plot(
                df['snapshot_idx'].values, df[col].values,
                linewidth=0.5, color=color, alpha=0.8, label=name
            )
        axes[i, 0].set_ylabel(label, fontsize=11)
        axes[i, 0].grid(True, alpha=0.3)
        axes[i, 0].legend(fontsize=9)

        # 右列: 寿命%に正規化
        for name, df in data.items():
            color = BEARING_COLORS.get(name, 'gray')
            life_pct = np.linspace(0, 100, len(df))
            axes[i, 1].plot(
                life_pct, df[col].values,
                linewidth=0.5, color=color, alpha=0.8, label=name
            )
        axes[i, 1].set_ylabel(label, fontsize=11)
        axes[i, 1].grid(True, alpha=0.3)
        axes[i, 1].legend(fontsize=9)

    axes[0, 0].set_title('Raw Snapshot Index', fontsize=13, fontweight='bold')
    axes[0, 1].set_title('Normalized by Life %', fontsize=13, fontweight='bold')
    axes[-1, 0].set_xlabel('Snapshot Index', fontsize=12)
    axes[-1, 1].set_xlabel('Life Percentage [%]', fontsize=12)

    fig.suptitle(
        'Bearing Degradation Comparison - Condition1 (1800rpm / 4kN)',
        fontsize=14, fontweight='bold', y=1.01
    )
    plt.tight_layout()

    output_path = OUTPUT_DIR / "bearing_comparison_cond1.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"Condition1比較保存: {output_path.name}")


def quantify_degradation_difference() -> None:
    """2本のベアリングの劣化特性を定量比較する"""
    logger.info("=== Condition1 劣化特性比較 ===")

    for name in ['Bearing1_1', 'Bearing1_2']:
        df = load_features(name)
        if df is None:
            continue

        n = len(df)
        n_normal = max(1, int(n * 0.10))
        n_late = max(1, int(n * 0.10))

        rms = df['h_rms'].values
        normal_mean = float(np.mean(rms[:n_normal]))
        late_mean = float(np.mean(rms[-n_late:]))
        rms_max = float(np.max(rms))

        # 劣化開始タイミング（正常+3σを超える初回）
        threshold = normal_mean + 3 * float(np.std(rms[:n_normal]))
        above = np.where(rms > threshold)[0]
        first_pct = above[0] / n * 100 if len(above) > 0 else -1

        logger.info(f"  {name}:")
        logger.info(f"    寿命: {n}スナップショット")
        logger.info(f"    正常期RMS: {normal_mean:.4f}")
        logger.info(f"    末期RMS(最後10%平均): {late_mean:.4f}")
        logger.info(f"    RMS最大: {rms_max:.4f} (正常比 {rms_max/normal_mean:.1f}倍)")
        if first_pct >= 0:
            logger.info(f"    劣化開始: 寿命の{first_pct:.1f}%地点")
        logger.info(f"    劣化速度指標: {(late_mean - normal_mean) / normal_mean:.2f}")


def plot_all_training_bearings() -> None:
    """全訓練ベアリング（6本）のRMSを寿命%で重ねてプロットする"""
    all_names = ['Bearing1_1', 'Bearing1_2', 'Bearing2_1',
                 'Bearing2_2', 'Bearing3_1', 'Bearing3_2']

    fig, ax = plt.subplots(figsize=(14, 7))

    for name in all_names:
        df = load_features(name)
        if df is None:
            continue
        color = BEARING_COLORS.get(name, 'gray')
        cond = 'Condition' + name.split('_')[0][-1]
        info = CONDITION_INFO.get(cond, '')
        life_pct = np.linspace(0, 100, len(df))
        ax.plot(
            life_pct, df['h_rms'].values,
            linewidth=0.5, color=color, alpha=0.8,
            label=f'{name} ({info})'
        )

    ax.set_xlabel('Life Percentage [%]', fontsize=12)
    ax.set_ylabel('RMS (Horizontal)', fontsize=12)
    ax.set_title(
        'All Training Bearings - RMS Degradation (Normalized by Life %)',
        fontsize=14, fontweight='bold'
    )
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = OUTPUT_DIR / "all_bearings_rms.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"全ベアリングRMS比較保存: {output_path.name}")


def main() -> None:
    """ベアリング比較の全工程を実行する"""
    logger.info("=== FEMTO ベアリング比較開始 ===")

    # Condition1の2本を詳細比較
    plot_condition1_comparison()

    # 定量比較
    quantify_degradation_difference()

    # 全訓練ベアリングのRMS比較
    plot_all_training_bearings()

    logger.info("=== ベアリング比較完了 ===")


if __name__ == "__main__":
    main()
