"""
FEMTO/PRONOSTIA — 個体別学習 vs 共通モデルの比較検証
「最初のN%を個体ごとの正常パターン学習に使う」アプローチの有効性を
学習期間10%・20%・30%で定量的に検証する

注意: ここで報告する数値は全て「異常検出率（異常判定割合）」であり精度ではない
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

# 学習期間のバリエーション
TRAIN_RATIOS = [0.10, 0.20, 0.30]

# 評価区間
LATE_RATIO = 0.10  # 末期区間（最後10%）

# 訓練ベアリング名
BEARING_NAMES = [
    'Bearing1_1', 'Bearing1_2',
    'Bearing2_1', 'Bearing2_2',
    'Bearing3_1', 'Bearing3_2',
]


def load_features(bearing_name: str) -> pd.DataFrame | None:
    """保存済み特徴量CSVを読み込む"""
    csv_path = FEATURE_DIR / f"features_{bearing_name}.csv"
    if not csv_path.exists():
        return None
    return pd.read_csv(csv_path)


def evaluate_model(
    model: IsolationForest,
    scaler: StandardScaler,
    df: pd.DataFrame,
    train_ratio: float,
) -> dict[str, float]:
    """モデルを評価し、正常区間誤報率と末期検出率を返す"""
    X = df[FEATURE_COLS].values
    X_scaled = scaler.transform(X)
    n = len(X_scaled)

    predictions = model.predict(X_scaled)
    anomaly_labels = np.where(predictions == -1, 1, 0)

    # 正常区間 = 学習に使った区間（最初N%）
    n_normal = max(1, int(n * train_ratio))
    n_late = max(1, int(n * LATE_RATIO))

    normal_false_alarm = float(np.mean(anomaly_labels[:n_normal]))
    late_detection = float(np.mean(anomaly_labels[-n_late:]))

    return {
        'normal_false_alarm': normal_false_alarm,
        'late_detection': late_detection,
    }


def train_individual_model(
    df: pd.DataFrame,
    train_ratio: float,
) -> tuple[IsolationForest, StandardScaler]:
    """個体別モデル: そのベアリングの最初N%だけで学習する"""
    X = df[FEATURE_COLS].values
    n_train = max(1, int(len(X) * train_ratio))
    X_train = X[:n_train]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    model = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train_scaled)
    return model, scaler


def train_common_model(
    all_data: dict[str, pd.DataFrame],
    train_ratio: float,
) -> tuple[IsolationForest, StandardScaler]:
    """共通モデル: 全ベアリングの最初N%を合わせて学習する"""
    train_chunks: list[np.ndarray] = []
    for df in all_data.values():
        n_train = max(1, int(len(df) * train_ratio))
        train_chunks.append(df[FEATURE_COLS].values[:n_train])

    X_train = np.vstack(train_chunks)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    model = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train_scaled)
    return model, scaler


def run_comparison(
    all_data: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """全ベアリング × 全学習期間 × 個体別/共通モデルの比較を実行する"""
    records: list[dict] = []

    for ratio in TRAIN_RATIOS:
        logger.info(f"--- 学習期間: {ratio:.0%} ---")

        # 共通モデル学習
        common_model, common_scaler = train_common_model(all_data, ratio)

        for name, df in all_data.items():
            # 個体別モデル学習
            indiv_model, indiv_scaler = train_individual_model(df, ratio)

            # 個体別モデルで評価
            indiv_result = evaluate_model(indiv_model, indiv_scaler, df, ratio)

            # 共通モデルで評価
            common_result = evaluate_model(common_model, common_scaler, df, ratio)

            records.append({
                'bearing': name,
                'train_ratio': ratio,
                'indiv_false_alarm': indiv_result['normal_false_alarm'],
                'indiv_late_detect': indiv_result['late_detection'],
                'common_false_alarm': common_result['normal_false_alarm'],
                'common_late_detect': common_result['late_detection'],
            })

            logger.info(
                f"  {name}: "
                f"個体別[誤報{indiv_result['normal_false_alarm']:.1%} "
                f"検出{indiv_result['late_detection']:.1%}] "
                f"共通[誤報{common_result['normal_false_alarm']:.1%} "
                f"検出{common_result['late_detection']:.1%}]"
            )

    return pd.DataFrame(records)


def plot_comparison_by_ratio(results_df: pd.DataFrame) -> None:
    """学習期間ごとに個体別 vs 共通モデルを棒グラフで比較する"""
    fig, axes = plt.subplots(len(TRAIN_RATIOS), 2, figsize=(16, 5 * len(TRAIN_RATIOS)))

    for i, ratio in enumerate(TRAIN_RATIOS):
        subset = results_df[results_df['train_ratio'] == ratio]
        names = subset['bearing'].values
        x = np.arange(len(names))
        width = 0.35

        # 左: 誤報率
        axes[i, 0].bar(x - width / 2, subset['indiv_false_alarm'].values, width,
                       label='Individual', color='#4CAF50', alpha=0.8)
        axes[i, 0].bar(x + width / 2, subset['common_false_alarm'].values, width,
                       label='Common', color='#FF9800', alpha=0.8)
        axes[i, 0].set_xticks(x)
        axes[i, 0].set_xticklabels(names, fontsize=9, rotation=30, ha='right')
        axes[i, 0].set_ylabel('False Alarm Rate', fontsize=11)
        axes[i, 0].set_title(f'False Alarm (Train {ratio:.0%})', fontsize=12, fontweight='bold')
        axes[i, 0].legend(fontsize=9)
        axes[i, 0].grid(True, alpha=0.3, axis='y')
        axes[i, 0].set_ylim(0, 0.5)

        # 右: 末期検出率
        axes[i, 1].bar(x - width / 2, subset['indiv_late_detect'].values, width,
                       label='Individual', color='#4CAF50', alpha=0.8)
        axes[i, 1].bar(x + width / 2, subset['common_late_detect'].values, width,
                       label='Common', color='#FF9800', alpha=0.8)
        axes[i, 1].set_xticks(x)
        axes[i, 1].set_xticklabels(names, fontsize=9, rotation=30, ha='right')
        axes[i, 1].set_ylabel('Late Detection Rate', fontsize=11)
        axes[i, 1].set_title(f'Late Detection (Train {ratio:.0%})', fontsize=12, fontweight='bold')
        axes[i, 1].legend(fontsize=9)
        axes[i, 1].grid(True, alpha=0.3, axis='y')
        axes[i, 1].set_ylim(0, 1.15)

    fig.suptitle(
        'Individual vs Common Model Comparison\n'
        '(Note: These are detection rates, not accuracy)',
        fontsize=14, fontweight='bold', y=1.02
    )
    plt.tight_layout()
    output_path = OUTPUT_DIR / "individual_vs_common.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"比較グラフ保存: {output_path.name}")


def plot_bearing12_focus(results_df: pd.DataFrame) -> None:
    """Bearing1_1 vs Bearing1_2 の学習期間別比較（焦点分析）"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    ratios = np.array(TRAIN_RATIOS) * 100  # %表記
    width = 2.5

    for ax_idx, (bearing, title) in enumerate([
        ('Bearing1_1', 'Bearing1_1 (Gradual Degradation)'),
        ('Bearing1_2', 'Bearing1_2 (Sudden Failure)'),
    ]):
        subset = results_df[results_df['bearing'] == bearing]
        if subset.empty:
            continue

        # 末期検出率を学習期間別に比較
        axes[ax_idx].bar(
            ratios - width / 2, subset['indiv_late_detect'].values, width,
            label='Individual Model', color='#4CAF50', alpha=0.8
        )
        axes[ax_idx].bar(
            ratios + width / 2, subset['common_late_detect'].values, width,
            label='Common Model', color='#FF9800', alpha=0.8
        )

        axes[ax_idx].set_xlabel('Training Period [%]', fontsize=12)
        axes[ax_idx].set_ylabel('Late Detection Rate', fontsize=12)
        axes[ax_idx].set_title(title, fontsize=13, fontweight='bold')
        axes[ax_idx].set_xticks(ratios)
        axes[ax_idx].set_xticklabels([f'{int(r)}%' for r in ratios])
        axes[ax_idx].legend(fontsize=10)
        axes[ax_idx].grid(True, alpha=0.3, axis='y')
        axes[ax_idx].set_ylim(0, 1.15)

    fig.suptitle(
        'Effect of Individual Learning on Detection Rate\n'
        '(Note: Detection rates, not accuracy)',
        fontsize=14, fontweight='bold', y=1.02
    )
    plt.tight_layout()
    output_path = OUTPUT_DIR / "bearing12_focus.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"Bearing1_1 vs 1_2 焦点分析保存: {output_path.name}")


