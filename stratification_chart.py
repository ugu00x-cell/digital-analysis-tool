"""
QC7つ道具 - 層別グラフ（箱ひげ図）作成ツール

機械別・作業者別などグループごとの分布を箱ひげ図で比較し、
異常なグループを検出する。
"""

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

# 日本語フォント設定
for font_name in ["Yu Gothic", "Meiryo", "MS Gothic"]:
    if font_name in {f.name for f in fm.fontManager.ttflist}:
        plt.rcParams["font.family"] = font_name
        break
plt.rcParams["axes.unicode_minus"] = False


def create_stratification_chart(data: dict, title="層別グラフ", unit="mm"):
    """
    層別の箱ひげ図を作成する。

    Parameters
    ----------
    data : dict
        {グループ名: 測定値の配列} の辞書
    title : str
        グラフタイトル
    unit : str
        単位
    """
    labels = list(data.keys())
    values = [np.asarray(v) for v in data.values()]

    # --- 統計量の計算 ---
    stats_list = []
    for label, vals in zip(labels, values):
        stats_list.append({
            "グループ": label,
            "平均": np.mean(vals),
            "中央値": np.median(vals),
            "標準偏差": np.std(vals, ddof=1),
            "最小": np.min(vals),
            "最大": np.max(vals),
        })

    # 全体の平均・標準偏差（異常判定の基準）
    all_values = np.concatenate(values)
    overall_mean = np.mean(all_values)
    overall_std = np.std(all_values, ddof=1)

    # --- テキスト出力 ---
    print(f"{'グループ':<10} {'平均':>10} {'中央値':>10} {'標準偏差':>10}")
    print("-" * 45)
    for s in stats_list:
        print(f"{s['グループ']:<10} {s['平均']:>10.4f} {s['中央値']:>10.4f} {s['標準偏差']:>10.4f}")
    print("-" * 45)
    print(f"{'全体':<10} {overall_mean:>10.4f} {'':>10} {overall_std:>10.4f}")
    print()

    # --- 異常判定（全体平均から2σ以上離れたグループ） ---
    anomalies = []
    for s in stats_list:
        diff = abs(s["平均"] - overall_mean)
        if diff > 2 * overall_std:
            anomalies.append(s["グループ"])

    if anomalies:
        print(f"判定: {', '.join(anomalies)} に異常の可能性あり（全体平均から2σ以上乖離）")
    else:
        print("判定: 全グループ正常範囲内")

    # --- グラフ作成 ---
    fig, ax = plt.subplots(figsize=(10, 6))

    bp = ax.boxplot(values, tick_labels=labels, patch_artist=True, widths=0.5,
                    medianprops=dict(color="white", linewidth=2),
                    whiskerprops=dict(linewidth=1.5),
                    capprops=dict(linewidth=1.5))

    # 箱の色分け（異常グループは赤系）
    colors = []
    for label in labels:
        if label in anomalies:
            colors.append("#FF6B6B")
        else:
            colors.append("#4472C4")
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.8)

    # 平均値をマーカーで表示
    for i, vals in enumerate(values):
        ax.scatter(i + 1, np.mean(vals), marker="D", color="#ED7D31",
                   s=80, zorder=3, edgecolor="white", linewidth=1.5)

    # 全体平均の水平線
    ax.axhline(overall_mean, color="#70AD47", linestyle="--", linewidth=1.5,
               label=f"全体平均 = {overall_mean:.4f} {unit}")

    ax.set_xlabel("グループ", fontsize=12)
    ax.set_ylabel(f"寸法（{unit}）", fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
    ax.legend(fontsize=10, loc="upper right")
    ax.grid(axis="y", alpha=0.3)

    # 凡例補足（平均値マーカー）
    ax.scatter([], [], marker="D", color="#ED7D31", s=80, edgecolor="white",
               linewidth=1.5, label="各グループ平均")
    ax.legend(fontsize=10, loc="upper right")

    fig.tight_layout()
    plt.show()


# ===== サンプルデータ =====
if __name__ == "__main__":
    np.random.seed(42)

    SAMPLE_DATA = {
        "機械A": np.random.normal(loc=50.0, scale=0.10, size=100),
        "機械B": np.random.normal(loc=50.0, scale=0.12, size=100),
        "機械C": np.random.normal(loc=50.3, scale=0.15, size=100),  # 平均ズレ
        "機械D": np.random.normal(loc=50.0, scale=0.11, size=100),
    }

    create_stratification_chart(SAMPLE_DATA, title="機械別 寸法分布の層別比較")
