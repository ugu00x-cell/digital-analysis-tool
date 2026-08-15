"""
異常検知結果の可視化モジュール（改良版）

3種類の図を生成する：
  1. センサー時系列ダッシュボード : 異常区間を背景色で強調・種類を注釈表示
  2. 手法比較グラフ               : IF vs 3σ の検知帯と精度指標を並べて表示
  3. 精度評価グラフ               : Precision / Recall をバーチャートで比較
"""

import logging
import warnings
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from pathlib import Path
from logger_config import get_logger

logger = get_logger(__name__)
warnings.filterwarnings('ignore', category=UserWarning, message='findfont')

# ── デザイン設定 ──
plt.rcParams.update({
    'font.family':       ['Meiryo', 'Hiragino Sans', 'IPAGothic', 'sans-serif'],
    'axes.spines.top':   False,
    'axes.spines.right': False,
    'axes.grid':         True,
    'grid.alpha':        0.25,
    'grid.linestyle':    '--',
    'figure.facecolor':  '#0f1117',
    'axes.facecolor':    '#1a1d27',
    'axes.labelcolor':   '#e0e0e0',
    'xtick.color':       '#a0a0a0',
    'ytick.color':       '#a0a0a0',
    'text.color':        '#e0e0e0',
    'grid.color':        '#333344',
    'axes.edgecolor':    '#333344',
})

# センサーごとの設定
SENSOR_CFG: dict[str, dict] = {
    'temperature': {'label': '温度 (℃)',    'color': '#ff6b6b'},
    'pressure':    {'label': '圧力 (MPa)',  'color': '#4ecdc4'},
    'vibration':   {'label': '振動 (mm/s)', 'color': '#ffe66d'},
}

# 異常タイプの注釈（インデックス範囲 → ラベル）
ANOMALY_ANNOTATIONS: list[dict] = [
    {'start': 199, 'end': 202,  'label': 'スパイク',  'color': '#ff9f43', 'sensor': 'temperature'},
    {'start': 649, 'end': 652,  'label': 'スパイク',  'color': '#ff9f43', 'sensor': 'temperature'},
    {'start': 700, 'end': 800,  'label': 'ドリフト',  'color': '#ee5a24', 'sensor': 'pressure'},
    {'start': 900, 'end': 950,  'label': '固着',      'color': '#a29bfe', 'sensor': 'vibration'},
    {'start': 1099,'end': 1102, 'label': 'スパイク',  'color': '#ff9f43', 'sensor': 'temperature'},
]


def _shade_anomaly_regions(
    ax: plt.Axes,
    df: pd.DataFrame,
    color: str = '#ff4444',
    alpha: float = 0.12
) -> None:
    """異常区間を背景色でハイライトするヘルパー。

    Args:
        ax: 描画対象の Axes
        df: both_pred カラムを持つ DataFrame
        color: 背景色
        alpha: 透過度
    """
    # 連続した異常区間をまとめて塗る
    in_anomaly = False
    start_t = None
    for _, row in df.iterrows():
        if row['both_pred'] == 1 and not in_anomaly:
            in_anomaly = True
            start_t = row['timestamp']
        elif row['both_pred'] == 0 and in_anomaly:
            ax.axvspan(start_t, row['timestamp'], color=color, alpha=alpha, zorder=0)
            in_anomaly = False
    if in_anomaly:
        ax.axvspan(start_t, df['timestamp'].iloc[-1], color=color, alpha=alpha, zorder=0)


