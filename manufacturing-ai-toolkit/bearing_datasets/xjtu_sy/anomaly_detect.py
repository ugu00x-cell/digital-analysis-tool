"""
XJTU-SYベアリングデータ — IsolationForest異常検知＋条件間転移検証
Condition1で学習したモデルをCondition2・3に適用し
「条件が変わると精度がどう落ちるか」を数値で出す
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
    'h_rms', 'h_kurtosis', 'h_crest_factor', 'h_peak_to_peak',
    'h_skewness', 'h_fft_energy',
]

# 正常区間の割合
NORMAL_RATIO = 0.20

# 条件情報
CONDITION_INFO: dict[str, str] = {
    'Condition1': '2100rpm / 12kN',
    'Condition2': '2250rpm / 11kN',
    'Condition3': '2400rpm / 10kN',
}


def load_first_bearing(condition: str) -> pd.DataFrame | None:
    """各Conditionの最初のベアリング特徴量を読み込む"""
    files = sorted(FEATURE_DIR.glob(f"features_{condition}_*.csv"))
    if not files:
        return None
    return pd.read_csv(files[0])


def train_isolation_forest(
    df: pd.DataFrame,
    condition: str,
) -> tuple[IsolationForest, StandardScaler]:
    """正常区間データでIsolationForestを学習する"""
    X = df[FEATURE_COLS].values
    n_normal = max(1, int(len(X) * NORMAL_RATIO))
    X_train = X[:n_normal]

    # 標準化
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    # IsolationForest学習
    model = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train_scaled)
    logger.info(f"{condition}: 学習データ={n_normal}スナップショット（最初{NORMAL_RATIO:.0%}）")

    return model, scaler


def evaluate_on_condition(
    model: IsolationForest,
    scaler: StandardScaler,
    df: pd.DataFrame,
    condition: str,
) -> dict[str, float]:
    """学習済みモデルを特定のConditionに適用して評価する"""
    X = df[FEATURE_COLS].values
    X_scaled = scaler.transform(X)

    scores = model.decision_function(X_scaled)
    predictions = model.predict(X_scaled)
    anomaly_labels = np.where(predictions == -1, 1, 0)

    # 評価指標
    n_total = len(anomaly_labels)
    n_anomaly = int(np.sum(anomaly_labels))
    anomaly_rate = n_anomaly / n_total

    # 最初の異常検出位置（寿命の何%地点か）
    first_idx = int(np.argmax(anomaly_labels)) if n_anomaly > 0 else -1
    first_pct = first_idx / n_total if first_idx >= 0 else -1.0

    # 後半50%での異常検出率（劣化期間の検出感度）
    n_late = n_total // 2
    late_anomaly_rate = float(np.mean(anomaly_labels[n_late:]))

    result = {
        'condition': condition,
        'n_snapshots': n_total,
        'n_anomaly': n_anomaly,
        'anomaly_rate': anomaly_rate,
        'first_detection_pct': first_pct,
        'late_half_detection_rate': late_anomaly_rate,
    }

    info = CONDITION_INFO.get(condition, '')
    logger.info(f"  {condition} ({info}):")
    logger.info(f"    異常検出: {n_anomaly}/{n_total} ({anomaly_rate:.1%})")
    if first_idx >= 0:
        logger.info(f"    初回検出: #{first_idx} ({first_pct:.1%}地点)")
    logger.info(f"    後半50%検出率: {late_anomaly_rate:.1%}")

    return result


def run_cross_condition_test() -> list[dict]:
    """条件間転移テストを実行する"""
    logger.info("=== 条件間転移テスト ===")

    # Condition1で学習
    df1 = load_first_bearing('Condition1')
    if df1 is None:
        logger.error("Condition1データなし")
        return []

    model, scaler = train_isolation_forest(df1, 'Condition1')

    # 各Conditionに適用
    results: list[dict] = []
    for cond in ['Condition1', 'Condition2', 'Condition3']:
        df = load_first_bearing(cond)
        if df is None:
            logger.warning(f"{cond}: データなし、スキップ")
            continue
        result = evaluate_on_condition(model, scaler, df, cond)
        results.append(result)

    return results


def run_self_trained_test() -> list[dict]:
    """各Condition自身のデータで学習・評価する（比較用）"""
    logger.info("=== 各Condition自己学習テスト ===")

    results: list[dict] = []
    for cond in ['Condition1', 'Condition2', 'Condition3']:
        df = load_first_bearing(cond)
        if df is None:
            continue

        model, scaler = train_isolation_forest(df, cond)
        result = evaluate_on_condition(model, scaler, df, cond)
        result['test_type'] = 'self'
        results.append(result)

    return results


def plot_cross_condition_results(
    cross_results: list[dict],
    self_results: list[dict],
) -> None:
    """条件間転移 vs 自己学習の検出率を比較するグラフ"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    conditions = [r['condition'] for r in cross_results]
    x = np.arange(len(conditions))
    width = 0.35

    # 左: 全体の異常検出率
    cross_rates = [r['anomaly_rate'] for r in cross_results]
    self_rates = [r['anomaly_rate'] for r in self_results]

    axes[0].bar(x - width / 2, cross_rates, width,
                label='Cross (Trained on Cond1)', color='#FF9800', alpha=0.8)
    axes[0].bar(x + width / 2, self_rates, width,
                label='Self (Trained on Own)', color='#4CAF50', alpha=0.8)

    axes[0].set_xticks(x)
    labels = [f'{c}\n{CONDITION_INFO.get(c, "")}' for c in conditions]
    axes[0].set_xticklabels(labels, fontsize=9)
    axes[0].set_ylabel('Anomaly Detection Rate', fontsize=12)
    axes[0].set_title('Overall Anomaly Detection Rate', fontsize=13, fontweight='bold')
    axes[0].legend(fontsize=10)
    axes[0].grid(True, alpha=0.3, axis='y')

    # 右: 後半50%の検出率（劣化期間の感度）
    cross_late = [r['late_half_detection_rate'] for r in cross_results]
    self_late = [r['late_half_detection_rate'] for r in self_results]

    axes[1].bar(x - width / 2, cross_late, width,
                label='Cross (Trained on Cond1)', color='#FF9800', alpha=0.8)
    axes[1].bar(x + width / 2, self_late, width,
                label='Self (Trained on Own)', color='#4CAF50', alpha=0.8)

    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, fontsize=9)
    axes[1].set_ylabel('Detection Rate (Late 50%)', fontsize=12)
    axes[1].set_title('Late-Phase Detection Rate', fontsize=13, fontweight='bold')
    axes[1].legend(fontsize=10)
    axes[1].grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    output_path = OUTPUT_DIR / "cross_condition_detection.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"条件間検出率比較保存: {output_path.name}")


