"""誤差分布グラフ生成（クリーンレイアウト版）。"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import japanize_matplotlib  # noqa: F401
import numpy as np

from card_reconciliation import config

config.TAKENAKA_COL_DATE = "処理日"
config.ENABLE_NEGATIVE_DIFF_TOLERANCE = False

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

    pstart, pend = date(2026, 3, 16), date(2026, 3, 31)
    orders_in = [o for o in orders_all if pstart <= o.ordered_at <= pend]
    txs_in = [t for t in txs_all if pstart <= t.used_at <= pend]
    results = match_transactions(txs_in, orders_in)

    matched_tx_ids = {
        r.transaction.row_index
        for r in results
        if r.status_label == config.STATUS_MATCHED and r.transaction
    }
    matched_order_ids = {
        r.order.row_index
        for r in results
        if r.status_label == config.STATUS_MATCHED and r.order
    }
    unmatched_txs = [t for t in txs_in if t.row_index not in matched_tx_ids]
    unmatched_orders = [o for o in orders_in if o.row_index not in matched_order_ids]

    txs_by_date = defaultdict(list)
    for t in unmatched_txs:
        txs_by_date[t.used_at].append(t)
    orders_by_date = defaultdict(list)
    for o in unmatched_orders:
        orders_by_date[o.ordered_at].append(o)

    sus = [r for r in results if r.status_label == config.STATUS_SUSPICIOUS]
    gray = [r for r in results if r.status_label == config.STATUS_GRAY]

    diffs: list[int] = []
    for r in gray:
        o = r.order
        best = None
        for dd in range(-2, 3):
            for t in txs_by_date.get(o.ordered_at + timedelta(days=dd), []):
                d = t.amount - o.total
                if best is None or abs(d) < abs(best):
                    best = d
        if best is not None:
            diffs.append(best)
    for r in sus:
        tx = r.transaction
        best = None
        for dd in range(-2, 3):
            for o in orders_by_date.get(tx.used_at + timedelta(days=dd), []):
                d = tx.amount - o.total
                if best is None or abs(d) < abs(best):
                    best = d
        if best is not None:
            diffs.append(best)

    diffs_filtered = [d for d in diffs if -500 <= d <= 500]
    plus = sum(1 for d in diffs_filtered if d > 0)
    minus_small = sum(1 for d in diffs_filtered if -100 <= d < 0)
    minus_mid = sum(1 for d in diffs_filtered if -300 <= d < -100)
    minus_large = sum(1 for d in diffs_filtered if d < -300)
    no_cand = (len(sus) + len(gray)) - len(diffs_filtered)

    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 3, hspace=0.4, wspace=0.30, height_ratios=[1.2, 1])

    # --- 1. 上段大: ±200円ヒストグラム ---
    ax1 = fig.add_subplot(gs[0, :2])
    data_200 = [d for d in diffs if -200 <= d <= 200]
    bins = np.arange(-200, 201, 5)
    n_arr, bins_arr, patches = ax1.hist(data_200, bins=bins, edgecolor="white", alpha=0.85)
    for patch, b in zip(patches, bins_arr[:-1]):
        if b < -100:
            patch.set_facecolor("#e67e22")
        elif b < 0:
            patch.set_facecolor("#27ae60")
        else:
            patch.set_facecolor("#e74c3c")
    ax1.axvline(0, color="black", linestyle="--", linewidth=1.2, alpha=0.6, label="差額ゼロ")
    ax1.axvline(-100, color="#f39c12", linestyle="--", linewidth=1.2, alpha=0.7,
                label="マイナス差100円ライン")
    ax1.set_xlabel("差額（円）  JCB金額 − 発注表金額", fontsize=11)
    ax1.set_ylabel("件数", fontsize=11)
    ax1.set_title("差額の分布（±200円・5円刻み）", fontsize=13, fontweight="bold")
    ax1.legend(loc="upper right", fontsize=10)
    ax1.grid(axis="y", alpha=0.3)
    ymax = ax1.get_ylim()[1]
    ax1.text(-150, ymax * 0.85, "マイナス差大\n(修正対象範囲)", fontsize=9,
             ha="center", color="#e67e22")
    ax1.text(-50, ymax * 0.85, "マイナス差小\n(修正プロセス対象外)", fontsize=9,
             ha="center", color="#27ae60")
    ax1.text(100, ymax * 0.85, "プラス差\n(プロセス上発生しない想定)", fontsize=9,
             ha="center", color="#e74c3c")

    # --- 2. 右上: ±50円詳細 ---
    ax2 = fig.add_subplot(gs[0, 2])
    data_50 = [d for d in diffs if -50 <= d <= 50]
    bins50 = np.arange(-50, 51, 1)
    _, bins_arr2, patches2 = ax2.hist(data_50, bins=bins50, edgecolor="white", alpha=0.85)
    for patch, b in zip(patches2, bins_arr2[:-1]):
        if b < 0:
            patch.set_facecolor("#27ae60")
        else:
            patch.set_facecolor("#e74c3c")
    ax2.axvline(0, color="black", linestyle="--", linewidth=1, alpha=0.6)
    ax2.set_xlabel("差額（円）", fontsize=10)
    ax2.set_ylabel("件数", fontsize=10)
    ax2.set_title(f"±50円の詳細（1円刻み・{len(data_50)}件）",
                  fontsize=11, fontweight="bold")
    ax2.grid(axis="y", alpha=0.3)

    # --- 3. 左下: カテゴリ別 横棒 ---
    ax3 = fig.add_subplot(gs[1, 0])
    minus_101_200 = sum(1 for d in diffs_filtered if -200 <= d < -100)
    minus_201_300 = sum(1 for d in diffs_filtered if -300 <= d < -200)
    plus_1_100 = sum(1 for d in diffs_filtered if 0 < d <= 100)
    plus_101_200 = sum(1 for d in diffs_filtered if 100 < d <= 200)
    plus_201_300 = sum(1 for d in diffs_filtered if 200 < d <= 300)
    plus_over_300 = sum(1 for d in diffs_filtered if d > 300)
    # 発注表側の構造的余剰（明細件数より多い分は対応相手不在）
    structural_surplus = max(0, len(gray) - len(sus))
    labels_list = [
        "マイナス差\n1-100円",
        "プラス差\n1-100円",
        "プラス差\n101-200円",
        "プラス差\n201-300円",
        "プラス差\n300円超",
        "マイナス差\n101-200円",
        "マイナス差\n201-300円",
        "マイナス差\n300円超",
        f"発注表側\n構造的余剰",
    ]
    sizes = [
        minus_small, plus_1_100, plus_101_200, plus_201_300, plus_over_300,
        minus_101_200, minus_201_300, minus_large, structural_surplus,
    ]
    colors = [
        "#27ae60", "#e74c3c", "#e74c3c", "#e74c3c", "#e74c3c",
        "#f39c12", "#f39c12", "#e67e22", "#95a5a6",
    ]
    total = sum(sizes)
    bars = ax3.barh(range(len(labels_list)), sizes, color=colors,
                    edgecolor="white", alpha=0.9)
    ax3.set_yticks(range(len(labels_list)))
    ax3.set_yticklabels(labels_list, fontsize=9)
    ax3.invert_yaxis()
    for b, c in zip(bars, sizes):
        pct = c / total * 100 if total else 0
        if c > 0:
            ax3.text(b.get_width() + max(sizes) * 0.02,
                     b.get_y() + b.get_height() / 2,
                     f"{c}件 ({pct:.1f}%)", va="center", fontsize=9)
    ax3.set_xlabel("件数", fontsize=10)
    ax3.set_title(f"カテゴリ別件数（計{total}件）", fontsize=11, fontweight="bold")
    ax3.set_xlim(0, max(sizes) * 1.30)
    ax3.grid(axis="x", alpha=0.3)

    # --- 4. 中下: 差額の幅別件数（プラス・マイナス並列）---
    ax4 = fig.add_subplot(gs[1, 1])
    buckets = ["1-10円", "11-50円", "51-100円", "101-200円", "201-300円", "301-500円"]
    minus_counts = [
        sum(1 for d in diffs_filtered if -10 <= d < 0),
        sum(1 for d in diffs_filtered if -50 <= d < -10),
        sum(1 for d in diffs_filtered if -100 <= d < -50),
        sum(1 for d in diffs_filtered if -200 <= d < -100),
        sum(1 for d in diffs_filtered if -300 <= d < -200),
        sum(1 for d in diffs_filtered if -500 <= d < -300),
    ]
    plus_counts = [
        sum(1 for d in diffs_filtered if 0 < d <= 10),
        sum(1 for d in diffs_filtered if 10 < d <= 50),
        sum(1 for d in diffs_filtered if 50 < d <= 100),
        sum(1 for d in diffs_filtered if 100 < d <= 200),
        sum(1 for d in diffs_filtered if 200 < d <= 300),
        sum(1 for d in diffs_filtered if 300 < d <= 500),
    ]
    x = np.arange(len(buckets))
    width = 0.4
    bars_minus = ax4.bar(x - width / 2, minus_counts, width,
                          label="マイナス差", color="#27ae60",
                          edgecolor="white", alpha=0.9)
    bars_plus = ax4.bar(x + width / 2, plus_counts, width,
                         label="プラス差", color="#e74c3c",
                         edgecolor="white", alpha=0.9)
    ymax_local = max(minus_counts + plus_counts) if (minus_counts + plus_counts) else 1
    for bars, counts_arr in [(bars_minus, minus_counts), (bars_plus, plus_counts)]:
        for b, c in zip(bars, counts_arr):
            if c > 0:
                ax4.text(b.get_x() + b.get_width() / 2,
                         b.get_height() + ymax_local * 0.02,
                         str(c), ha="center", fontsize=9)
    ax4.set_xticks(x)
    ax4.set_xticklabels(buckets, fontsize=9)
    ax4.set_ylabel("件数", fontsize=10)
    ax4.set_title("差額の幅別件数（プラス・マイナス比較）",
                  fontsize=11, fontweight="bold")
    ax4.legend(loc="upper right", fontsize=9)
    ax4.grid(axis="y", alpha=0.3)

    # --- 5. 右下: サマリーテキスト ---
    ax5 = fig.add_subplot(gs[1, 2])
    ax5.axis("off")
    matched_count = sum(1 for r in results if r.status_label == config.STATUS_MATCHED)
    abs_avg = np.mean([abs(d) for d in diffs_filtered]) if diffs_filtered else 0
    minus_only = [d for d in diffs_filtered if d < 0]
    median_neg = np.median(minus_only) if minus_only else 0

    structural_surplus = max(0, len(gray) - len(sus))
    summary = (
        f"【消込結果サマリー（3/16-3/31）】\n"
        f"発注表 : {len(orders_in)} 件\n"
        f"明細   : {len(txs_in)} 件\n"
        f"\n"
        f"  ✅ 完全一致消込: {matched_count}件\n"
        f"     ({matched_count/len(txs_in)*100:.1f}%)\n"
        f"  🚨 要確認 (JCB側) : {len(sus)}件\n"
        f"  ⚠️ グレー (発注表側): {len(gray)}件\n"
        f"\n"
        f"【未マッチ分の差額傾向】\n"
        f"差の絶対値の平均: 約 {abs_avg:.0f}円\n"
        f"マイナス差の中央値: {median_neg:+.0f}円\n"
        f"\n"
        f"発注表側の構造的余剰: {structural_surplus}件\n"
        f"  (発注表が明細より{structural_surplus}件多く、\n"
        f"   構造的に対応相手不在)"
    )
    ax5.text(0.05, 0.95, summary, transform=ax5.transAxes,
             fontsize=10, verticalalignment="top",
             bbox=dict(boxstyle="round", facecolor="#f5f5f5", edgecolor="gray"))

    fig.suptitle("消込誤差の分布分析", fontsize=15, fontweight="bold", y=0.995)
    out = Path(config.OUTPUT_DIR) / "誤差分析グラフ_20260424.png"
    plt.savefig(out, dpi=130, bbox_inches="tight")
    plt.close()
    print(f"グラフ再生成: {out.name}")


if __name__ == "__main__":
    main()
