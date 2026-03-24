"""
QC7つ道具 統合ダッシュボード

製造DXコンサルタント向け提案デモ用。
7つの品質管理ツールを1画面に統合表示する。
"""

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.gridspec as gridspec
import matplotlib.patches as patches
import numpy as np
from scipy import stats
import seaborn as sns

# ===== 日本語フォント設定 =====
for _font in ["Yu Gothic", "Meiryo", "MS Gothic"]:
    if _font in {f.name for f in fm.fontManager.ttflist}:
        plt.rcParams["font.family"] = _font
        break
plt.rcParams["axes.unicode_minus"] = False


# ===== サンプルデータ生成 =====
def generate_sample_data():
    np.random.seed(42)
    data = {}

    # 1. パレート図
    data["pareto"] = {
        "寸法不良": 45, "傷": 30, "バリ": 10,
        "汚れ": 8, "欠け": 5, "その他": 2,
    }

    # 2. ヒストグラム
    data["histogram"] = {
        "values": np.random.normal(loc=50.0, scale=0.3, size=100),
        "usl": 51.0, "lsl": 49.0,
    }

    # 3. 散布図
    temp = np.random.uniform(20, 40, 50)
    data["scatter"] = {
        "x": temp,
        "y": 0.005 * temp + np.random.normal(0, 0.02, 50),
    }

    # 4. 管理図
    ctrl = np.random.normal(loc=50.0, scale=0.1, size=(25, 4))
    ctrl[14:18] += np.random.normal(loc=0.3, scale=0.15, size=(4, 4))
    data["control"] = ctrl

    # 5. 層別
    data["stratification"] = {
        "機械A": np.random.normal(50.0, 0.10, 100),
        "機械B": np.random.normal(50.0, 0.12, 100),
        "機械C": np.random.normal(50.3, 0.15, 100),
        "機械D": np.random.normal(50.0, 0.11, 100),
    }

    # 6. チェックシート
    base = np.array([
        [8, 6, 7, 5, 12],
        [4, 5, 3, 4,  8],
        [2, 3, 2, 1,  5],
        [1, 2, 1, 2,  3],
        [1, 0, 1, 1,  2],
    ])
    noise = np.random.randint(-1, 2, size=base.shape)
    data["checksheet"] = np.clip(base + noise, 0, None)

    # 7. 特性要因図
    data["fishbone"] = {
        "effect": "寸法不良",
        "causes": {
            "人":   ["作業ミス", "経験不足", "疲労"],
            "機械": ["工具摩耗", "振動", "精度低下"],
            "材料": ["材質バラツキ", "寸法誤差"],
            "方法": ["手順不備", "条件設定ミス"],
            "環境": ["温度変化", "湿度"],
            "測定": ["測定誤差", "器具不良"],
        },
    }
    return data


# ===== 各パネル描画関数 =====

def draw_pareto(ax, pareto_data):
    """パレート図"""
    items = sorted(pareto_data.items(), key=lambda x: x[1], reverse=True)
    labels = [k for k, _ in items]
    counts = [v for _, v in items]
    total = sum(counts)
    cum_pct = np.cumsum(counts) / total * 100

    x = range(len(labels))
    ax.bar(x, counts, color="#4472C4", edgecolor="white", zorder=2)
    for i, c in enumerate(counts):
        ax.text(i, c + total * 0.01, str(c), ha="center", fontsize=7, fontweight="bold")

    ax2 = ax.twinx()
    ax2.plot(x, cum_pct, color="#ED7D31", marker="o", linewidth=1.5, markersize=4, zorder=3)
    ax2.axhline(80, color="red", linestyle="--", linewidth=1, alpha=0.7)
    ax2.set_ylim(0, 105)
    ax2.tick_params(labelsize=7)
    ax2.set_ylabel("累積％", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.tick_params(labelsize=7)
    ax.set_title("① パレート図", fontsize=10, fontweight="bold")
    ax.set_ylabel("件数", fontsize=8)


def draw_histogram(ax, hist_data):
    """ヒストグラム＋規格線＋Cpk"""
    values = hist_data["values"]
    usl, lsl = hist_data["usl"], hist_data["lsl"]
    mean = np.mean(values)
    std = np.std(values, ddof=1)
    cpu = (usl - mean) / (3 * std)
    cpl = (mean - lsl) / (3 * std)
    cpk = min(cpu, cpl)

    ax.hist(values, bins=20, color="#4472C4", edgecolor="white", alpha=0.85, zorder=2)
    ax.axvline(usl, color="red", linestyle="--", linewidth=1.5, label=f"USL={usl}")
    ax.axvline(lsl, color="red", linestyle="--", linewidth=1.5, label=f"LSL={lsl}")
    ax.axvline(mean, color="#4472C4", linestyle="--", linewidth=1.5, label=f"平均={mean:.2f}")

    cpk_color = "#70AD47" if cpk >= 1.33 else "#ED7D31" if cpk >= 1.0 else "red"
    ax.text(0.03, 0.95, f"Cpk={cpk:.2f}", transform=ax.transAxes, fontsize=8,
            va="top", bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=cpk_color, lw=1.5))

    ax.legend(fontsize=6, loc="upper right")
    ax.tick_params(labelsize=7)
    ax.set_title("② ヒストグラム", fontsize=10, fontweight="bold")
    ax.set_ylabel("度数", fontsize=8)


