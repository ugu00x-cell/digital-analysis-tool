"""AGV経路最適化シミュレーター。人流データに基づく重み付きA*で経路を計算する。"""

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import streamlit as st

matplotlib.rcParams["font.family"] = "MS Gothic"

from map_generator import GRID_SIZE, TIME_PERIODS, density_to_cost, generate_density_map
from pathfinding import a_star

# --- ページ設定 ---
st.set_page_config(page_title="AGV経路最適化シミュレーター", layout="wide")
st.title("AGV経路最適化シミュレーター")
st.caption("人流密度を考慮した重み付きA*アルゴリズムによる経路計算")

# --- サイドバー ---
st.sidebar.header("パラメータ設定")

time_period = st.sidebar.slider(
    "時間帯",
    min_value=0,
    max_value=2,
    value=0,
    format="%d",
    help="0=朝, 1=昼, 2=夕方",
)
st.sidebar.info(f"現在の時間帯: **{TIME_PERIODS[time_period]}**")

st.sidebar.subheader("スタート・ゴール設定")
col_s1, col_s2 = st.sidebar.columns(2)
start_row = col_s1.number_input("スタート行", 0, GRID_SIZE - 1, 0)
start_col = col_s2.number_input("スタート列", 0, GRID_SIZE - 1, 0)

col_g1, col_g2 = st.sidebar.columns(2)
goal_row = col_g1.number_input("ゴール行", 0, GRID_SIZE - 1, 9)
goal_col = col_g2.number_input("ゴール列", 0, GRID_SIZE - 1, 9)

start = (int(start_row), int(start_col))
goal = (int(goal_row), int(goal_col))

max_penalty = st.sidebar.slider(
    "混雑ペナルティ倍率",
    min_value=2.0,
    max_value=20.0,
    value=10.0,
    step=1.0,
    help="人が多いセルの移動コスト倍率",
)

# --- データ生成 ---
density = generate_density_map(time_period)
cost_map = density_to_cost(density, max_penalty=max_penalty)

# --- 経路計算 ---
result = a_star(cost_map, start, goal)

# --- 可視化 ---
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

# 左: 人流密度ヒートマップ + 経路
im1 = ax1.imshow(density, cmap="YlOrRd", vmin=0, vmax=1, origin="upper")
ax1.set_title("人流密度マップ + AGV経路", fontsize=14)
fig.colorbar(im1, ax=ax1, label="人の密度", shrink=0.8)

# グリッド線
for i in range(GRID_SIZE + 1):
    ax1.axhline(i - 0.5, color="gray", linewidth=0.5, alpha=0.5)
    ax1.axvline(i - 0.5, color="gray", linewidth=0.5, alpha=0.5)

# 経路を描画
if result is not None:
    path, total_cost = result
    path_rows = [p[0] for p in path]
    path_cols = [p[1] for p in path]
    ax1.plot(path_cols, path_rows, "-o", linewidth=2.5, markersize=5, color="red", zorder=5)

# スタート・ゴールのマーカー
ax1.plot(start[1], start[0], "s", color="lime", markersize=14, markeredgecolor="black", zorder=10)
ax1.plot(goal[1], goal[0], "*", color="blue", markersize=18, markeredgecolor="black", zorder=10)

# 凡例
legend_elements = [
    mpatches.Patch(facecolor="lime", edgecolor="black", label="スタート"),
    mpatches.Patch(facecolor="blue", edgecolor="black", label="ゴール"),
    plt.Line2D([0], [0], color="red", linewidth=2.5, label="AGV経路"),
]
ax1.legend(handles=legend_elements, loc="upper right", fontsize=9)

ax1.set_xticks(range(GRID_SIZE))
ax1.set_yticks(range(GRID_SIZE))

# 右: コストマップ
im2 = ax2.imshow(cost_map, cmap="Blues", origin="upper")
ax2.set_title("移動コストマップ", fontsize=14)
fig.colorbar(im2, ax=ax2, label="移動コスト", shrink=0.8)

# コスト値をセルに表示
for i in range(GRID_SIZE):
    for j in range(GRID_SIZE):
        ax2.text(j, i, f"{cost_map[i, j]:.1f}", ha="center", va="center", fontsize=7, color="black")

for i in range(GRID_SIZE + 1):
    ax2.axhline(i - 0.5, color="gray", linewidth=0.5, alpha=0.5)
    ax2.axvline(i - 0.5, color="gray", linewidth=0.5, alpha=0.5)

ax2.set_xticks(range(GRID_SIZE))
ax2.set_yticks(range(GRID_SIZE))

plt.tight_layout()
st.pyplot(fig)
plt.close(fig)

# --- 結果表示 ---
st.divider()

if result is not None:
    path, total_cost = result
    col1, col2, col3 = st.columns(3)

    # 人がいない場合の最短経路コスト（基本コスト=1.0で計算）
    ideal_cost_map = np.ones_like(cost_map)
    ideal_result = a_star(ideal_cost_map, start, goal)
    ideal_cost = ideal_result[1] if ideal_result else 0

    time_loss = total_cost - ideal_cost

    col1.metric("経路コスト（合計）", f"{total_cost:.2f}")
    col2.metric("タイムロス（人流による増加分）", f"{time_loss:.2f}")
    col3.metric("経路ステップ数", f"{len(path)} セル")

    # 経路の詳細
    with st.expander("経路の詳細を表示"):
        st.write("**経路座標 (行, 列):**")
        path_str = " → ".join([f"({r},{c})" for r, c in path])
        st.code(path_str, language=None)
else:
    st.error("経路が見つかりませんでした。スタートとゴールの設定を確認してください。")
