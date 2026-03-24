"""
QC7つ道具 - 散布図作成ツール

2つの変数の関係を散布図で表示し、
回帰直線と相関係数から関係性を判定する。
"""

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
from scipy import stats

# 日本語フォント設定
for font_name in ["Yu Gothic", "Meiryo", "MS Gothic"]:
    if font_name in {f.name for f in fm.fontManager.ttflist}:
        plt.rcParams["font.family"] = font_name
        break
plt.rcParams["axes.unicode_minus"] = False


def judge_correlation(r):
    """相関係数から相関の強さを判定する"""
    abs_r = abs(r)
    if abs_r >= 0.7:
        direction = "正" if r > 0 else "負"
        return f"強い{direction}の相関"
    if abs_r >= 0.4:
        direction = "正" if r > 0 else "負"
        return f"弱い{direction}の相関"
    return "相関なし"


def create_scatter_chart(x, y, xlabel, ylabel, title="散布図"):
    """
    散布図を作成する。

    Parameters
    ----------
    x : array-like
        横軸データ
    y : array-like
        縦軸データ
    xlabel : str
        横軸ラベル
    ylabel : str
        縦軸ラベル
    title : str
        グラフタイトル
    """
    x = np.asarray(x)
    y = np.asarray(y)

    # 回帰直線と相関係数
    slope, intercept, r, p_value, std_err = stats.linregress(x, y)
    judgment = judge_correlation(r)

    # --- テキスト出力 ---
    print(f"データ数:   {len(x)}")
    print(f"相関係数 r: {r:.4f}")
    print(f"判定:       {judgment}")
    print(f"回帰式:     y = {slope:.4f}x + {intercept:.4f}")
    print(f"p値:        {p_value:.2e}")

    # --- グラフ作成 ---
    fig, ax = plt.subplots(figsize=(10, 6))

    # 散布図
    ax.scatter(x, y, color="#4472C4", edgecolor="white", s=60,
               alpha=0.8, zorder=2)

    # 回帰直線
    x_line = np.linspace(x.min(), x.max(), 100)
    y_line = slope * x_line + intercept
    ax.plot(x_line, y_line, color="#ED7D31", linewidth=2,
            label=f"回帰直線: y = {slope:.4f}x + {intercept:.4f}", zorder=3)

    # 相関係数と判定を表示
    r_color = "#70AD47" if abs(r) >= 0.7 else "#ED7D31" if abs(r) >= 0.4 else "#999999"
    ax.text(
        0.02, 0.95,
        f"r = {r:.4f}\n{judgment}",
        transform=ax.transAxes, fontsize=11, verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white",
                  edgecolor=r_color, linewidth=2),
    )

    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
    ax.legend(fontsize=10, loc="lower right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    plt.show()


# ===== サンプルデータ =====
if __name__ == "__main__":
    np.random.seed(42)

    # 加工温度（℃）: 20〜40℃の範囲
    temperature = np.random.uniform(20, 40, 50)

    # 寸法誤差（mm）: 温度に比例 + ノイズ（正の相関）
    dimension_error = 0.005 * temperature + np.random.normal(0, 0.02, 50)

    create_scatter_chart(
        temperature, dimension_error,
        xlabel="加工温度（℃）",
        ylabel="寸法誤差（mm）",
        title="加工温度と寸法誤差の散布図",
    )
