"""3/23 のJCB明細の差額グラフ生成（要確認25件分析）。"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import japanize_matplotlib  # noqa: F401
import numpy as np

from card_reconciliation import config

config.TAKENAKA_COL_DATE = "処理日"

from card_reconciliation.services.loader import (
    load_takenaka_order_csv,
    load_combined_statements,
)
from card_reconciliation.services.matcher import match_transactions

import logging

logging.disable(logging.CRITICAL)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    orders_all = load_takenaka_order_csv(
        Path("card_reconciliation/input/takenaka_202604_sample.csv")
    )
    txs_all = load_combined_statements(
        Path("card_reconciliation/input/jcb_manual_sample.csv")
    )
    orders_in = [
        o for o in orders_all if date(2026, 3, 16) <= o.ordered_at <= date(2026, 3, 31)
    ]
    target = date(2026, 3, 23)
    txs_in = [t for t in txs_all if t.used_at == target]
    results = match_transactions(txs_in, orders_in)

    matched = [r for r in results if r.status_label == config.STATUS_MATCHED]
    sus = [r for r in results if r.status_label == config.STATUS_SUSPICIOUS]

    matched_order_ids = {
        r.order.row_index
        for r in results
        if r.status_label == config.STATUS_MATCHED and r.order
    }
    unmatched_orders = [o for o in orders_in if o.row_index not in matched_order_ids]
    orders_by_date = defaultdict(list)
    for o in unmatched_orders:
        orders_by_date[o.ordered_at].append(o)

    diffs: list[int] = []
    for r in sus:
        tx = r.transaction
        best_d = None
        for dd in range(-3, 4):
            for o in orders_by_date.get(tx.used_at + timedelta(days=dd), []):
                d = tx.amount - o.total
                if best_d is None or abs(d) < abs(best_d):
                    best_d = d
        if best_d is not None:
            diffs.append(best_d)

    fig = plt.figure(figsize=(14, 8))
    gs = fig.add_gridspec(2, 2, hspace=0.40, wspace=0.30, height_ratios=[1, 1])

    # 上左: ±200円ヒストグラム
    ax1 = fig.add_subplot(gs[0, 0])
    bins = np.arange(-200, 201, 10)
    n_arr, bins_arr, patches = ax1.hist(
        [d for d in diffs if -200 <= d <= 200],
        bins=bins,
        edgecolor="white",
        alpha=0.85,
    )
    for patch, b in zip(patches, bins_arr[:-1]):
        if b < 0:
            patch.set_facecolor("#27ae60")
        else:
            patch.set_facecolor("#e74c3c")
    ax1.axvline(0, color="black", linestyle="--", linewidth=1)
    ax1.set_xlabel("差額（円） JCB金額 − 発注表金額", fontsize=10)
    ax1.set_ylabel("件数", fontsize=10)
    ax1.set_title("差額の分布（±200円・10円刻み）", fontsize=11, fontweight="bold")
    ax1.grid(axis="y", alpha=0.3)

    # 上右: 差額幅別
    ax2 = fig.add_subplot(gs[0, 1])
    buckets = [
        "±10円以内",
        "±11-50円",
        "±51-100円",
        "±101-300円",
        "±300円超",
    ]
    counts = [
        sum(1 for d in diffs if abs(d) <= 10),
        sum(1 for d in diffs if 11 <= abs(d) <= 50),
        sum(1 for d in diffs if 51 <= abs(d) <= 100),
        sum(1 for d in diffs if 101 <= abs(d) <= 300),
        sum(1 for d in diffs if abs(d) > 300),
    ]
    colors_bar = ["#27ae60", "#27ae60", "#27ae60", "#f39c12", "#e67e22"]
    bars = ax2.bar(buckets, counts, color=colors_bar, edgecolor="white", alpha=0.9)
    ymax = max(counts) if counts else 1
    for b, c in zip(bars, counts):
        if c > 0:
            ax2.text(
                b.get_x() + b.get_width() / 2,
                b.get_height() + ymax * 0.03,
                str(c),
                ha="center",
                fontsize=10,
            )
    ax2.set_ylabel("件数", fontsize=10)
    ax2.set_title(f"差額幅別の件数（要確認 計{len(diffs)}件）",
                  fontsize=11, fontweight="bold")
    ax2.tick_params(axis="x", labelsize=9)
    ax2.grid(axis="y", alpha=0.3)

    # 下左: プラス/マイナス比較
    ax3 = fig.add_subplot(gs[1, 0])
    plus_count = sum(1 for d in diffs if d > 0)
    minus_count = sum(1 for d in diffs if d < 0)
    ax3.bar(["マイナス差\n(JCB<発注表)", "プラス差\n(JCB>発注表)"],
            [minus_count, plus_count],
            color=["#27ae60", "#e74c3c"], edgecolor="white", alpha=0.9)
    ax3.text(0, minus_count + 0.3, str(minus_count), ha="center", fontsize=11)
    ax3.text(1, plus_count + 0.3, str(plus_count), ha="center", fontsize=11)
    ax3.set_ylabel("件数", fontsize=10)
    ax3.set_title("プラス/マイナスの分布", fontsize=11, fontweight="bold")
    ax3.grid(axis="y", alpha=0.3)

    # 下右: サマリー
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.axis("off")
    abs_avg = np.mean([abs(d) for d in diffs]) if diffs else 0
    abs_max = max(abs(d) for d in diffs) if diffs else 0
    summary = (
        "【消込結果サマリー】\n"
        f"対象: JCB+バク楽 利用日 = 3/23（月）\n"
        f"発注表: 処理日 3/16-3/31 (465件)\n"
        f"明細  : 73件\n"
        f"\n"
        f"  ✅ 消込: {len(matched)}件\n"
        f"     ({len(matched)/len(txs_in)*100:.1f}%)\n"
        f"  🚨 要確認: {len(sus)}件\n"
        f"\n"
        f"【差額分析】\n"
        f"差の絶対値 平均: {abs_avg:.0f}円\n"
        f"差の絶対値 最大: {abs_max}円\n"
        f"\n"
        f"※±50円以内: "
        f"{sum(1 for d in diffs if abs(d) <= 50)}件 "
        f"({sum(1 for d in diffs if abs(d) <= 50)/len(diffs)*100:.0f}%)\n"
        f"  → 大半が微小ズレ（正常範囲）"
    )
    ax4.text(
        0.05, 0.95, summary, transform=ax4.transAxes,
        fontsize=10, verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="#f5f5f5", edgecolor="gray"),
    )

    fig.suptitle("3/23 JCB明細の差額分析（発注表3/16-3/31期間）",
                 fontsize=14, fontweight="bold", y=0.995)
    out = Path(config.OUTPUT_DIR) / "差額分析グラフ_JCB3月23日_20260426.png"
    plt.savefig(out, dpi=130, bbox_inches="tight")
    plt.close()
    print(f"グラフ出力: {out.name}")


if __name__ == "__main__":
    main()
