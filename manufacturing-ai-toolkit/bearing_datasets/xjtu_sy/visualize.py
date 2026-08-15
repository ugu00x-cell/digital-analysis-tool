"""
XJTU-SYベアリングデータ — 劣化過程の可視化
Condition1 Bearing1_1を中心に、RMS・尖度の時系列推移を描画し
NASAで発見した「ピーク→フェードアウト→破損」パターンの有無を確認する
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


def load_features(condition: str, bearing: str) -> pd.DataFrame | None:
    """保存済み特徴量CSVを読み込む"""
    csv_path = FEATURE_DIR / f"features_{condition}_{bearing}.csv"
    if not csv_path.exists():
        logger.warning(f"特徴量ファイルなし: {csv_path.name}")
        return None
    return pd.read_csv(csv_path)


def plot_degradation_timeline(
    df: pd.DataFrame,
    bearing_label: str,
    output_path: Path,
) -> None:
    """RMS・尖度・波高率・P2Pの時系列推移を4段で描画する"""
    features = [
        ('h_rms', 'RMS (Horizontal)', '#4CAF50'),
        ('h_kurtosis', 'Kurtosis (Horizontal)', '#FF9800'),
        ('h_crest_factor', 'Crest Factor (Horizontal)', '#2196F3'),
        ('h_peak_to_peak', 'Peak-to-Peak (Horizontal)', '#9C27B0'),
    ]

    fig, axes = plt.subplots(len(features), 1, figsize=(14, 3.2 * len(features)))
    idx = df['snapshot_idx'].values

    for i, (col, label, color) in enumerate(features):
        axes[i].plot(idx, df[col].values, linewidth=0.8, color=color)
        axes[i].set_ylabel(label, fontsize=10)
        axes[i].grid(True, alpha=0.3)

    axes[0].set_title(
        f'Degradation Timeline - {bearing_label}',
        fontsize=14, fontweight='bold'
    )
    axes[-1].set_xlabel('Snapshot Index (Time →)', fontsize=12)

    plt.tight_layout()
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"劣化タイムライン保存: {output_path.name}")


def plot_rms_with_phases(
    df: pd.DataFrame,
    bearing_label: str,
    output_path: Path,
) -> None:
    """RMS推移に劣化フェーズの注釈を付けて描画する"""
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    idx = df['snapshot_idx'].values

    # 上段: 水平RMS
    axes[0].plot(idx, df['h_rms'].values, linewidth=0.8, color='#4CAF50')
    axes[0].set_ylabel('RMS (Horizontal)', fontsize=12)
    axes[0].set_title(
        f'RMS Degradation with Phase Analysis - {bearing_label}',
        fontsize=14, fontweight='bold'
    )
    axes[0].grid(True, alpha=0.3)

    # 下段: 垂直RMS
    axes[1].plot(idx, df['v_rms'].values, linewidth=0.8, color='#2196F3')
    axes[1].set_ylabel('RMS (Vertical)', fontsize=12)
    axes[1].set_xlabel('Snapshot Index (Time →)', fontsize=12)
    axes[1].grid(True, alpha=0.3)

    # 移動平均で劣化トレンドを可視化
    window = max(5, len(df) // 20)
    for ax, col, color in [
        (axes[0], 'h_rms', '#F44336'),
        (axes[1], 'v_rms', '#F44336'),
    ]:
        ma = df[col].rolling(window=window, center=True).mean()
        ax.plot(idx, ma.values, linewidth=2.0, color=color,
                alpha=0.7, label=f'Moving Avg (w={window})')
        ax.legend(fontsize=10)

    plt.tight_layout()
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"RMSフェーズ解析保存: {output_path.name}")


def plot_kurtosis_vs_rms(
    df: pd.DataFrame,
    bearing_label: str,
    output_path: Path,
) -> None:
    """尖度とRMSの散布図で劣化フェーズを色分けする"""
    n = len(df)
    # 時間経過で色分け（初期=緑、中期=黄、末期=赤）
    colors = np.linspace(0, 1, n)

    fig, ax = plt.subplots(figsize=(10, 8))
    scatter = ax.scatter(
        df['h_rms'].values, df['h_kurtosis'].values,
        c=colors, cmap='RdYlGn_r', s=15, alpha=0.7
    )
    cbar = fig.colorbar(scatter, ax=ax)
    cbar.set_label('Time Progression (0=Early, 1=Late)', fontsize=11)

    ax.set_xlabel('RMS (Horizontal)', fontsize=12)
    ax.set_ylabel('Kurtosis (Horizontal)', fontsize=12)
    ax.set_title(
        f'Kurtosis vs RMS Phase Diagram - {bearing_label}',
        fontsize=14, fontweight='bold'
    )
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"尖度-RMS散布図保存: {output_path.name}")


def analyze_pattern(df: pd.DataFrame, bearing_label: str) -> None:
    """NASAで見つけた「ピーク→フェードアウト→破損」パターンを定量分析する"""
    rms = df['h_rms'].values
    n = len(rms)

    # 正常期の基準（最初10%の平均・標準偏差）
    n_normal = max(1, int(n * 0.10))
    normal_mean = np.mean(rms[:n_normal])
    normal_std = np.std(rms[:n_normal])
    threshold = normal_mean + 3 * normal_std

    # 閾値を超えたインデックスを検出
    above = np.where(rms > threshold)[0]
    if len(above) == 0:
        logger.info(f"  {bearing_label}: 閾値超過なし（劣化が緩やか）")
        return

    first_exceed = above[0]
    logger.info(f"  {bearing_label}: 初回閾値超過 = #{first_exceed} ({first_exceed/n:.1%}地点)")
    logger.info(f"  正常期RMS平均 = {normal_mean:.4f}, 閾値(3σ) = {threshold:.4f}")
    logger.info(f"  末期RMS最大 = {np.max(rms):.4f} (正常比 {np.max(rms)/normal_mean:.1f}倍)")

    # フェードアウトパターンの検出: 一度上がって下がって再上昇
    if len(above) > 10:
        gaps = np.diff(above)
        large_gaps = np.where(gaps > 3)[0]
        if len(large_gaps) > 0:
            logger.info(f"  → 「ピーク→フェードアウト」パターン検出の可能性あり（不連続{len(large_gaps)}箇所）")
        else:
            logger.info(f"  → 連続的な劣化パターン（フェードアウトなし）")


def main() -> None:
    """劣化可視化の全工程を実行する"""
    logger.info("=== XJTU-SY 劣化可視化開始 ===")

    # Condition1 Bearing1_1 を主要分析対象にする
    # ベアリング名のパターンを自動検出
    feature_files = list(FEATURE_DIR.glob("features_Condition1_*.csv"))
    if not feature_files:
        logger.error("特徴量データなし。feature_extract.pyを先に実行してください。")
        return

    # Condition1の最初のベアリングを主要分析対象に
    feature_files.sort()
    first_file = feature_files[0]
    # ファイル名から Condition と Bearing 名を抽出
    parts = first_file.stem.replace("features_", "").split("_", 1)
    cond_name = parts[0]
    bearing_name = parts[1] if len(parts) > 1 else "unknown"

    df = pd.read_csv(first_file)
    label = f"{cond_name} {bearing_name}"
    logger.info(f"主要分析対象: {label} ({len(df)}スナップショット)")

    # 劣化タイムライン（4特徴量）
    plot_degradation_timeline(df, label, OUTPUT_DIR / "degradation_timeline.png")

    # RMS + 移動平均（水平・垂直）
    plot_rms_with_phases(df, label, OUTPUT_DIR / "rms_phase_analysis.png")

    # 尖度-RMS散布図
    plot_kurtosis_vs_rms(df, label, OUTPUT_DIR / "kurtosis_vs_rms.png")

    # パターン分析（全Condition1ベアリング）
    logger.info("=== パターン分析 ===")
    for ff in feature_files:
        parts = ff.stem.replace("features_", "").split("_", 1)
        b_name = parts[1] if len(parts) > 1 else "unknown"
        b_df = pd.read_csv(ff)
        analyze_pattern(b_df, f"Condition1 {b_name}")

    logger.info("=== 劣化可視化完了 ===")


if __name__ == "__main__":
    main()
