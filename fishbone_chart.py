"""
QC7つ道具 - 特性要因図（魚の骨図）作成ツール

大骨6カテゴリ（人・機械・材料・方法・環境・測定）に
小骨（原因）を配置した魚の骨図を描画する。
"""

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.patches as patches

# 日本語フォント設定
for font_name in ["Yu Gothic", "Meiryo", "MS Gothic"]:
    if font_name in {f.name for f in fm.fontManager.ttflist}:
        plt.rcParams["font.family"] = font_name
        break
plt.rcParams["axes.unicode_minus"] = False


def create_fishbone_chart(effect: str, causes: dict, title: str = "特性要因図"):
    """
    特性要因図（魚の骨図）を作成する。

    Parameters
    ----------
    effect : str
        特性（右端に表示する結果）
    causes : dict
        {カテゴリ名: [原因1, 原因2, ...]} の辞書
    title : str
        グラフタイトル
    """
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_xlim(-1, 11)
    ax.set_ylim(-4, 4)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=16, fontweight="bold", pad=20)

    # --- 背骨（中央の横線） ---
    spine_y = 0
    spine_left = 0.5
    spine_right = 9.5
    ax.annotate(
        "",
        xy=(spine_right, spine_y),
        xytext=(spine_left, spine_y),
        arrowprops=dict(arrowstyle="->,head_width=0.4,head_length=0.3",
                        lw=2.5, color="#333333"),
    )

    # --- 特性（魚の頭） ---
    head_x = spine_right + 0.3
    rect = patches.FancyBboxPatch(
        (head_x - 0.1, spine_y - 0.5), 1.6, 1.0,
        boxstyle="round,pad=0.15",
        facecolor="#FF6B6B", edgecolor="#CC3333", linewidth=2,
    )
    ax.add_patch(rect)
    ax.text(head_x + 0.7, spine_y, effect, fontsize=13,
            fontweight="bold", color="white", ha="center", va="center")

    # --- 大骨の配置 ---
    # 上段3本・下段3本、等間隔に配置
    category_list = list(causes.items())
    # 上段: index 0, 2, 4 → 左から右へ
    # 下段: index 1, 3, 5 → 左から右へ
    x_positions = [2.0, 4.5, 7.0]
    bone_angle_dx = 1.5  # 大骨の水平方向の長さ
    bone_angle_dy = 2.5  # 大骨の垂直方向の長さ

    colors_top = ["#4472C4", "#ED7D31", "#70AD47"]
    colors_bot = ["#9B59B6", "#E74C3C", "#1ABC9C"]

    for i, (category, sub_causes) in enumerate(category_list):
        col_idx = i // 2  # 0,1,2
        is_top = (i % 2 == 0)
        base_x = x_positions[col_idx]
        sign = 1 if is_top else -1
        color = colors_top[col_idx] if is_top else colors_bot[col_idx]

        # 大骨の先端
        tip_x = base_x - bone_angle_dx
        tip_y = spine_y + sign * bone_angle_dy

        # 大骨を描画
        ax.annotate(
            "",
            xy=(base_x, spine_y),
            xytext=(tip_x, tip_y),
            arrowprops=dict(arrowstyle="->,head_width=0.2,head_length=0.15",
                            lw=2, color=color),
        )

        # カテゴリ名（大骨の先端）
        ax.text(
            tip_x - 0.1, tip_y + sign * 0.3, category,
            fontsize=13, fontweight="bold", color=color,
            ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor=color, linewidth=1.5),
        )

        # --- 小骨 ---
        n = len(sub_causes)
        for j, cause in enumerate(sub_causes):
            # 大骨上の位置を等間隔に配置（先端寄り → 根元寄り）
            t = (j + 1) / (n + 1)
            attach_x = tip_x + t * (base_x - tip_x)
            attach_y = tip_y + t * (spine_y - tip_y)

            # 小骨は背骨と平行（水平）に描く
            sub_len = 1.0
            sub_start_x = attach_x - sub_len
            sub_start_y = attach_y

            ax.plot(
                [sub_start_x, attach_x],
                [sub_start_y, attach_y],
                color=color, lw=1.2,
            )

            # 小骨のラベル
            ax.text(
                sub_start_x - 0.1, sub_start_y, cause,
                fontsize=9, color="#333333", ha="right", va="center",
            )

    fig.tight_layout()
    plt.show()


# ===== サンプルデータ（寸法不良） =====
SAMPLE_EFFECT = "寸法不良"
SAMPLE_CAUSES = {
    "人":   ["作業ミス", "経験不足", "疲労"],
    "機械": ["工具摩耗", "振動", "精度低下"],
    "材料": ["材質バラツキ", "寸法誤差"],
    "方法": ["手順不備", "条件設定ミス"],
    "環境": ["温度変化", "湿度"],
    "測定": ["測定誤差", "器具不良"],
}

if __name__ == "__main__":
    create_fishbone_chart(SAMPLE_EFFECT, SAMPLE_CAUSES)