def plot_train_ratio_trend(results_df: pd.DataFrame) -> None:
    """学習期間を横軸にした末期検出率の推移（全ベアリング）"""
    fig, ax = plt.subplots(figsize=(12, 7))

    colors = {
        'Bearing1_1': '#4CAF50', 'Bearing1_2': '#F44336',
        'Bearing2_1': '#2196F3', 'Bearing2_2': '#FF9800',
        'Bearing3_1': '#9C27B0', 'Bearing3_2': '#00BCD4',
    }

    for name in BEARING_NAMES:
        subset = results_df[results_df['bearing'] == name]
        if subset.empty:
            continue
        color = colors.get(name, 'gray')

        # 個体別モデル（実線）
        ax.plot(
            subset['train_ratio'].values * 100,
            subset['indiv_late_detect'].values,
            marker='o', linewidth=2, color=color, alpha=0.8,
            label=f'{name} (Individual)'
        )
        # 共通モデル（破線）
        ax.plot(
            subset['train_ratio'].values * 100,
            subset['common_late_detect'].values,
            marker='s', linewidth=1.5, color=color, alpha=0.4,
            linestyle='--', label=f'{name} (Common)'
        )

    ax.set_xlabel('Training Period [%]', fontsize=12)
    ax.set_ylabel('Late-Phase Detection Rate (Last 10%)', fontsize=12)
    ax.set_title(
        'Detection Rate vs Training Period\n'
        '(Solid=Individual, Dashed=Common | Note: Detection rates, not accuracy)',
        fontsize=13, fontweight='bold'
    )
    ax.set_xticks([10, 20, 30])
    ax.legend(fontsize=8, ncol=2, loc='lower right')
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 1.1)

    plt.tight_layout()
    output_path = OUTPUT_DIR / "train_ratio_trend.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"学習期間トレンド保存: {output_path.name}")