def draw_scatter(ax, scatter_data):
    """散布図＋回帰直線"""
    x, y = scatter_data["x"], scatter_data["y"]
    slope, intercept, r, _, _ = stats.linregress(x, y)

    ax.scatter(x, y, color="#4472C4", edgecolor="white", s=25, alpha=0.8, zorder=2)
    x_line = np.linspace(x.min(), x.max(), 100)
    ax.plot(x_line, slope * x_line + intercept, color="#ED7D31", linewidth=1.5, zorder=3)

    r_color = "#70AD47" if abs(r) >= 0.7 else "#ED7D31" if abs(r) >= 0.4 else "#999"
    label = "強い正の相関" if r >= 0.7 else "強い負の相関" if r <= -0.7 else \
            "弱い相関" if abs(r) >= 0.4 else "相関なし"
    ax.text(0.03, 0.95, f"r={r:.3f}\n{label}", transform=ax.transAxes, fontsize=8,
            va="top", bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=r_color, lw=1.5))

    ax.tick_params(labelsize=7)
    ax.set_title("③ 散布図", fontsize=10, fontweight="bold")
    ax.set_xlabel("加工温度（℃）", fontsize=8)
    ax.set_ylabel("寸法誤差（mm）", fontsize=8)


def draw_control_chart(ax_xbar, ax_r, ctrl_data):
    """Xbar-R管理図（上下2段）"""
    A2, D3, D4 = 0.729, 0.000, 2.282  # n=4
    xbar = ctrl_data.mean(axis=1)
    r = ctrl_data.max(axis=1) - ctrl_data.min(axis=1)
    xbar_bar, r_bar = xbar.mean(), r.mean()

    xbar_ucl = xbar_bar + A2 * r_bar
    xbar_lcl = xbar_bar - A2 * r_bar
    r_ucl = D4 * r_bar

    x = np.arange(1, len(xbar) + 1)
    xbar_out = (xbar > xbar_ucl) | (xbar < xbar_lcl)
    r_out = r > r_ucl

    # Xbar
    ax_xbar.plot(x, xbar, marker="o", color="#4472C4", linewidth=1, markersize=3, zorder=2)
    ax_xbar.axhline(xbar_ucl, color="red", linewidth=1)
    ax_xbar.axhline(xbar_bar, color="#70AD47", linestyle="--", linewidth=1)
    ax_xbar.axhline(xbar_lcl, color="red", linewidth=1)
    if xbar_out.any():
        ax_xbar.scatter(x[xbar_out], xbar[xbar_out], color="red", s=50, zorder=3,
                        edgecolor="darkred", linewidth=1.5)
    ax_xbar.tick_params(labelsize=7)
    ax_xbar.set_title("④ 管理図（Xbar）", fontsize=10, fontweight="bold")
    ax_xbar.set_ylabel("Xbar", fontsize=8)

    # R
    ax_r.plot(x, r, marker="s", color="#ED7D31", linewidth=1, markersize=3, zorder=2)
    ax_r.axhline(r_ucl, color="red", linewidth=1)
    ax_r.axhline(r_bar, color="#70AD47", linestyle="--", linewidth=1)
    ax_r.axhline(0, color="red", linewidth=1)
    if r_out.any():
        ax_r.scatter(x[r_out], r[r_out], color="red", s=50, zorder=3,
                     edgecolor="darkred", linewidth=1.5)
    ax_r.tick_params(labelsize=7)
    ax_r.set_title("　　　　（R）", fontsize=10, fontweight="bold")
    ax_r.set_ylabel("R", fontsize=8)
    ax_r.set_xlabel("サブグループ", fontsize=8)


