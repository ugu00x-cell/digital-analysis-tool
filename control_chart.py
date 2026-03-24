"""
QC7つ道具 - Xbar-R管理図作成ツール

サブグループごとの平均値（Xbar）と範囲（R）を管理図で表示し、
管理限界を外れた点を検出する。
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

# Xbar-R管理図の係数（サンプルサイズ n に対応）
# n: (A2, D3, D4, d2)
CONTROL_CHART_CONSTANTS = {
    2: (1.880, 0.000, 3.267, 1.128),
    3: (1.023, 0.000, 2.575, 1.693),
    4: (0.729, 0.000, 2.282, 2.059),
    5: (0.577, 0.000, 2.115, 2.326),
    6: (0.483, 0.000, 2.004, 2.534),
    7: (0.419, 0.076, 1.924, 2.704),
    8: (0.373, 0.136, 1.864, 2.847),
    9: (0.337, 0.184, 1.816, 2.970),
    10: (0.308, 0.223, 1.777, 3.078),
}


def create_control_chart(data, title="Xbar-R管理図"):
    """
    Xbar-R管理図を作成する。

    Parameters
    ----------
    data : array-like, shape (k, n)
        k: サブグループ数、n: サブグループ内サンプル数
    title : str
        グラフタイトル
    """
    data = np.asarray(data)
    k, n = data.shape

    if n not in CONTROL_CHART_CONSTANTS:
        print(f"サンプルサイズ n={n} は未対応です（2〜10に対応）")
        return

    A2, D3, D4, d2 = CONTROL_CHART_CONSTANTS[n]

    # 各サブグループの平均と範囲
    xbar = data.mean(axis=1)
    r = data.max(axis=1) - data.min(axis=1)

    # 総平均・平均範囲
    xbar_bar = xbar.mean()
    r_bar = r.mean()

    # 管理限界線
    xbar_ucl = xbar_bar + A2 * r_bar
    xbar_lcl = xbar_bar - A2 * r_bar
    r_ucl = D4 * r_bar
    r_lcl = D3 * r_bar

    # 異常点の検出
    xbar_out = (xbar > xbar_ucl) | (xbar < xbar_lcl)
    r_out = (r > r_ucl) | (r < r_lcl)
    has_anomaly = xbar_out.any() or r_out.any()

    # --- テキスト出力 ---
    print(f"サブグループ数: {k}  サンプルサイズ: {n}")
    print(f"Xbar: CL={xbar_bar:.4f}  UCL={xbar_ucl:.4f}  LCL={xbar_lcl:.4f}")
    print(f"R:    CL={r_bar:.4f}  UCL={r_ucl:.4f}  LCL={r_lcl:.4f}")

    if xbar_out.any():
        groups = np.where(xbar_out)[0] + 1
        print(f"Xbar異常点: グループ {', '.join(map(str, groups))}")
    if r_out.any():
        groups = np.where(r_out)[0] + 1
        print(f"R異常点:    グループ {', '.join(map(str, groups))}")

    print(f"判定: {'異常あり → 原因調査が必要' if has_anomaly else '異常なし → 工程は管理状態'}")

    # --- グラフ作成 ---
    x = np.arange(1, k + 1)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    fig.suptitle(title, fontsize=14, fontweight="bold")

    # === Xbar管理図（上段） ===
    ax1.plot(x, xbar, marker="o", color="#4472C4", linewidth=1.5,
             markersize=5, zorder=2)
    # 管理限界線
    ax1.axhline(xbar_ucl, color="red", linewidth=1.5, label=f"UCL={xbar_ucl:.4f}")
    ax1.axhline(xbar_bar, color="#70AD47", linewidth=1.5, linestyle="--",
                label=f"CL={xbar_bar:.4f}")
    ax1.axhline(xbar_lcl, color="red", linewidth=1.5, label=f"LCL={xbar_lcl:.4f}")
    # 異常点ハイライト
    if xbar_out.any():
        ax1.scatter(x[xbar_out], xbar[xbar_out], color="red", s=120,
                    zorder=3, edgecolor="darkred", linewidth=2, label="異常点")

    ax1.set_ylabel("Xbar（平均値）", fontsize=11)
    ax1.legend(fontsize=9, loc="upper right")
    ax1.grid(alpha=0.3)

    # === R管理図（下段） ===
    ax2.plot(x, r, marker="s", color="#ED7D31", linewidth=1.5,
             markersize=5, zorder=2)
    # 管理限界線
    ax2.axhline(r_ucl, color="red", linewidth=1.5, label=f"UCL={r_ucl:.4f}")
    ax2.axhline(r_bar, color="#70AD47", linewidth=1.5, linestyle="--",
                label=f"CL={r_bar:.4f}")
    ax2.axhline(r_lcl, color="red", linewidth=1.5, label=f"LCL={r_lcl:.4f}")
    # 異常点ハイライト
    if r_out.any():
        ax2.scatter(x[r_out], r[r_out], color="red", s=120,
                    zorder=3, edgecolor="darkred", linewidth=2, label="異常点")

    ax2.set_xlabel("サブグループ番号", fontsize=11)
    ax2.set_ylabel("R（範囲）", fontsize=11)
    ax2.legend(fontsize=9, loc="upper right")
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    plt.show()


# ===== サンプルデータ =====
if __name__ == "__main__":
    np.random.seed(42)

    k = 25  # サブグループ数
    n = 4   # サンプルサイズ

    # 正常データ（目標値50.0mm、σ=0.1mm）
    data = np.random.normal(loc=50.0, scale=0.1, size=(k, n))

    # グループ15〜18に工程異常を発生させる（平均シフト＋バラツキ増大）
    data[14:18] += np.random.normal(loc=0.3, scale=0.15, size=(4, n))

    create_control_chart(data, title="加工品寸法 Xbar-R管理図")
