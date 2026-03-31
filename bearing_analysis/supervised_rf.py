"""
RandomForestによるベアリング故障3クラス分類（教師あり学習）
正常・内輪損傷・外輪損傷を分類し、IsolationForestとの精度比較を行う
"""

import logging
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, f1_score, classification_report, confusion_matrix
)
from sklearn.model_selection import train_test_split, cross_val_score
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

# セグメント長（0.1秒 = 1200サンプル）
SEGMENT_LENGTH = 1200

# 特徴量カラム名
FEATURE_COLS = [
    'rms', 'peak', 'mean', 'std', 'kurtosis', 'skewness',
    'crest_factor', 'mean_freq', 'fft_energy', 'peak_freq',
]

# クラス定義（3クラス分類）
CLASS_LABELS = {
    "normal": 0,
    "inner_race": 1,
    "outer_race": 2,
}
CLASS_NAMES = ["Normal", "Inner Race", "Outer Race"]
CLASS_COLORS = ["#4CAF50", "#F44336", "#FF9800"]


def extract_features_from_segment(segment: np.ndarray) -> dict[str, float]:
    """1セグメントから統計的特徴量を抽出する（anomaly_detect.pyと同一ロジック）"""
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
    total_fft = np.sum(fft_vals)
    mean_freq = np.sum(freqs * fft_vals) / total_fft if total_fft > 0 else 0

    # FFTエネルギー
    fft_energy = np.sum(fft_vals ** 2)

    # ピーク周波数
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
    all_features: list[dict] = []

    for label_name, label_id in CLASS_LABELS.items():
        csv_path = DATA_DIR / f"{label_name}.csv"
        if not csv_path.exists():
            logger.warning(f"ファイルなし: {csv_path}")
            continue

        df = pd.read_csv(csv_path)
        signal = df['acceleration'].values

        # セグメント分割して特徴量抽出
        n_segments = len(signal) // SEGMENT_LENGTH
        for i in range(n_segments):
            start = i * SEGMENT_LENGTH
            segment = signal[start:start + SEGMENT_LENGTH]
            features = extract_features_from_segment(segment)
            features['label'] = label_id
            features['fault_type'] = label_name
            all_features.append(features)

    feature_df = pd.DataFrame(all_features)
    logger.info(f"特徴量データセット: {feature_df.shape}")
    logger.info(f"クラス分布:\n{feature_df['fault_type'].value_counts().to_string()}")
    return feature_df


def train_random_forest(feature_df: pd.DataFrame) -> dict[str, float]:
    """RandomForestで3クラス分類を学習・評価する"""
    logger.info("=== RandomForest 学習開始 ===")

    X = feature_df[FEATURE_COLS].values
    y = feature_df['label'].values

    # 標準化
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # train/test = 8:2
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y
    )
    logger.info(f"学習データ: {len(X_train)}件, テストデータ: {len(X_test)}件")

    # RandomForest
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=None,
        min_samples_split=5,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    # 予測
    y_pred = model.predict(X_test)

    # 精度評価
    acc = accuracy_score(y_test, y_pred)
    f1_macro = f1_score(y_test, y_pred, average='macro')
    f1_weighted = f1_score(y_test, y_pred, average='weighted')

    logger.info(f"Accuracy:        {acc:.4f}")
    logger.info(f"F1 Score(macro): {f1_macro:.4f}")
    logger.info(f"F1 Score(weighted): {f1_weighted:.4f}")

    # 分類レポート
    report = classification_report(
        y_test, y_pred, target_names=CLASS_NAMES, digits=4
    )
    logger.info(f"Classification Report:\n{report}")

    # 混同行列
    cm = confusion_matrix(y_test, y_pred)
    logger.info(f"Confusion Matrix:\n{cm}")

    # 5-Fold CV も実行
    cv_scores = cross_val_score(model, X_scaled, y, cv=5, scoring='accuracy')
    logger.info(f"5-Fold CV Accuracy: {cv_scores.mean():.4f} (±{cv_scores.std():.4f})")

    # グラフ出力
    plot_confusion_matrix_3class(cm)
    plot_feature_importance(model)

    return {
        'accuracy': acc,
        'f1_macro': f1_macro,
        'f1_weighted': f1_weighted,
        'cv_mean': cv_scores.mean(),
        'cv_std': cv_scores.std(),
    }


def plot_confusion_matrix_3class(cm: np.ndarray) -> None:
    """3クラス混同行列をヒートマップで可視化する"""
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(cm, interpolation='nearest', cmap='Blues')
    ax.set_title('Confusion Matrix - Random Forest (3-class)',
                 fontsize=14, fontweight='bold')

    ax.set_xticks(range(3))
    ax.set_yticks(range(3))
    ax.set_xticklabels(CLASS_NAMES, fontsize=11)
    ax.set_yticklabels(CLASS_NAMES, fontsize=11)
    ax.set_xlabel('Predicted', fontsize=12)
    ax.set_ylabel('Actual', fontsize=12)

    # セル内に数値を表示
    for i in range(3):
        for j in range(3):
            color = 'white' if cm[i, j] > cm.max() / 2 else 'black'
            ax.text(j, i, str(cm[i, j]), ha='center', va='center',
                    fontsize=16, fontweight='bold', color=color)

    fig.colorbar(im)
    plt.tight_layout()

    output_path = OUTPUT_DIR / "rf_confusion_matrix.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"混同行列グラフ保存: {output_path.name}")