def print_summary(results_df: pd.DataFrame) -> None:
    """結果サマリをログ出力する"""
    logger.info("=" * 60)
    logger.info("=== 個体別学習 vs 共通モデル サマリ ===")
    logger.info("※全て異常検出率（異常判定割合）。精度ではない。")
    logger.info("=" * 60)

    for ratio in TRAIN_RATIOS:
        subset = results_df[results_df['train_ratio'] == ratio]
        logger.info(f"\n--- 学習期間: {ratio:.0%} ---")
        logger.info(f"{'Bearing':<14} {'個体誤報':>8} {'個体検出':>8} "
                    f"{'共通誤報':>8} {'共通検出':>8} {'検出差分':>8}")
        logger.info("-" * 60)
        for _, row in subset.iterrows():
            diff = row['indiv_late_detect'] - row['common_late_detect']
            logger.info(
                f"{row['bearing']:<14} "
                f"{row['indiv_false_alarm']:>7.1%} "
                f"{row['indiv_late_detect']:>7.1%} "
                f"{row['common_false_alarm']:>7.1%} "
                f"{row['common_late_detect']:>7.1%} "
                f"{diff:>+7.1%}"
            )

    # Bearing1_2 に焦点
    logger.info("\n=== Bearing1_2（突然壊れるタイプ）の焦点分析 ===")
    b12 = results_df[results_df['bearing'] == 'Bearing1_2']
    for _, row in b12.iterrows():
        diff = row['indiv_late_detect'] - row['common_late_detect']
        direction = "改善" if diff > 0.01 else "悪化" if diff < -0.01 else "同等"
        logger.info(
            f"  学習{row['train_ratio']:.0%}: "
            f"個体別={row['indiv_late_detect']:.1%} "
            f"共通={row['common_late_detect']:.1%} "
            f"→ {direction}({diff:+.1%})"
        )


def main() -> None:
    """個体別学習 vs 共通モデルの全比較を実行する"""
    logger.info("=== 個体別学習 vs 共通モデル 検証開始 ===")
    logger.info("※以下の数値は全て「異常検出率（異常判定割合）」であり精度ではありません")

    # データ読み込み
    all_data: dict[str, pd.DataFrame] = {}
    for name in BEARING_NAMES:
        df = load_features(name)
        if df is not None:
            all_data[name] = df

    if not all_data:
        logger.error("データなし。feature_extract.pyを先に実行してください。")
        return

    # 比較実行
    results_df = run_comparison(all_data)

    # 結果CSV保存
    csv_path = OUTPUT_DIR / "individual_vs_common_results.csv"
    results_df.to_csv(csv_path, index=False)
    logger.info(f"結果CSV保存: {csv_path.name}")

    # 可視化
    plot_comparison_by_ratio(results_df)
    plot_bearing12_focus(results_df)
    plot_train_ratio_trend(results_df)

    # サマリ出力
    print_summary(results_df)

    logger.info("=== 検証完了 ===")


if __name__ == "__main__":
    main()
