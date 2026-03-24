"""
QC7つ道具 - ヒストグラム作成ツール

加工品の寸法データからヒストグラムを作成し、
規格線・平均値・Cpkを表示する。
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


def calc_cpk(values, usl, lsl):
    """Cpkを計算する"""
    mean = np.mean(values)
    std = np.std(values, ddof=1)
    if std == 0:
        return None, None, None
    cpu = (usl - mean) / (3 * std)
    cpl = (mean - lsl) / (3 * std)
    return min(cpu, cpl), cpu, cpl


def judge_cpk(cpk):
    """Cpkの判定"""
    if cpk is None:
        return "計算不可"
    if cpk >= 1.33:
        return "工程は安定しています（Cpk >= 1.33）"
    if cpk >= 1.00:
        return "工程能力はギリギリです。要注意（1.00 <= Cpk < 1.33）"
    return "工程能力が不足しています。要改善（Cpk < 1.00）"


def create_histogram(values, usl, lsl, title="ヒストグラム", unit="mm"):
    """
    ヒストグラムを作成する。

    Parameters
    ----------
    values : array-like
        測定値の配列
    usl : float
        規格上限
    lsl : float
        規格下限
    title : str
        グラフタイトル
    unit : str
        単位
    """
    mean = np.mean(values)
    std = np.std(values, ddof=1)
    cpk, cpu, cpl = calc_cpk(values, usl, lsl)

    # --- テキスト出力 ---
    print(f"データ数: {len(values)}")
    print(f"平均値:   {mean:.4f} {unit}")
    print(f"標準偏差: {std:.4f} {unit}")
    print(f"Cpu: {cpu:.2f}  Cpl: {cpl:.2f}  Cpk: {cpk:.2f}")
    print(f"判定: {judge_cpk(cpk)}")

    # --- グラフ作成 ---
    fig, ax = plt.subplots(figsize=(10, 6))

    # ヒストグラム
    ax.hist(values, bins=20, color="#4472C4", edgecolor="white",
            alpha=0.85, zorder=2)

    # 規格上限（USL）・規格下限（LSL）
    ax.axvline(usl, color="red", linestyle="--", linewidth=2,
               label=f"USL = {usl} {unit}")
    ax.axvline(lsl, color="red", linestyle="--", linewidth=2,
               label=f"LSL = {lsl} {unit}")

    # 平均値
    ax.axvline(mean, color="#4472C4", linestyle="--", linewidth=2,
               label=f"平均 = {mean:.3f} {unit}")

    # Cpk表示
    cpk_color = "#70AD47" if cpk >= 1.33 else "#ED7D31" if cpk >= 1.00 else "#FF0000"
    ax.text(
        0.02, 0.95,
        f"Cpk = {cpk:.2f}\n{judge_cpk(cpk)}",
        transform=ax.transAxes, fontsize=11, verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white",
                  edgecolor=cpk_color, linewidth=2),
    )

    ax.set_xlabel(f"寸法 ({unit})", fontsize=12)
    ax.set_ylabel("度数", fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
    ax.legend(fontsize=10, loc="upper right")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    plt.show()


# ===== サンプルデータ =====
if __name__ == "__main__":
    np.random.seed(42)

    SAMPLE_DATA = np.random.normal(loc=50.0, scale=0.3, size=100)
    USL = 51.0
    LSL = 49.0

    create_histogram(SAMPLE_DATA, USL, LSL, title="加工品寸法ヒストグラム")
