"""
QC7つ道具 - チェックシート（ヒートマップ）作成ツール

不良種類×曜日のマトリクスをヒートマップで可視化し、
最多不良・最多曜日を自動判定する。
"""

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import seaborn as sns

# 日本語フォント設定
for font_name in ["Yu Gothic", "Meiryo", "MS Gothic"]:
    if font_name in {f.name for f in fm.fontManager.ttflist}:
        plt.rcParams["font.family"] = font_name
        break
plt.rcParams["axes.unicode_minus"] = False


def create_checksheet(data, defects, days, title="チェックシート"):
    """
    チェックシート（ヒートマップ）を作成する。

    Parameters
    ----------
    data : array-like, shape (不良種類数, 曜日数)
        各セルの不良件数
    defects : list[str]
        不良種類のラベル
    days : list[str]
        曜日のラベル
    title : str
        グラフタイトル
    """
    data = np.asarray(data)

    row_totals = data.sum(axis=1)
    col_totals = data.sum(axis=0)
    grand_total = data.sum()

    # --- テキスト出力 ---
    header = f"{'':>10}" + "".join(f"{d:>6}" for d in days) + f"{'合計':>8}"
    print(header)
    print("-" * len(header))
    for i, defect in enumerate(defects):
        row = f"{defect:<10}" + "".join(f"{data[i, j]:>6}" for j in range(len(days)))
        row += f"{row_totals[i]:>8}"
        print(row)
    print("-" * len(header))
    total_row = f"{'合計':<10}" + "".join(f"{col_totals[j]:>6}" for j in range(len(days)))
    total_row += f"{grand_total:>8}"
    print(total_row)
    print()

    top_defect = defects[np.argmax(row_totals)]
    top_day = days[np.argmax(col_totals)]
    print(f"最多不良種類: {top_defect}（{row_totals.max()}件）")
    print(f"最多曜日:     {top_day}（{col_totals.max()}件）")

    # --- ヒートマップ作成 ---
    # 合計行・列を追加した拡張データ
    extended = np.zeros((len(defects) + 1, len(days) + 1), dtype=int)
    extended[:len(defects), :len(days)] = data
    extended[:len(defects), -1] = row_totals
    extended[-1, :len(days)] = col_totals
    extended[-1, -1] = grand_total

    ext_defects = defects + ["合計"]
    ext_days = days + ["合計"]

    fig, ax = plt.subplots(figsize=(10, 6))

    # 本体部分のみで色スケールを決定
    sns.heatmap(
        extended, annot=True, fmt="d", cmap="YlOrRd",
        xticklabels=ext_days, yticklabels=ext_defects,
        linewidths=1, linecolor="white",
        vmin=0, vmax=data.max(),
        cbar_kws={"label": "件数"},
        ax=ax,
    )

    # 合計行・列の背景をグレーに上書き
    for i in range(len(ext_days)):
        ax.add_patch(plt.Rectangle((i, len(defects)), 1, 1,
                     fill=True, facecolor="#D9D9D9", edgecolor="white", lw=1))
        ax.text(i + 0.5, len(defects) + 0.5, str(extended[-1, i]),
                ha="center", va="center", fontsize=11, fontweight="bold")
    for j in range(len(defects)):
        ax.add_patch(plt.Rectangle((len(days), j), 1, 1,
                     fill=True, facecolor="#D9D9D9", edgecolor="white", lw=1))
        ax.text(len(days) + 0.5, j + 0.5, str(extended[j, -1]),
                ha="center", va="center", fontsize=11, fontweight="bold")
    # 右下角（総合計）
    ax.add_patch(plt.Rectangle((len(days), len(defects)), 1, 1,
                 fill=True, facecolor="#BFBFBF", edgecolor="white", lw=1))
    ax.text(len(days) + 0.5, len(defects) + 0.5, str(grand_total),
            ha="center", va="center", fontsize=11, fontweight="bold")

    ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("曜日", fontsize=12)
    ax.set_ylabel("不良種類", fontsize=12)
    ax.tick_params(axis="y", rotation=0)

    fig.tight_layout()
    plt.show()


# ===== サンプルデータ =====
if __name__ == "__main__":
    np.random.seed(42)

    DEFECTS = ["寸法不良", "傷", "バリ", "汚れ", "欠け"]
    DAYS = ["月", "火", "水", "木", "金"]

    # ベースの件数（不良種類ごとの傾向）
    base = np.array([
        [8, 6, 7, 5, 12],   # 寸法不良：金曜に多い
        [4, 5, 3, 4,  8],   # 傷：金曜に多い
        [2, 3, 2, 1,  5],   # バリ
        [1, 2, 1, 2,  3],   # 汚れ
        [1, 0, 1, 1,  2],   # 欠け
    ])

    # 少しランダムにばらつかせる
    noise = np.random.randint(-1, 2, size=base.shape)
    sample_data = np.clip(base + noise, 0, None)

    create_checksheet(sample_data, DEFECTS, DAYS, title="週次不良チェックシート")
