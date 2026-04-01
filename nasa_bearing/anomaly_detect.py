"""
NASA IMS Bearing Dataset — IsolationForestによる異常検知
Bearing1（外輪故障）の全スナップショットから特徴量を抽出し、
初期データで学習した異常検知モデルで劣化進行を検出する
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
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
SAMPLING_RATE = 20000  # 20kHz
DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 正常区間の割合（最初20%を正常データとして学習に使用）
NORMAL_RATIO = 0.20


def extract_features_from_segment(segment: np.ndarray) -> dict[str, float]:
    """1セグメントから統計的特徴量を抽出する（CWRUと同じ10特徴量）"""
    # 時間領域の特徴量
    rms = float(np.sqrt(np.mean(segment ** 2)))
    peak = float(np.max(np.abs(segment)))
    mean_val = float(np.mean(segment))
    std_val = float(np.std(segment))
    kurtosis = float(sp_stats.kurtosis(segment))
    skewness = float(sp_stats.skew(segment))
    crest_factor = float(peak / rms) if rms > 0 else 0.0

    # 周波数領域の特徴量
    fft_vals = np.abs(np.fft.fft(segment))[:len(segment) // 2]
    freqs = np.fft.fftfreq(len(segment), d=1.0 / SAMPLING_RATE)[:len(segment) // 2]

    # 平均周波数（重心周波数）
    fft_sum = np.sum(fft_vals)
    mean_freq = float(np.sum(freqs * fft_vals) / fft_sum) if fft_sum > 0 else 0.0

    # FFTエネルギー
    fft_energy = float(np.sum(fft_vals ** 2))

    # ピーク周波数
    peak_freq = float(freqs[np.argmax(fft_vals)]) if len(fft_vals) > 0 else 0.0

    return {
        'rms': rms,
        'peak': peak,
        'mean': mean_val,
        'std': std_val,
        'kurtosis': kurtosis,
        'skewness': skewness,
        'crest_factor': crest_factor,
        'mean_freq': mean_freq,
        'fft_energy': fft_energy,
        'peak_freq': peak_freq,
    }


def create_feature_dataset() -> pd.DataFrame:
    """Bearing1の全スナップショットから特徴量を抽出する"""
    npz_path = DATA_DIR / "bearing1_all.npz"
    if not npz_path.exists():
        logger.error(f"データなし: {npz_path}（download_data.pyを先に実行してください）")
        return pd.DataFrame()

    logger.info("特徴量抽出開始")
    loaded = np.load(str(npz_path), allow_pickle=True)
    signals = loaded['signals']
    filenames = loaded['filenames']

    logger.info(f"スナップショット数: {len(signals)}, サンプル/ショット: {signals.shape[1]}")

    records: list[dict] = []
    for idx, (signal, fname) in enumerate(zip(signals, filenames)):
        features = extract_features_from_segment(signal)
        features['snapshot_idx'] = idx
        features['filename'] = str(fname)
        records.append(features)

    feature_df = pd.DataFrame(records)
    logger.info(f"特徴量データセット: {feature_df.shape}")
    return feature_df


def train_anomaly_detector(feature_df: pd.DataFrame) -> None:
    """初期データで学習し、全期間の異常スコアを算出する"""
    logger.info("=== IsolationForest 異常検知開始 ===")

    feature_cols = [
        'rms', 'peak', 'mean', 'std', 'kurtosis', 'skewness',
        'crest_factor', 'mean_freq', 'fft_energy', 'peak_freq'
    ]
    X = feature_df[feature_cols].values
    n_total = len(X)

    # 標準化
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 初期データ（最初20%）を正常区間として学習
    n_normal = int(n_total * NORMAL_RATIO)
    X_train = X_scaled[:n_normal]
    logger.info(f"学習データ: {n_normal}スナップショット（最初{NORMAL_RATIO:.0%}）")
    logger.info(f"全データ: {n_total}スナップショット")

    # IsolationForest学習（正常データのみで学習、contamination=低め）
    model = IsolationForest(
        n_estimators=200,
        contamination=0.05,  # 正常区間にもわずかな異常を許容
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train)

    # 全データの異常スコアを算出
    scores = model.decision_function(X_scaled)
    predictions = model.predict(X_scaled)
    # -1=異常, 1=正常 → 0=正常, 1=異常に変換
    anomaly_labels = np.where(predictions == -1, 1, 0)

    # 結果をDataFrameに追加
    feature_df['anomaly_score'] = scores
    feature_df['is_anomaly'] = anomaly_labels

    # 異常検出の統計
    n_anomaly = np.sum(anomaly_labels)
    first_anomaly_idx = np.argmax(anomaly_labels) if n_anomaly > 0 else -1
    logger.info(f"異常検出数: {n_anomaly}/{n_total} ({n_anomaly/n_total:.1%})")
    if first_anomaly_idx >= 0:
        logger.info(f"初回異常検出: スナップショット#{first_anomaly_idx} ({first_anomaly_idx/n_total:.1%}地点)")

    # 可視化
    plot_anomaly_timeline(feature_df)
    plot_feature_trends(feature_df, feature_cols)
    plot_anomaly_score_distribution(feature_df)

    # 特徴量CSV保存
    feature_csv = DATA_DIR / "features.csv"
    feature_df.to_csv(feature_csv, index=False)
    logger.info(f"特徴量CSV保存: {feature_csv.name}")


def plot_anomaly_timeline(feature_df: pd.DataFrame) -> None:
    """時系列の異常スコアと検出結果を可視化する"""
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    idx = feature_df['snapshot_idx'].values
    scores = feature_df['anomaly_score'].values
    anomaly_mask = feature_df['is_anomaly'].values == 1

    # 上段: 異常スコアの時系列推移
    axes[0].plot(idx, scores, linewidth=0.8, color='#2196F3', alpha=0.7)
    axes[0].axhline(y=0, color='red', linestyle='--', linewidth=1.5, label='Threshold')
    # 異常検出点をマーク
    if np.any(anomaly_mask):
        axes[0].scatter(
            idx[anomaly_mask], scores[anomaly_mask],
            color='#F44336', s=8, alpha=0.6, label='Anomaly', zorder=5
        )
    axes[0].set_ylabel('Anomaly Score', fontsize=12)
    axes[0].set_title(
        'Anomaly Score Timeline - Bearing1 (Outer Race Fault)',
        fontsize=14, fontweight='bold'
    )
    axes[0].legend(fontsize=11)
    axes[0].grid(True, alpha=0.3)

    # 下段: RMSの時系列推移（劣化トレンド確認）
    rms_vals = feature_df['rms'].values
    axes[1].plot(idx, rms_vals, linewidth=0.8, color='#4CAF50')
    if np.any(anomaly_mask):
        axes[1].scatter(
            idx[anomaly_mask], rms_vals[anomaly_mask],
            color='#F44336', s=8, alpha=0.6, zorder=5
        )
    axes[1].set_xlabel('Snapshot Index (Time →)', fontsize=12)
    axes[1].set_ylabel('RMS', fontsize=12)
    axes[1].set_title('RMS Trend - Bearing1', fontsize=12, fontweight='bold')
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = OUTPUT_DIR / "anomaly_timeline.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"異常タイムライン保存: {output_path.name}")


def plot_feature_trends(feature_df: pd.DataFrame, feature_cols: list[str]) -> None:
    """主要特徴量の時系列推移を可視化する"""
    # 可視化する特徴量を厳選
    key_features = ['rms', 'kurtosis', 'peak', 'fft_energy']
    colors = ['#4CAF50', '#FF9800', '#2196F3', '#9C27B0']

    fig, axes = plt.subplots(len(key_features), 1, figsize=(14, 3 * len(key_features)))
    idx = feature_df['snapshot_idx'].values

    for i, (feat, color) in enumerate(zip(key_features, colors)):
        vals = feature_df[feat].values
        axes[i].plot(idx, vals, linewidth=0.8, color=color)
        axes[i].set_ylabel(feat, fontsize=11)
        axes[i].set_title(f'{feat} Trend', fontsize=11, fontweight='bold')
        axes[i].grid(True, alpha=0.3)

    axes[-1].set_xlabel('Snapshot Index (Time →)', fontsize=12)
    fig.suptitle(
        'Feature Trends - Bearing1 Degradation',
        fontsize=14, fontweight='bold', y=1.01
    )
    plt.tight_layout()

    output_path = OUTPUT_DIR / "feature_trend.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"特徴量トレンド保存: {output_path.name}")


def plot_anomaly_score_distribution(feature_df: pd.DataFrame) -> None:
    """正常区間と異常区間の異常スコア分布を比較する"""
    n_total = len(feature_df)
    n_normal_zone = int(n_total * NORMAL_RATIO)

    scores_normal = feature_df['anomaly_score'].values[:n_normal_zone]
    scores_late = feature_df['anomaly_score'].values[n_normal_zone:]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(scores_normal, bins=40, alpha=0.6, color='#4CAF50',
            label=f'Early ({NORMAL_RATIO:.0%})', edgecolor='white')
    ax.hist(scores_late, bins=40, alpha=0.6, color='#F44336',
            label=f'Later ({1-NORMAL_RATIO:.0%})', edgecolor='white')

    ax.axvline(x=0, color='black', linestyle='--', linewidth=1.5, label='Threshold')
    ax.set_xlabel('Anomaly Score', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title(
        'Anomaly Score Distribution: Early vs Later Phase',
        fontsize=14, fontweight='bold'
    )
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = OUTPUT_DIR / "anomaly_score_distribution.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"異常スコア分布保存: {output_path.name}")


def main() -> None:
    """異常検知の全工程を実行する"""
    logger.info("=== NASA Bearing 異常検知開始 ===")

    # 特徴量データセット作成
    feature_df = create_feature_dataset()
    if feature_df.empty:
        logger.error("データが空です。download_data.pyを先に実行してください。")
        return

    # IsolationForest異常検知
    train_anomaly_detector(feature_df)

    logger.info("=== NASA Bearing 異常検知完了 ===")


if __name__ == "__main__":
    main()
