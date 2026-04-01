"""
FEMTO/PRONOSTIA ベアリングデータ — 劣化過程の可視化
Bearing1_1を中心にRMS・尖度・エンベロープRMSの時系列推移を描画し
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


def load_features(bearing_name: str) -> pd.DataFrame | None:
    """保存済み特徴量CSVを読み込む"""
    csv_path = FEATURE_DIR / f"features_{bearing_name}.csv"
    if not csv_path.exists():
        logger.warning(f"特徴量ファイルなし: {csv_path.name}")
        return None
    return pd.read_csv(csv_path)


def plot_degradation_timeline(
    df: pd.DataFrame,
    bearing_label: str,
    output_path: Path,
) -> None:
    """RMS・尖度・波高率・エンベロープRMSの時系列推移を4段で描画する"""
    features = [
        ('h_rms', 'RMS (Horizontal)', '#4CAF50'),
        ('h_kurtosis', 'Kurtosis (Horizontal)', '#FF9800'),
        ('h_crest_factor', 'Crest Factor (Horizontal)', '#2196F3'),
        ('h_envelope_rms', 'Envelope RMS (Horizontal)', '#E91E63'),
    ]

    fig, axes = plt.subplots(len(features), 1, figsize=(14, 3.2 * len(features)))
    idx = df['snapshot_idx'].values

    for i, (col, label, color) in enumerate(features):
        axes[i].plot(idx, df[col].values, linewidth=0.5, color=color)
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


def plot_rms_with_envelope(
    df: pd.DataFrame,
    bearing_label: str,
    output_path: Path,
) -> None:
    """RMSとエンベロープRMSを重ねて描画する（複合損傷の検出力比較）"""
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    idx = df['snapshot_idx'].values

    # 上段: 水平RMS vs エンベロープRMS
    axes[0].plot(idx, df['h_rms'].values, linewidth=0.8,
                 color='#4CAF50', label='RMS', alpha=0.8)
    axes[0].plot(idx, df['h_envelope_rms'].values, linewidth=0.8,
                 color='#E91E63', label='Envelope RMS', alpha=0.8)
    axes[0].set_ylabel('Amplitude', fontsize=12)
    axes[0].set_title(
        f'RMS vs Envelope RMS - {bearing_label} (Horizontal)',
        fontsize=14, fontweight='bold'
    )
    axes[0].legend(fontsize=10)
    axes[0].grid(True, alpha=0.3)

    # 下段: エンベロープRMS / RMS の比率（衝撃成分の指標）
    ratio = df['h_envelope_rms'].values / np.maximum(df['h_rms'].values, 1e-10)
    axes[1].plot(idx, ratio, linewidth=0.8, color='#9C27B0')
    axes[1].set_ylabel('Envelope/RMS Ratio', fontsize=12)
    axes[1].set_xlabel('Snapshot Index (Time →)', fontsize=12)
    axes[1].set_title('Envelope/RMS Ratio Trend', fontsize=12, fontweight='bold')
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"RMS-エンベロープ比較保存: {output_path.name}")


def analyze_pattern(df: pd.DataFrame, bearing_label: str) -> None:
    """NASAで見つけた「ピーク→フェードアウト→破損」パターンを定量分析する"""
    rms = df['h_rms'].values
    n = len(rms)

    # 正常期の基準（最初10%の平均・標準偏差）
    n_normal = max(1, int(n * 0.10))
    normal_mean = float(np.mean(rms[:n_normal]))
    normal_std = float(np.std(rms[:n_normal]))
    threshold = normal_mean + 3 * normal_std

    above = np.where(rms > threshold)[0]
    if len(above) == 0:
        logger.info(f"  {bearing_label}: 閾値超過なし（劣化が緩やか）")
        return

    first_exceed = above[0]
    logger.info(f"  {bearing_label}: 初回閾値超過 = #{first_exceed} ({first_exceed/n:.1%}地点)")
    logger.info(f"  正常期RMS平均 = {normal_mean:.4f}, 閾値(3σ) = {threshold:.4f}")
    logger.info(f"  末期RMS最大 = {np.max(rms):.4f} (正常比 {np.max(rms)/normal_mean:.1f}倍)")

    # フェードアウトパターン検出
    if len(above) > 10:
        gaps = np.diff(above)
        large_gaps = np.where(gaps > 3)[0]
        if len(large_gaps) > 0:
            logger.info(f"  → 「ピーク→フェードアウト」パターン検出の可能性あり（不連続{len(large_gaps)}箇所）")
        else:
            logger.info(f"  → 連続的な劣化パターン（フェードアウトなし）")


def main() -> None:
    """劣化可視化の全工程を実行する"""
    logger.info("=== FEMTO 劣化可視化開始 ===")

    # Bearing1_1 を主要分析対象に
    df = load_features('Bearing1_1')
    if df is None:
        logger.error("特徴量データなし。feature_extract.pyを先に実行してください。")
        return

    label = 'Condition1 Bearing1_1'
    logger.info(f"主要分析対象: {label} ({len(df)}スナップショット)")

    # 劣化タイムライン
    plot_degradation_timeline(df, label, OUTPUT_DIR / "degradation_timeline.png")

    # RMS vs エンベロープRMS
    plot_rms_with_envelope(df, label, OUTPUT_DIR / "rms_vs_envelope.png")

    # 全訓練ベアリングのパターン分析
    logger.info("=== パターン分析 ===")
    for bearing_name in ['Bearing1_1', 'Bearing1_2', 'Bearing2_1', 'Bearing2_2',
                         'Bearing3_1', 'Bearing3_2']:
        bdf = load_features(bearing_name)
        if bdf is not None:
            cond = 'Condition' + bearing_name.split('_')[0][-1]
            analyze_pattern(bdf, f"{cond} {bearing_name}")

    logger.info("=== 劣化可視化完了 ===")


if __name__ == "__main__":
    main()