def plot_sensor_dashboard(
    df: pd.DataFrame,
    thresholds: dict[str, dict],
    output_path: str = 'output/sensor_timeseries.png'
) -> None:
    """センサー時系列ダッシュボードを生成する。

    各センサーのグラフに：
    - 正常データ（細線）
    - 3σしきい値（破線）
    - 異常区間の背景ハイライト
    - 検知ポイントの色分けマーカー
    - 異常タイプの注釈ラベル
    を重ねて表示する。

    Args:
        df: 検知結果付き DataFrame
        thresholds: 3σしきい値の辞書
        output_path: 保存先パス
    """
    sensors = list(SENSOR_CFG.keys())
    fig, axes = plt.subplots(len(sensors), 1, figsize=(16, 10), sharex=True)
    fig.suptitle('工程センサーデータ  異常検知ダッシュボード',
                 fontsize=15, fontweight='bold', color='#ffffff', y=0.98)

    for ax, sensor in zip(axes, sensors):
        cfg = SENSOR_CFG[sensor]
        x, y = df['timestamp'], df[sensor]
        t = thresholds[sensor]

        # ── 正常データ（細い線）──
        ax.plot(x, y, color=cfg['color'], linewidth=0.6, alpha=0.5, zorder=1)

        # ── 3σしきい値 ──
        ax.axhline(t['upper'], color='#ffffff', linestyle='--', linewidth=0.8,
                   alpha=0.4, label=f'+3σ ({t["upper"]:.2f})')
        ax.axhline(t['lower'], color='#ffffff', linestyle='--', linewidth=0.8,
                   alpha=0.4, label=f'-3σ ({t["lower"]:.2f})')
        # しきい値間を薄く塗る（正常域の可視化）
        ax.fill_between(x, t['lower'], t['upper'], color='#ffffff', alpha=0.03, zorder=0)

        # ── 異常区間の背景ハイライト ──
        _shade_anomaly_regions(ax, df, color='#ff4444', alpha=0.10)

        # ── 検知マーカー ──
        mask_only_if    = (df['if_pred'] == 1) & (df['sigma_pred'] == 0)
        mask_only_sigma = (df['sigma_pred'] == 1) & (df['if_pred'] == 0)
        mask_both       = df['both_pred'] == 1

        ax.scatter(x[mask_only_if],    y[mask_only_if],    s=10, color='#f9ca24',
                   zorder=4, alpha=0.8, label='IFのみ検知')
        ax.scatter(x[mask_only_sigma], y[mask_only_sigma], s=10, color='#6c5ce7',
                   zorder=4, alpha=0.8, label='3σのみ検知')
        ax.scatter(x[mask_both],       y[mask_both],       s=20, color='#ff4444',
                   zorder=5, edgecolors='#ffffff', linewidths=0.3, label='両手法で検知')

        # ── 異常タイプの注釈 ──
        _add_anomaly_annotations(ax, df, sensor)

        ax.set_ylabel(cfg['label'], fontsize=9, color=cfg['color'])
        ax.legend(loc='upper right', fontsize=7, ncol=4,
                  facecolor='#1a1d27', edgecolor='#333344', labelcolor='#e0e0e0')

    # X軸フォーマット
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    axes[-1].set_xlabel('時刻（2024-01-01）', fontsize=9)
    fig.autofmt_xdate(rotation=0, ha='center')
    fig.tight_layout(rect=[0, 0, 1, 0.97])

    _save_figure(fig, output_path)


def _add_anomaly_annotations(
    ax: plt.Axes,
    df: pd.DataFrame,
    sensor: str
) -> None:
    """異常タイプのラベルを矢印付きで注釈するヘルパー。

    Args:
        ax: 描画対象の Axes
        df: センサーデータ
        sensor: 対象センサー名
    """
    for ann in ANOMALY_ANNOTATIONS:
        if ann['sensor'] != sensor:
            continue
        mid_idx = (ann['start'] + ann['end']) // 2
        if mid_idx >= len(df):
            continue
        x_pos = df['timestamp'].iloc[mid_idx]
        y_pos = df[sensor].iloc[mid_idx]
        y_max = df[sensor].max()

        ax.annotate(
            ann['label'],
            xy=(x_pos, y_pos),
            xytext=(x_pos, y_max * 1.01),
            fontsize=8, color=ann['color'], fontweight='bold',
            ha='center',
            arrowprops=dict(arrowstyle='->', color=ann['color'], lw=1.2),
            bbox=dict(boxstyle='round,pad=0.2', facecolor=ann['color'],
                      alpha=0.2, edgecolor=ann['color'])
        )