def plot_feature_importance(model: RandomForestClassifier) -> None:
    """RandomForestの特徴量重要度を可視化する"""
    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1]

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(FEATURE_COLS)))

    ax.barh(
        range(len(FEATURE_COLS)),
        importances[indices[::-1]],
        color=colors,
        edgecolor='white',
    )
    ax.set_yticks(range(len(FEATURE_COLS)))
    ax.set_yticklabels([FEATURE_COLS[i] for i in indices[::-1]], fontsize=11)
    ax.set_xlabel('Feature Importance', fontsize=12)
    ax.set_title('Random Forest - Feature Importance',
                 fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='x')
    plt.tight_layout()

    output_path = OUTPUT_DIR / "rf_feature_importance.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"特徴量重要度グラフ保存: {output_path.name}")


def plot_comparison_summary(rf_results: dict[str, float]) -> None:
    """IsolationForest vs RandomForest の比較グラフを作成する"""
    # IsolationForestの結果（前回の実行結果）
    if_results = {
        'accuracy': 0.7869,
        'f1': 0.7969,
        'method': 'IsolationForest\n(Unsupervised, 2-class)',
    }

    fig, ax = plt.subplots(figsize=(10, 6))

    # 比較する指標
    metrics = ['Accuracy', 'F1 Score']
    if_vals = [if_results['accuracy'], if_results['f1']]
    rf_vals = [rf_results['accuracy'], rf_results['f1_macro']]

    x = np.arange(len(metrics))
    width = 0.3

    bars1 = ax.bar(x - width / 2, if_vals, width,
                   label='IsolationForest (Unsupervised)', color='#FF9800', alpha=0.85)
    bars2 = ax.bar(x + width / 2, rf_vals, width,
                   label='RandomForest (Supervised)', color='#2196F3', alpha=0.85)

    # バーの上に数値を表示
    for bar in bars1:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f'{bar.get_height():.3f}', ha='center', va='bottom',
                fontsize=13, fontweight='bold')
    for bar in bars2:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f'{bar.get_height():.3f}', ha='center', va='bottom',
                fontsize=13, fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=13)
    ax.set_ylabel('Score', fontsize=12)
    ax.set_title('IsolationForest vs RandomForest - Performance Comparison',
                 fontsize=14, fontweight='bold')
    ax.legend(fontsize=11, loc='lower right')
    ax.set_ylim(0, 1.15)
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()

    output_path = OUTPUT_DIR / "model_comparison.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"モデル比較グラフ保存: {output_path.name}")


def print_comparison_summary(rf_results: dict[str, float]) -> None:
    """IsolationForest vs RandomForest の比較サマリーをログ出力する"""
    logger.info("=" * 60)
    logger.info("  モデル比較サマリー")
    logger.info("=" * 60)
    logger.info(f"{'指標':<20} {'IsolationForest':>16} {'RandomForest':>16}")
    logger.info("-" * 60)
    logger.info(f"{'学習方式':<20} {'教師なし(2クラス)':>16} {'教師あり(3クラス)':>16}")
    logger.info(f"{'Accuracy':<20} {'0.7869':>16} {rf_results['accuracy']:>16.4f}")
    logger.info(f"{'F1 Score':<20} {'0.7969':>16} {rf_results['f1_macro']:>16.4f}")
    logger.info(f"{'5-Fold CV':<20} {'N/A':>16} {rf_results['cv_mean']:>12.4f}±{rf_results['cv_std']:.4f}")
    logger.info("=" * 60)

    # 改善幅
    acc_diff = rf_results['accuracy'] - 0.7869
    f1_diff = rf_results['f1_macro'] - 0.7969
    logger.info(f"Accuracy改善: {acc_diff:+.4f}")
    logger.info(f"F1 Score改善: {f1_diff:+.4f}")


def main() -> None:
    """教師あり学習の全工程を実行する"""
    logger.info("=== RandomForest 3クラス分類 開始 ===")

    # 特徴量データセット作成
    feature_df = create_feature_dataset()
    if feature_df.empty:
        logger.error("データが空です。download_data.pyを先に実行してください。")
        return

    # RandomForest学習・評価
    rf_results = train_random_forest(feature_df)

    # IsolationForestとの比較
    plot_comparison_summary(rf_results)
    print_comparison_summary(rf_results)

    logger.info("=== RandomForest 3クラス分類 完了 ===")


if __name__ == "__main__":
    main()