def draw_stratification(ax, strat_data):
    """層別グラフ（箱ひげ図）"""
    labels = list(strat_data.keys())
    values = [strat_data[k] for k in labels]
    overall_mean = np.mean(np.concatenate(values))

    bp = ax.boxplot(values, tick_labels=labels, patch_artist=True, widths=0.5,
                    medianprops=dict(color="white", linewidth=1.5),
                    whiskerprops=dict(linewidth=1), capprops=dict(linewidth=1))
    for patch in bp["boxes"]:
        patch.set_facecolor("#4472C4")
        patch.set_alpha(0.8)
    for i, vals in enumerate(values):
        ax.scatter(i + 1, np.mean(vals), marker="D", color="#ED7D31", s=30,
                   zorder=3, edgecolor="white", linewidth=1)
    ax.axhline(overall_mean, color="#70AD47", linestyle="--", linewidth=1)

    ax.tick_params(labelsize=7)
    ax.set_title("⑤ 層別グラフ", fontsize=10, fontweight="bold")
    ax.set_ylabel("寸法（mm）", fontsize=8)


def draw_checksheet(ax, cs_data):
    """チェックシート（ヒートマップ）"""
    defects = ["寸法不良", "傷", "バリ", "汚れ", "欠け"]
    days = ["月", "火", "水", "木", "金"]

    sns.heatmap(cs_data, annot=True, fmt="d", cmap="YlOrRd",
                xticklabels=days, yticklabels=defects,
                linewidths=0.5, linecolor="white",
                cbar=False, ax=ax)
    ax.tick_params(labelsize=7)
    ax.set_title("⑥ チェックシート", fontsize=10, fontweight="bold")


def draw_fishbone(ax, fb_data):
    """特性要因図（魚の骨図）"""
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(-3.5, 3.5)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("⑦ 特性要因図", fontsize=10, fontweight="bold")

    spine_y = 0
    # 背骨
    ax.annotate("", xy=(9.0, spine_y), xytext=(0.5, spine_y),
                arrowprops=dict(arrowstyle="->,head_width=0.3,head_length=0.2",
                                lw=2, color="#333"))
    # 魚の頭
    rect = patches.FancyBboxPatch((9.1, -0.4), 1.3, 0.8,
                                   boxstyle="round,pad=0.1",
                                   fc="#FF6B6B", ec="#CC3333", lw=1.5)
    ax.add_patch(rect)
    ax.text(9.75, spine_y, fb_data["effect"], fontsize=8, fontweight="bold",
            color="white", ha="center", va="center")

    causes = list(fb_data["causes"].items())
    x_pos = [1.8, 4.2, 6.6]
    colors_top = ["#4472C4", "#ED7D31", "#70AD47"]
    colors_bot = ["#9B59B6", "#E74C3C", "#1ABC9C"]

    for i, (cat, subs) in enumerate(causes):
        col_idx = i // 2
        is_top = (i % 2 == 0)
        bx = x_pos[col_idx]
        sign = 1 if is_top else -1
        color = colors_top[col_idx] if is_top else colors_bot[col_idx]

        tx = bx - 1.2
        ty = sign * 2.2

        ax.annotate("", xy=(bx, spine_y), xytext=(tx, ty),
                    arrowprops=dict(arrowstyle="->,head_width=0.15,head_length=0.1",
                                    lw=1.5, color=color))
        ax.text(tx - 0.1, ty + sign * 0.25, cat, fontsize=8, fontweight="bold",
                color=color, ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=color, lw=1))

        for j, sub in enumerate(subs):
            t = (j + 1) / (len(subs) + 1)
            ax_x = tx + t * (bx - tx)
            ax_y = ty + t * (spine_y - ty)
            ax.plot([ax_x - 0.8, ax_x], [ax_y, ax_y], color=color, lw=0.8)
            ax.text(ax_x - 0.85, ax_y, sub, fontsize=6, color="#333",
                    ha="right", va="center")


