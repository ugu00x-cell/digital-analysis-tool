"""
XJTU-SYベアリングデータ — 条件間比較（このデータセットの核心）
Condition1・2・3のBearing_1のRMS時系列を重ねて
「正常時のRMSが条件によってどれだけ違うか」を定量化する
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

# 条件ラベル
CONDITION_INFO: dict[str, str] = {
    'Condition1': '2100rpm / 12kN',
    'Condition2': '2250rpm / 11kN',
    'Condition3': '2400rpm / 10kN',
}
CONDITION_COLORS: dict[str, str] = {
    'Condition1': '#4CAF50',
    'Condition2': '#2196F3',
    'Condition3': '#F44336',
}


def find_first_bearing(condition: str) -> pd.DataFrame | None:
    """各Conditionの最初のベアリングの特徴量を読み込む"""
    pattern = f"features_{condition}_*.csv"
    files = sorted(FEATURE_DIR.glob(pattern))
    if not files:
        logger.warning(f"{condition}: 特徴量ファイルなし")
        return None
    df = pd.read_csv(files[0])
    bearing_name = files[0].stem.replace(f"features_{condition}_", "")
    logger.info(f"{condition} {bearing_name}: {len(df)}スナップショット")
    return df


def plot_rms_overlay(cond_data: dict[str, pd.DataFrame]) -> None:
    """3条件のRMS時系列を正規化して重ねてプロットする"""
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))

    # 上段: 生の時系列（スナップショットインデックス）
    for cond_name, df in cond_data.items():
        color = CONDITION_COLORS.get(cond_name, 'gray')
        info = CONDITION_INFO.get(cond_name, '')
        axes[0].plot(
            df['snapshot_idx'].values, df['h_rms'].values,
            linewidth=0.8, color=color, alpha=0.8,
            label=f'{cond_name} ({info})'
        )

    axes[0].set_xlabel('Snapshot Index', fontsize=12)
    axes[0].set_ylabel('RMS (Horizontal)', fontsize=12)
    axes[0].set_title(
        'RMS Timeline Comparison Across Conditions (Raw)',
        fontsize=14, fontweight='bold'
    )
    axes[0].legend(fontsize=10)
    axes[0].grid(True, alpha=0.3)

    # 下段: 寿命を0〜100%に正規化して重ねる
    for cond_name, df in cond_data.items():
        color = CONDITION_COLORS.get(cond_name, 'gray')
        info = CONDITION_INFO.get(cond_name, '')
        n = len(df)
        life_pct = np.linspace(0, 100, n)
        axes[1].plot(
            life_pct, df['h_rms'].values,
            linewidth=0.8, color=color, alpha=0.8,
            label=f'{cond_name} ({info})'
        )

    axes[1].set_xlabel('Life Percentage [%]', fontsize=12)
    axes[1].set_ylabel('RMS (Horizontal)', fontsize=12)
    axes[1].set_title(
        'RMS Timeline Comparison (Normalized by Life %)',
        fontsize=14, fontweight='bold'
    )
    axes[1].legend(fontsize=10)
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = OUTPUT_DIR / "cross_condition_rms.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"条件間RMS比較保存: {output_path.name}")


def quantify_normal_baseline(cond_data: dict[str, pd.DataFrame]) -> None:
    """各条件の正常時RMS（最初10%）を定量比較する"""
    logger.info("=== 正常時ベースライン比較 ===")

    baselines: dict[str, dict[str, float]] = {}
    for cond_name, df in cond_data.items():
        n = len(df)
        n_normal = max(1, int(n * 0.10))
        h_rms_normal = df['h_rms'].values[:n_normal]

        mean_val = float(np.mean(h_rms_normal))
        std_val = float(np.std(h_rms_normal))
        info = CONDITION_INFO.get(cond_name, '')

        baselines[cond_name] = {'mean': mean_val, 'std': std_val}
        logger.info(f"  {cond_name} ({info}): RMS平均={mean_val:.4f}, σ={std_val:.4f}")

    # 条件間のRMS比率を計算
    cond_names = sorted(baselines.keys())
    if len(cond_names) >= 2:
        logger.info("=== 条件間RMS比率 ===")
        base = baselines[cond_names[0]]['mean']
        for cn in cond_names:
            ratio = baselines[cn]['mean'] / base if base > 0 else 0
            logger.info(f"  {cn} / {cond_names[0]} = {ratio:.2f}倍")


def plot_normal_baseline_comparison(cond_data: dict[str, pd.DataFrame]) -> None:
    """正常時のRMS分布を箱ひげ図で比較する"""
    fig, ax = plt.subplots(figsize=(10, 6))

    box_data: list[np.ndarray] = []
    labels: list[str] = []
    colors: list[str] = []

    for cond_name, df in sorted(cond_data.items()):
        n = len(df)
        n_normal = max(1, int(n * 0.10))
        h_rms_normal = df['h_rms'].values[:n_normal]
        box_data.append(h_rms_normal)
        info = CONDITION_INFO.get(cond_name, '')
        labels.append(f'{cond_name}\n{info}')
        colors.append(CONDITION_COLORS.get(cond_name, 'gray'))

    bp = ax.boxplot(box_data, labels=labels, patch_artist=True, widths=0.5)
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.5)

    ax.set_ylabel('RMS (Horizontal)', fontsize=12)
    ax.set_title(
        'Normal Baseline RMS Distribution by Condition (First 10%)',
        fontsize=14, fontweight='bold'
    )
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    output_path = OUTPUT_DIR / "baseline_comparison.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"ベースライン比較保存: {output_path.name}")


def plot_threshold_analysis(cond_data: dict[str, pd.DataFrame]) -> None:
    """条件別の3σ閾値と末期RMSの関係を可視化する"""
    fig, ax = plt.subplots(figsize=(12, 6))

    x_positions = np.arange(len(cond_data))
    width = 0.25
    cond_names = sorted(cond_data.keys())

    means, thresholds, maxvals = [], [], []
    for cond_name in cond_names:
        df = cond_data[cond_name]
        n = len(df)
        n_normal = max(1, int(n * 0.10))
        rms_normal = df['h_rms'].values[:n_normal]
        m = float(np.mean(rms_normal))
        s = float(np.std(rms_normal))
        means.append(m)
        thresholds.append(m + 3 * s)
        maxvals.append(float(df['h_rms'].max()))

    ax.bar(x_positions - width, means, width, label='Normal Mean',
           color='#4CAF50', alpha=0.8)
    ax.bar(x_positions, thresholds, width, label='Threshold (3σ)',
           color='#FF9800', alpha=0.8)
    ax.bar(x_positions + width, maxvals, width, label='Max RMS (Failure)',
           color='#F44336', alpha=0.8)

    ax.set_xticks(x_positions)
    labels = [f'{cn}\n{CONDITION_INFO.get(cn, "")}' for cn in cond_names]
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel('RMS Value', fontsize=12)
    ax.set_title(
        'Threshold Analysis: Normal vs 3σ Threshold vs Failure',
        fontsize=14, fontweight='bold'
    )
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    output_path = OUTPUT_DIR / "threshold_analysis.png"
    fig.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    logger.info(f"閾値分析保存: {output_path.name}")


def main() -> None:
    """条件間比較の全工程を実行する"""
    logger.info("=== XJTU-SY 条件間比較開始 ===")

    # 各Conditionの最初のベアリングを読み込む
    cond_data: dict[str, pd.DataFrame] = {}
    for cond_name in ['Condition1', 'Condition2', 'Condition3']:
        df = find_first_bearing(cond_name)
        if df is not None:
            cond_data[cond_name] = df

    if not cond_data:
        logger.error("データなし。feature_extract.pyを先に実行してください。")
        return

    # RMS時系列オーバーレイ
    plot_rms_overlay(cond_data)

    # 正常時ベースライン定量比較
    quantify_normal_baseline(cond_data)

    # 正常RMS箱ひげ図
    plot_normal_baseline_comparison(cond_data)

    # 閾値分析（条件別）
    plot_threshold_analysis(cond_data)

    logger.info("=== 条件間比較完了 ===")


if __name__ == "__main__":
    main()
