"""
QC7つ道具 - パレート図作成ツール

不良原因と件数からパレート図を作成し、
上位80%を占める主要原因を特定する。
"""

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import pandas as pd


# 日本語フォント設定（Windows標準フォントを使用）
for font_name in ["Yu Gothic", "Meiryo", "MS Gothic"]:
    if font_name in {f.name for f in fm.fontManager.ttflist}:
        plt.rcParams["font.family"] = font_name
        break
plt.rcParams["axes.unicode_minus"] = False


def create_pareto_chart(data: dict, title: str = "パレート図"):
    """
    パレート図を作成する。

    Parameters
    ----------
    data : dict
        {原因: 件数} の辞書
    title : str
        グラフタイトル
    """
    # データフレーム作成・件数の降順でソート
    df = pd.DataFrame(list(data.items()), columns=["原因", "件数"])
    df = df.sort_values("件数", ascending=False).reset_index(drop=True)

    # 累積％を計算
    total = df["件数"].sum()
    df["累積％"] = df["件数"].cumsum() / total * 100

    # --- 上位80%の原因を抽出 ---
    top_causes = []
    for _, row in df.iterrows():
        top_causes.append(row["原因"])
        if row["累積％"] >= 80:
            break

    print(f"上位80%を占める原因：{'、'.join(top_causes)}")

    # --- グラフ作成 ---
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # 棒グラフ（件数）
    x = range(len(df))
    bars = ax1.bar(x, df["件数"], color="#4472C4", edgecolor="white", zorder=2)
    ax1.set_xlabel("不良原因", fontsize=12)
    ax1.set_ylabel("件数", color="#4472C4", fontsize=12)
    ax1.set_xticks(x)
    ax1.set_xticklabels(df["原因"], fontsize=11)
    ax1.tick_params(axis="y", labelcolor="#4472C4")

    # 棒の上に件数を表示
    for bar, count in zip(bars, df["件数"]):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + total * 0.01,
            str(count),
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    # 折れ線グラフ（累積％）
    ax2 = ax1.twinx()
    ax2.plot(x, df["累積％"], color="#ED7D31", marker="o", linewidth=2, zorder=3)
    ax2.set_ylabel("累積％", color="#ED7D31", fontsize=12)
    ax2.set_ylim(0, 105)
    ax2.tick_params(axis="y", labelcolor="#ED7D31")

    # 80%ライン（赤い点線）
    ax2.axhline(y=80, color="red", linestyle="--", linewidth=1.5)
    ax2.text(len(df) - 0.5, 82, "80%", color="red", fontsize=10, ha="right")

    ax1.set_title(title, fontsize=14, fontweight="bold", pad=15)
    ax1.set_axisbelow(True)
    ax1.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    plt.show()


# ===== サンプルデータ =====
SAMPLE_DATA = {
    "寸法不良": 45,
    "傷": 30,
    "バリ": 10,
    "汚れ": 8,
    "欠け": 5,
    "その他": 2,
}

if __name__ == "__main__":
    create_pareto_chart(SAMPLE_DATA, title="不良原因パレート図")