# ===== メイン =====
def create_dashboard():
    data = generate_sample_data()

    fig = plt.figure(figsize=(18, 22))
    fig.patch.set_facecolor("#F5F5F5")

    # タイトル
    fig.text(0.5, 0.975, "QC7つ道具 統合ダッシュボード",
             ha="center", va="top", fontsize=20, fontweight="bold", color="#333")
    fig.text(0.5, 0.96, "― 製造DXコンサルティング 提案デモ ―",
             ha="center", va="top", fontsize=12, color="#666")

    gs = gridspec.GridSpec(4, 3, hspace=0.35, wspace=0.3,
                           top=0.94, bottom=0.03, left=0.06, right=0.96)

    # Row 0: パレート図 | ヒストグラム | 散布図
    ax_pareto = fig.add_subplot(gs[0, 0])
    ax_hist = fig.add_subplot(gs[0, 1])
    ax_scatter = fig.add_subplot(gs[0, 2])

    # Row 1: 管理図Xbar | 管理図R | 層別
    ax_xbar = fig.add_subplot(gs[1, 0])
    ax_r = fig.add_subplot(gs[1, 1])
    ax_strat = fig.add_subplot(gs[1, 2])

    # Row 2: チェックシート | 特性要因図（2列分）
    ax_cs = fig.add_subplot(gs[2, 0])
    ax_fb = fig.add_subplot(gs[2, 1:])

    # Row 3: サマリーパネル（3列分）
    ax_summary = fig.add_subplot(gs[3, :])

    # 各パネル描画
    draw_pareto(ax_pareto, data["pareto"])
    draw_histogram(ax_hist, data["histogram"])
    draw_scatter(ax_scatter, data["scatter"])
    draw_control_chart(ax_xbar, ax_r, data["control"])
    draw_stratification(ax_strat, data["stratification"])
    draw_checksheet(ax_cs, data["checksheet"])
    draw_fishbone(ax_fb, data["fishbone"])

    # サマリーパネル
    draw_summary(ax_summary, data)

    plt.show()

    # テキストサマリー
    print_summary(data)


def draw_summary(ax, data):
    """分析サマリーパネル"""
    ax.axis("off")
    ax.set_facecolor("#2C3E50")
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("#2C3E50")
        spine.set_linewidth(2)

    # Cpk計算
    h = data["histogram"]
    mean = np.mean(h["values"])
    std = np.std(h["values"], ddof=1)
    cpk = min((h["usl"] - mean) / (3 * std), (mean - h["lsl"]) / (3 * std))

    # 相関係数
    s = data["scatter"]
    r = stats.linregress(s["x"], s["y"])[2]

    # 管理図異常
    ctrl = data["control"]
    A2, D4 = 0.729, 2.282
    xbar = ctrl.mean(axis=1)
    r_vals = ctrl.max(axis=1) - ctrl.min(axis=1)
    xbar_bar, r_bar = xbar.mean(), r_vals.mean()
    xbar_out = ((xbar > xbar_bar + A2 * r_bar) | (xbar < xbar_bar - A2 * r_bar))
    anomaly_groups = np.where(xbar_out)[0] + 1

    # パレート上位80%
    items = sorted(data["pareto"].items(), key=lambda x: x[1], reverse=True)
    total = sum(v for _, v in items)
    cum = 0
    top80 = []
    for k, v in items:
        cum += v
        top80.append(k)
        if cum / total >= 0.8:
            break

    # チェックシート
    cs = data["checksheet"]
    days = ["月", "火", "水", "木", "金"]
    worst_day = days[cs.sum(axis=0).argmax()]

    lines = [
        "【分析サマリー】",
        "",
        f"  パレート分析    上位80%を占める不良: {', '.join(top80)}    → 重点対策対象",
        f"  工程能力        Cpk = {cpk:.2f}{'  ✓ 安定' if cpk >= 1.33 else '  ▲ 要改善'}",
        f"  相関分析        加工温度 vs 寸法誤差  r = {r:.3f}    → {'温度管理が有効' if abs(r) >= 0.7 else '要追加調査'}",
        f"  管理図          異常検出: グループ {', '.join(map(str, anomaly_groups))}    → 原因調査が必要",
        f"  層別分析        機械Cの平均値が他機械より+0.3mmシフト    → 個別調整が必要",
        f"  チェックシート  不良最多曜日: {worst_day}曜日    → 週末の疲労・段取り替えの影響を調査",
    ]

    text = "\n".join(lines)
    ax.text(0.05, 0.5, text, transform=ax.transAxes, fontsize=10,
            va="center", ha="left", color="white",
            linespacing=1.8)


def print_summary(data):
    """テキストサマリー出力"""
    h = data["histogram"]
    mean = np.mean(h["values"])
    std = np.std(h["values"], ddof=1)
    cpk = min((h["usl"] - mean) / (3 * std), (mean - h["lsl"]) / (3 * std))

    s = data["scatter"]
    r = stats.linregress(s["x"], s["y"])[2]

    print("=" * 60)
    print("  QC7つ道具 統合ダッシュボード - 分析サマリー")
    print("=" * 60)
    print(f"  Cpk:        {cpk:.2f}")
    print(f"  相関係数 r: {r:.3f}")
    print(f"  管理図:     グループ15〜18に異常検出")
    print(f"  層別:       機械Cに平均シフトあり")
    print(f"  最多不良:   寸法不良（45件）")
    print(f"  最多曜日:   金曜日")
    print("=" * 60)


if __name__ == "__main__":
    create_dashboard()
