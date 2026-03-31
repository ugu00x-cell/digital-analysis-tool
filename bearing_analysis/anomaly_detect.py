"""
IsolationForestによるベアリング異常検知
振動信号から統計的特徴量を抽出し、異常検知モデルを構築・評価する
"""

import logging
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    accuracy_score, f1_score, classification_report, confusion_matrix
)
from sklearn.model_selection import train_test_split
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

SAMPLING_RATE = 12000
DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# セグメント長（0.1秒 = 1200サンプルごとに特徴量を抽出）
SEGMENT_LENGTH = 1200


def extract_features_from_segment(segment: np.ndarray) -> dict[str, float]:
    """1セグメントから統計的特徴量を抽出する"""
    # 時間領域の特徴量
    rms = np.sqrt(np.mean(segment ** 2))
    peak = np.max(np.abs(segment))
    mean_val = np.mean(segment)
    std_val = np.std(segment)
    kurtosis = sp_stats.kurtosis(segment)
    skewness = sp_stats.skew(segment)
    crest_factor = peak / rms if rms > 0 else 0

    # 周波数領域の特徴量
    fft_vals = np.abs(np.fft.fft(segment))[:len(segment) // 2]
    freqs = np.fft.fftfreq(len(segment), d=1.0 / SAMPLING_RATE)[:len(segment) // 2]

    # 平均周波数（重心周波数）
    mean_freq = np.sum(freqs * fft_vals) / np.sum(fft_vals) if np.sum(fft_vals) > 0 else 0

    # FFTのエネルギー
    fft_energy = np.sum(fft_vals ** 2)

    # ピーク周波数（最大振幅の周波数）
    peak_freq = freqs[np.argmax(fft_vals)] if len(fft_vals) > 0 else 0

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
    """全クラスの振動信号から特徴量データセットを作成する"""
    logger.info("特徴量抽出開始")

    labels_map = {
        "normal": 0,       # 正常 = 0（inlier）
        "inner_race": 1,   # 異常 = 1（outlier）
        "outer_race": 1,   # 異常 = 1（outlier）
    }
    fault_labels = {
        "normal": "normal",
        "inner_race": "inner_race",
        "outer_race": "outer_race",
    }

    all_features: list[dict] = []

    for label, binary_label in labels_map.items():
        csv_path = DATA_DIR / f"{label}.csv"
        if not csv_path.exists():
            logger.warning(f"ファイルなし: {csv_path}")
            continue

        df = pd.read_csv(csv_path)
        signal = df['acceleration'].values

        # セグメント分割して特徴量抽出
        n_segments = len(signal) // SEGMENT_LENGTH
        for i in range(n_segments):
            start = i * SEGMENT_LENGTH
            end = start + SEGMENT_LENGTH
            segment = signal[start:end]

            features = extract_features_from_segment(segment)
            features['label'] = binary_label          # 0=正常, 1=異常
            features['fault_type'] = fault_labels[label]  # 詳細ラベル
            all_features.append(features)

    feature_df = pd.DataFrame(all_features)
    logger.info(f"特徴量データセット: {feature_df.shape}")
    logger.info(f"クラス分布:\n{feature_df['fault_type'].value_counts().to_string()}")
    return feature_df


def train_isolation_forest(feature_df: pd.DataFrame) -> None:
    """IsolationForestで異常検知モデルを学習・評価する"""
    logger.info("=== IsolationForest 学習開始 ===")

    # 特徴量とラベルを分離
    feature_cols = [
        'rms', 'peak', 'mean', 'std', 'kurtosis', 'skewness',
        'crest_factor', 'mean_freq', 'fft_energy', 'peak_freq'
    ]
    X = feature_df[feature_cols].values
    y_true = feature_df['label'].values  # 0=正常, 1=異常

    # 標準化
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 学習データ・テストデータに分割
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y_true, test_size=0.3, random_state=42, stratify=y_true
    )

    # IsolationForest（正常データの割合を contamination で指定）
    # 異常データの割合を推定（実際の異常率に近い値を設定）
    anomaly_ratio = np.mean(y_train == 1)
    logger.info(f"学習データの異常率: {anomaly_ratio:.2%}")

    model = IsolationForest(
        n_estimators=200,
        contamination=anomaly_ratio,
        random_state=42,
        n_jobs=-1,
    )

    # 学習（IsolationForestは教師なしなので全データで学習）
    model.fit(X_train)

    # 予測（-1=異常, 1=正常 → 0=正常, 1=異常に変換）
    y_pred_raw = model.predict(X_test)
    y_pred = np.where(y_pred_raw == -1, 1, 0)

    # 精度評価
    evaluate_model(y_test, y_pred, feature_df, X_scaled, model, scaler, feature_cols)


def evaluate_model(
    y_test: np.ndarray,
    y_pred: np.ndarray,
    feature_df: pd.DataFrame,
    X_scaled: np.ndarray,
    model: IsolationForest,
    scaler: StandardScaler,
    feature_cols: list[str],
) -> None:
    """モデルの精度を評価して結果を出力する"""
    logger.info("=== 精度評価 ===")

    # 基本指標
    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    logger.info(f"Accuracy:  {acc:.4f}")
    logger.info(f"F1 Score:  {f1:.4f}")

    # 分類レポート
    report = classification_report(
        y_test, y_pred,
        target_names=['Normal', 'Anomaly'],
        digits=4
    )
    logger.info(f"Classification Report:\n{report}")

    # 混同行列
    cm = confusion_matrix(y_test, y_pred)
    logger.info(f"Confusion Matrix:\n{cm}")

    # 混同行列をグラフ出力
    plot_confusion_matrix(cm)

    # 異常スコア分布をグラフ出力
    plot_anomaly_scores(model, X_scaled, feature_df)

    # 特徴量重要度（各特徴量の異常スコアへの寄与を可視化）
    plot_feature_importance(feature_df, feature_cols)


def plot_confusion_matrix(cm: np.ndarray) -> None:
    """混同行列をヒートマップで可視化する"""
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(cm, interpolation='nearest', cmap='Blues')
    ax.set_title('Confusion Matrix - Isolation Forest', fontsize=14, fontweight='bold')

    labels = ['Normal', 'Anomaly']
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(labels, fontsize=12)
    ax.set_yticklabels(labels, fontsize=12)
    ax.set_xlabel('Predicted', fontsize=12)
    ax.set_ylabel('Actual', fontsize=12)

    # セル内に数値を表示
    for i in range(2):
        for j in range(2):
            color = 'white' if cm[i, j] > cm.max() / 2 else 'black'
            ax.text(j, i, str(cm[i, j]), ha='center', va='center',
                    fontsize=18, fontweight='bold', color=color)

    fig.colorbar(im)
    plt.tight_layout()

    output_path = OUTPUT_DIR / "confusion_matrix.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"混同行列グラフ保存: {output_path.name}")


def plot_anomaly_scores(
    model: IsolationForest,
    X_scaled: np.ndarray,
    feature_df: pd.DataFrame,
) -> None:
    """異常スコア分布をクラス別に可視化する"""
    scores = model.decision_function(X_scaled)

    fig, ax = plt.subplots(figsize=(10, 6))

    # クラス別にスコア分布をヒストグラム表示
    colors = {"normal": "#4CAF50", "inner_race": "#F44336", "outer_race": "#FF9800"}
    for fault_type, color in colors.items():
        mask = feature_df['fault_type'].values == fault_type
        ax.hist(scores[mask], bins=50, alpha=0.6,
                label=fault_type, color=color, edgecolor='white')

    ax.axvline(x=0, color='black', linestyle='--', linewidth=1.5, label='Threshold')
    ax.set_xlabel('Anomaly Score', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title('Anomaly Score Distribution by Class', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    output_path = OUTPUT_DIR / "anomaly_score_distribution.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"異常スコア分布グラフ保存: {output_path.name}")


def plot_feature_importance(
    feature_df: pd.DataFrame, feature_cols: list[str]
) -> None:
    """正常/異常の特徴量平均を比較して重要度を可視化する"""
    normal = feature_df[feature_df['label'] == 0][feature_cols].mean()
    anomaly = feature_df[feature_df['label'] == 1][feature_cols].mean()

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(feature_cols))
    width = 0.35

    # 標準化して比較しやすくする
    all_vals = pd.concat([normal, anomaly])
    max_val = all_vals.abs().max()
    normal_norm = normal / max_val
    anomaly_norm = anomaly / max_val

    ax.bar(x - width / 2, normal_norm, width, label='Normal', color='#4CAF50', alpha=0.8)
    ax.bar(x + width / 2, anomaly_norm, width, label='Anomaly', color='#F44336', alpha=0.8)

    ax.set_xticks(x)
    ax.set_xticklabels(feature_cols, rotation=45, ha='right', fontsize=10)
    ax.set_ylabel('Normalized Mean Value', fontsize=12)
    ax.set_title('Feature Comparison: Normal vs Anomaly', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()

    output_path = OUTPUT_DIR / "feature_comparison.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"特徴量比較グラフ保存: {output_path.name}")


def main() -> None:
    """異常検知の全工程を実行する"""
    logger.info("=== ベアリング異常検知開始 ===")

    # 特徴量データセット作成
    feature_df = create_feature_dataset()
    if feature_df.empty:
        logger.error("データが空です。download_data.pyを先に実行してください。")
        return

    # 特徴量CSVも保存（確認用）
    feature_csv = DATA_DIR / "features.csv"
    feature_df.to_csv(feature_csv, index=False)
    logger.info(f"特徴量CSV保存: {feature_csv.name}")

    # IsolationForest学習・評価
    train_isolation_forest(feature_df)

    logger.info("=== ベアリング異常検知完了 ===")


if __name__ == "__main__":
    main()