def plot_anomaly_timelines(cross_results_raw: dict[str, np.ndarray]) -> None:
    """各Conditionの異常スコア時系列を並べて描画する"""
    n_conds = len(cross_results_raw)
    fig, axes = plt.subplots(n_conds, 1, figsize=(14, 3.5 * n_conds))
    if n_conds == 1:
        axes = [axes]

    colors = {'Condition1': '#4CAF50', 'Condition2': '#2196F3', 'Condition3': '#F44336'}

    for i, (cond, scores) in enumerate(sorted(cross_results_raw.items())):
        idx = np.arange(len(scores))
        life_pct = np.linspace(0, 100, len(scores))
        color = colors.get(cond, 'gray')
        info = CONDITION_INFO.get(cond, '')

        axes[i].plot(life_pct, scores, linewidth=0.8, color=color, alpha=0.7)
        axes[i].axhline(y=0, color='red', linestyle='--', linewidth=1.5)
        axes[i].set_ylabel('Anomaly Score', fontsize=10)
        axes[i].set_title(f'{cond} ({info}) - Model Trained on Condition1',
                         fontsize=11, fontweight='bold')
        axes[i].grid(True, alpha=0.3)

    axes[-1].set_xlabel('Life Percentage [%]', fontsize=12)
    fig.suptitle(
        'Cross-Condition Anomaly Score (Trained on Condition1)',
        fontsize=14, fontweight='bold', y=1.01
    )

    plt.tight_layout()
    output_path = OUTPUT_DIR / "cross_condition_timeline.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"条件間タイムライン保存: {output_path.name}")


def main() -> None:
    """異常検知＋条件間転移検証の全工程を実行する"""
    logger.info("=== XJTU-SY 異常検知開始 ===")

    # Condition1で学習し、全Conditionに適用
    df1 = load_first_bearing('Condition1')
    if df1 is None:
        logger.error("Condition1データなし。feature_extract.pyを先に実行してください。")
        return

    model, scaler = train_isolation_forest(df1, 'Condition1')

    # 異常スコアの時系列を取得（グラフ用）
    score_timelines: dict[str, np.ndarray] = {}
    for cond in ['Condition1', 'Condition2', 'Condition3']:
        df = load_first_bearing(cond)
        if df is None:
            continue
        X_scaled = scaler.transform(df[FEATURE_COLS].values)
        scores = model.decision_function(X_scaled)
        score_timelines[cond] = scores

    # 条件間タイムライン
    if score_timelines:
        plot_anomaly_timelines(score_timelines)

    # 条件間転移テスト
    cross_results = run_cross_condition_test()

    # 自己学習テスト（比較用）
    self_results = run_self_trained_test()

    # 比較グラフ
    if cross_results and self_results:
        plot_cross_condition_results(cross_results, self_results)

    # サマリ出力
    logger.info("=== 転移検証サマリ ===")
    for cr, sr in zip(cross_results, self_results):
        cond = cr['condition']
        logger.info(f"  {cond}: Cross={cr['anomaly_rate']:.1%} / Self={sr['anomaly_rate']:.1%}")
        drop = sr['anomaly_rate'] - cr['anomaly_rate']
        if abs(drop) > 0.05:
            logger.info(f"    → 差分 {drop:+.1%}（条件変動による影響あり）")
        else:
            logger.info(f"    → 差分 {drop:+.1%}（影響軽微）")

    logger.info("=== XJTU-SY 異常検知完了 ===")


if __name__ == "__main__":
    main()