def plot_comparison_dashboard(
    df: pd.DataFrame,
    precision_if: float,
    recall_if: float,
    precision_sigma: float,
    recall_sigma: float,
    output_path: str = 'output/comparison.png'
) -> None:
    """手法比較ダッシュボードを生成する。

    上段：IF と 3σ の検知帯を時系列で比較
    下段：Precision / Recall をバーチャートで比較

    Args:
        df: 検知結果付き DataFrame
        precision_if: Isolation Forest の適合率
        recall_if: Isolation Forest の再現率
        precision_sigma: 3σ法の適合率
        recall_sigma: 3σ法の再現率
        output_path: 保存先パス
    """
    fig = plt.figure(figsize=(16, 10))
    gs = gridspec.GridSpec(3, 2, figure=fig,
                           height_ratios=[1.2, 1.2, 1.8],
                           hspace=0.5, wspace=0.35)

    ax_if     = fig.add_subplot(gs[0, :])  # IFスコア（全幅）
    ax_pred_if    = fig.add_subplot(gs[1, 0], sharex=ax_if)
    ax_pred_sigma = fig.add_subplot(gs[1, 1], sharex=ax_if)
    ax_bar_pr = fig.add_subplot(gs[2, 0])
    ax_bar_f1 = fig.add_subplot(gs[2, 1])

    fig.suptitle('異常検知  手法比較ダッシュボード',
                 fontsize=15, fontweight='bold', color='#ffffff', y=0.99)

    x = df['timestamp']

    # ── ① 異常スコア（Isolation Forest） ──
    ax_if.fill_between(x, df['if_score'], color='#ff6b6b', alpha=0.7)
    ax_if.set_ylabel('異常スコア (IF)', fontsize=9, color='#ff6b6b')
    ax_if.set_title('Isolation Forest  異常スコア推移', fontsize=10, pad=4)
    # 正解ラベルをオーバーレイ
    if 'is_anomaly' in df.columns:
        true_mask = df['is_anomaly'] == 1
        ax_if.fill_between(x, df['if_score'].max() * 1.05,
                           where=true_mask, color='#ffeaa7', alpha=0.25,
                           label='実際の異常区間')
        ax_if.legend(fontsize=8, facecolor='#1a1d27', edgecolor='#333344',
                     labelcolor='#e0e0e0')

    # ── ② IF 検知結果 ──
    _plot_detection_band(ax_pred_if,  x, df['if_pred'],
                         df.get('is_anomaly'), '#ff6b6b', 'Isolation Forest  検知結果')

    # ── ③ 3σ 検知結果 ──
    _plot_detection_band(ax_pred_sigma, x, df['sigma_pred'],
                         df.get('is_anomaly'), '#4ecdc4', '3σ法  検知結果')

    # ── ④ Precision / Recall バーチャート ──
    _plot_precision_recall(ax_bar_pr,
                           precision_if, recall_if,
                           precision_sigma, recall_sigma)

    # ── ⑤ F1スコア比較 ──
    _plot_f1_gauge(ax_bar_f1, precision_if, recall_if, precision_sigma, recall_sigma)

    # X軸フォーマット（時系列部分のみ）
    for ax in [ax_if, ax_pred_if, ax_pred_sigma]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.setp(ax_if.get_xticklabels(), visible=False)

    _save_figure(fig, output_path)


def _plot_detection_band(
    ax: plt.Axes,
    x: pd.Series,
    pred: pd.Series,
    true_labels: pd.Series | None,
    color: str,
    title: str
) -> None:
    """検知帯と正解ラベルを重ねて表示するヘルパー。

    Args:
        ax: 描画対象の Axes
        x: X軸（timestamp）
        pred: 予測ラベル（0/1）
        true_labels: 正解ラベル（None なら非表示）
        color: 検知帯の色
        title: グラフタイトル
    """
    # 正解ラベルの背景
    if true_labels is not None:
        ax.fill_between(x, 1, where=(true_labels == 1),
                        color='#ffeaa7', alpha=0.25, step='mid', label='正解（実際の異常）')

    # 検知帯
    ax.fill_between(x, pred, step='mid', color=color, alpha=0.8, label='検知した異常')
    ax.set_ylim(-0.1, 1.4)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(['正常', '異常'], fontsize=8)
    ax.set_title(title, fontsize=10, pad=4)
    ax.legend(loc='upper right', fontsize=7,
              facecolor='#1a1d27', edgecolor='#333344', labelcolor='#e0e0e0')


