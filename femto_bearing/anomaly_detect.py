"""
FEMTO/PRONOSTIA ベアリングデータ — IsolationForest異常検知
XJTU-SYの教訓を踏まえて、正常区間の誤報率と末期区間の検出率を分離報告する

注意: ここで報告する数値は「異常検出率（全スナップショット中の異常判定割合）」
であり、精度（Accuracy）ではない。教師なし学習のため正解ラベルが存在しない。
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
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
DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
FEATURE_DIR = DATA_DIR / "features"

# 特徴量カラム（水平チャンネル）
FEATURE_COLS = [
    'h_rms', 'h_kurtosis', 'h_crest_factor',
    'h_envelope_rms', 'h_skewness', 'h_fft_energy',
]

NORMAL_RATIO = 0.20   # 正常区間（最初20%）
LATE_RATIO = 0.10     # 末期区間（最後10%）


def load_features(bearing_name: str) -> pd.DataFrame | None:
    """保存済み特徴量CSVを読み込む"""
    csv_path = FEATURE_DIR / f"features_{bearing_name}.csv"
    if not csv_path.exists():
        return None
    return pd.read_csv(csv_path)


def train_and_evaluate(
    df: pd.DataFrame,
    bearing_name: str,
) -> dict[str, float]:
    """正常区間で学習し、区間別の検出率を分離報告する"""
    X = df[FEATURE_COLS].values
    n_total = len(X)
    n_normal = max(1, int(n_total * NORMAL_RATIO))
    n_late = max(1, int(n_total * LATE_RATIO))

    # 標準化
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_train = X_scaled[:n_normal]

    # IsolationForest学習（正常データのみ）
    model = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train)

    # 全データの予測
    predictions = model.predict(X_scaled)
    anomaly_labels = np.where(predictions == -1, 1, 0)
    scores = model.decision_function(X_scaled)

    # 区間別の検出率（XJTU-SYの教訓：分離して報告）
    normal_zone = anomaly_labels[:n_normal]
    late_zone = anomaly_labels[-n_late:]
    mid_zone = anomaly_labels[n_normal:-n_late] if n_total > n_normal + n_late else np.array([])

    normal_false_alarm = float(np.mean(normal_zone))
    late_detection = float(np.mean(late_zone))
    overall_rate = float(np.mean(anomaly_labels))

    result = {
        'bearing': bearing_name,
        'n_snapshots': n_total,
        'overall_anomaly_rate': overall_rate,
        'normal_false_alarm_rate': normal_false_alarm,
        'late_detection_rate': late_detection,
    }

    logger.info(f"  {bearing_name} ({n_total}スナップショット):")
    logger.info(f"    全体異常検出率: {overall_rate:.1%}"
                f"（※精度ではなく異常判定割合）")
    logger.info(f"    正常区間(最初{NORMAL_RATIO:.0%})の誤報率: {normal_false_alarm:.1%}")
    logger.info(f"    末期区間(最後{LATE_RATIO:.0%})の検出率: {late_detection:.1%}")

    return result, scores, anomaly_labels


def plot_anomaly_timelines(
    results_data: dict[str, tuple],
) -> None:
    """各ベアリングの異常スコア時系列を並べて描画する"""
    n_bearings = len(results_data)
    fig, axes = plt.subplots(n_bearings, 1, figsize=(14, 3.5 * n_bearings))
    if n_bearings == 1:
        axes = [axes]

    colors = ['#4CAF50', '#F44336', '#2196F3', '#FF9800', '#9C27B0', '#00BCD4']

    for i, (name, (scores, labels)) in enumerate(sorted(results_data.items())):
        n = len(scores)
        life_pct = np.linspace(0, 100, n)
        color = colors[i % len(colors)]

        axes[i].plot(life_pct, scores, linewidth=0.5, color=color, alpha=0.7)
        axes[i].axhline(y=0, color='red', linestyle='--', linewidth=1.5)

        # 正常区間と末期区間をハイライト
        n_normal = int(n * NORMAL_RATIO)
        n_late_start = int(n * (1 - LATE_RATIO))
        axes[i].axvspan(0, NORMAL_RATIO * 100, alpha=0.1, color='green', label='Normal zone')
        axes[i].axvspan((1 - LATE_RATIO) * 100, 100, alpha=0.1, color='red', label='Late zone')

        axes[i].set_ylabel('Anomaly Score', fontsize=10)
        axes[i].set_title(f'{name}', fontsize=11, fontweight='bold')
        axes[i].grid(True, alpha=0.3)
        axes[i].legend(fontsize=8, loc='upper right')

    axes[-1].set_xlabel('Life Percentage [%]', fontsize=12)
    fig.suptitle(
        'Anomaly Score Timeline - All Training Bearings',
        fontsize=14, fontweight='bold', y=1.01
    )

    plt.tight_layout()
    output_path = OUTPUT_DIR / "anomaly_timeline.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"異常タイムライン保存: {output_path.name}")


def plot_zone_comparison(results: list[dict]) -> None:
    """正常区間誤報率と末期検出率を棒グラフで比較する"""
    fig, ax = plt.subplots(figsize=(12, 6))

    names = [r['bearing'] for r in results]
    x = np.arange(len(names))
    width = 0.35

    false_alarms = [r['normal_false_alarm_rate'] for r in results]
    detections = [r['late_detection_rate'] for r in results]

    ax.bar(x - width / 2, false_alarms, width,
           label=f'False Alarm (Normal {NORMAL_RATIO:.0%})',
           color='#FF9800', alpha=0.8)
    ax.bar(x + width / 2, detections, width,
           label=f'Detection (Late {LATE_RATIO:.0%})',
           color='#4CAF50', alpha=0.8)

    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=10, rotation=30, ha='right')
    ax.set_ylabel('Rate', fontsize=12)
    ax.set_title(
        'False Alarm Rate vs Late-Phase Detection Rate\n'
        '(Note: These are detection rates, not accuracy)',
        fontsize=13, fontweight='bold'
    )
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(0, 1.1)

    plt.tight_layout()
    output_path = OUTPUT_DIR / "zone_comparison.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"区間別比較保存: {output_path.name}")


def main() -> None:
    """異常検知の全工程を実行する"""
    logger.info("=== FEMTO 異常検知開始 ===")
    logger.info("※以下の数値は全て「異常検出率（異常判定割合）」であり精度ではありません")

    all_results: list[dict] = []
    timeline_data: dict[str, tuple] = {}

    for name in ['Bearing1_1', 'Bearing1_2', 'Bearing2_1',
                 'Bearing2_2', 'Bearing3_1', 'Bearing3_2']:
        df = load_features(name)
        if df is None:
            continue

        result, scores, labels = train_and_evaluate(df, name)
        all_results.append(result)
        timeline_data[name] = (scores, labels)

    if not all_results:
        logger.error("データなし。feature_extract.pyを先に実行してください。")
        return

    # 異常スコアタイムライン
    plot_anomaly_timelines(timeline_data)

    # 区間別比較
    plot_zone_comparison(all_results)

    # サマリテーブル
    logger.info("=== 異常検知サマリ ===")
    logger.info("（※全て異常検出率。精度ではない。正解ラベルなし教師なし学習）")
    logger.info(f"{'Bearing':<14} {'全体':>8} {'誤報率':>8} {'末期検出':>8}")
    logger.info("-" * 42)
    for r in all_results:
        logger.info(
            f"{r['bearing']:<14} "
            f"{r['overall_anomaly_rate']:>7.1%} "
            f"{r['normal_false_alarm_rate']:>7.1%} "
            f"{r['late_detection_rate']:>7.1%}"
        )

    logger.info("=== FEMTO 異常検知完了 ===")


if __name__ == "__main__":
    main()