def _plot_precision_recall(
    ax: plt.Axes,
    p_if: float, r_if: float,
    p_sg: float, r_sg: float
) -> None:
    """Precision / Recall のグループバーチャートを描くヘルパー。

    Args:
        ax: 描画対象の Axes
        p_if, r_if: Isolation Forest の Precision / Recall
        p_sg, r_sg: 3σ法の Precision / Recall
    """
    x = np.arange(2)
    w = 0.3
    bars_if = ax.bar(x - w/2, [p_if, r_if], w,
                     label='Isolation Forest', color='#ff6b6b', alpha=0.85)
    bars_sg = ax.bar(x + w/2, [p_sg, r_sg], w,
                     label='3σ法', color='#4ecdc4', alpha=0.85)

    # 値ラベル
    for bar in list(bars_if) + list(bars_sg):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.02,
                f'{bar.get_height():.3f}',
                ha='center', va='bottom', fontsize=9, color='#e0e0e0')

    ax.set_xticks(x)
    ax.set_xticklabels(['Precision\n(適合率)', 'Recall\n(再現率)'], fontsize=9)
    ax.set_ylim(0, 1.2)
    ax.set_title('精度比較', fontsize=11, pad=6)
    ax.axhline(0.8, color='#ffffff', linestyle=':', alpha=0.3, label='目標ライン (0.8)')
    ax.legend(fontsize=8, facecolor='#1a1d27', edgecolor='#333344', labelcolor='#e0e0e0')


def _plot_f1_gauge(
    ax: plt.Axes,
    p_if: float, r_if: float,
    p_sg: float, r_sg: float
) -> None:
    """F1スコアの横棒ゲージを描くヘルパー。

    Args:
        ax: 描画対象の Axes
        p_if, r_if: Isolation Forest の Precision / Recall
        p_sg, r_sg: 3σ法の Precision / Recall
    """
    # F1 = 2 * P * R / (P + R)
    f1_if = 2 * p_if * r_if / (p_if + r_if) if (p_if + r_if) > 0 else 0
    f1_sg = 2 * p_sg * r_sg / (p_sg + r_sg) if (p_sg + r_sg) > 0 else 0

    labels = ['Isolation\nForest', '3σ法']
    values = [f1_if, f1_sg]
    colors = ['#ff6b6b', '#4ecdc4']

    # 背景バー（満点=1.0）
    ax.barh(labels, [1, 1], color='#2d3048', height=0.5, zorder=1)
    # スコアバー
    bars = ax.barh(labels, values, color=colors, height=0.5, alpha=0.85, zorder=2)

    for bar, val in zip(bars, values):
        ax.text(val + 0.02, bar.get_y() + bar.get_height() / 2,
                f'{val:.3f}', va='center', fontsize=11,
                fontweight='bold', color='#ffffff')

    ax.set_xlim(0, 1.2)
    ax.set_title('F1スコア（総合評価）', fontsize=11, pad=6)
    ax.axvline(0.8, color='#ffffff', linestyle=':', alpha=0.3)
    ax.text(0.81, -0.5, '目標 0.8', fontsize=7, color='#a0a0a0')
    ax.set_xlabel('F1 Score', fontsize=9)


def _save_figure(fig: plt.Figure, output_path: str) -> None:
    """図を保存してメモリを解放するヘルパー。

    Args:
        fig: 保存する Figure
        output_path: 保存先パス
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close(fig)
    logger.info(f'図を保存: {output_path}')


# ── 後方互換のため旧関数名もラップ ──
def plot_sensor_timeseries(df, thresholds, output_path='output/sensor_timeseries.png'):
    """後方互換ラッパー。"""
    plot_sensor_dashboard(df, thresholds, output_path)


def plot_comparison(df, output_path='output/comparison.png'):
    """後方互換ラッパー（精度指標なしバージョン）。"""
    plot_comparison_dashboard(df, 0, 0, 0, 0, output_path)
