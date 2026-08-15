"""
差額サンプルCSV生成スクリプト。

期間内のグレー／要確認のうち、同日に ±200円以内の候補がある組を抽出し、
価格変動・差額検証用のサンプルCSVに出力する。

使い方:
    python -m card_reconciliation.analyze_diff

出力先:
    card_reconciliation/output/差額サンプル_YYYYMMDD.csv
"""
from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from card_reconciliation import config
from card_reconciliation.services.loader import (
    load_jcb_manual_csv,
    load_takenaka_order_csv,
)
from card_reconciliation.services.matcher import match_transactions


# 差額として採用する絶対値の上限（これを超える組は別注文のノイズと判定）
DIFF_MAX_ABS: int = 200

# 出力列名（ユーザ（クライアント）向けに分かりやすい名称）
OUTPUT_COLUMNS: tuple[str, ...] = (
    "種別",
    "日付",
    "商品名／JCB店名",
    "発注表 仕入れ総額(円)",
    "JCB請求額(円)",
    "差額(円)",
    "差額率(%)",
    "備考",
)


def _setup_logging() -> None:
    """UTF-8ログ出力設定。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def _find_near_matches_for_gray(
    gray_orders: list,
    txs: list,
) -> list[dict]:
    """
    グレー発注に対し、同日で金額差がDIFF_MAX_ABS以内の最近傍JCB明細を探す。

    Returns:
        dict のリスト（OUTPUT_COLUMNS に対応するキー）
    """
    rows: list[dict] = []
    for r in gray_orders:
        o = r.order
        same_day = [tx for tx in txs if tx.used_at == o.ordered_at]
        if not same_day:
            continue
        best = min(same_day, key=lambda tx: abs(tx.amount - o.total))
        diff = best.amount - o.total
        if abs(diff) > DIFF_MAX_ABS or diff == 0:
            continue

        rows.append(
            {
                "種別": "グレー（発注表のみ）",
                "日付": o.ordered_at.isoformat(),
                "商品名／JCB店名": o.product[:60],
                "発注表 仕入れ総額(円)": o.total,
                "JCB請求額(円)": best.amount,
                "差額(円)": diff,
                "差額率(%)": round(diff / o.total * 100, 2) if o.total else 0,
                "備考": "同日のJCB最近傍候補",
            }
        )
    return rows


def _find_near_matches_for_suspicious(
    suspicious_txs: list,
    orders: list,
) -> list[dict]:
    """
    要確認トランザクションに対し、同日で金額差がDIFF_MAX_ABS以内の最近傍発注を探す。
    """
    rows: list[dict] = []
    for r in suspicious_txs:
        tx = r.transaction
        same_day = [o for o in orders if o.ordered_at == tx.used_at]
        if not same_day:
            continue
        best = min(same_day, key=lambda o: abs(tx.amount - o.total))
        diff = tx.amount - best.total
        if abs(diff) > DIFF_MAX_ABS or diff == 0:
            continue

        rows.append(
            {
                "種別": "要確認（JCBのみ）",
                "日付": tx.used_at.isoformat(),
                "商品名／JCB店名": f"{best.product[:50]} (JCB店名: {tx.store[:20]})",
                "発注表 仕入れ総額(円)": best.total,
                "JCB請求額(円)": tx.amount,
                "差額(円)": diff,
                "差額率(%)": round(diff / best.total * 100, 2) if best.total else 0,
                "備考": "同日の発注表最近傍候補",
            }
        )
    return rows


def build_diff_sample(
    takenaka_path: Path,
    jcb_path: Path,
    period_start: date,
    period_end: date,
) -> list[dict]:
    """差額サンプル行のリストを生成する。"""
    orders = load_takenaka_order_csv(takenaka_path)
    txs = load_jcb_manual_csv(jcb_path)

    results = match_transactions(txs, orders)

    # 期間内のグレー／要確認のみ対象
    gray_in = [
        r
        for r in results
        if r.status_label == config.STATUS_GRAY
        and r.order is not None
        and period_start <= r.order.ordered_at <= period_end
    ]
    sus_in = [
        r
        for r in results
        if r.status_label == config.STATUS_SUSPICIOUS
        and r.transaction is not None
        and period_start <= r.transaction.used_at <= period_end
    ]

    rows = _find_near_matches_for_gray(gray_in, txs)
    rows.extend(_find_near_matches_for_suspicious(sus_in, orders))

    # 日付 → 差額の絶対値 の順でソート（クライアントが見やすいように）
    rows.sort(key=lambda r: (r["日付"], abs(r["差額(円)"])))
    return rows


def main() -> int:
    """CLIエントリ。差額サンプルCSVを生成。"""
    _setup_logging()

    takenaka_path = next(config.INPUT_DIR.glob("takenaka_*.csv"), None)
    jcb_path = next(config.INPUT_DIR.glob("jcb_manual_*.csv"), None)
    if takenaka_path is None or jcb_path is None:
        logging.error("発注表またはJCB明細ファイルが見つかりません")
        return 1

    # JCB明細の期間を自動検出
    txs = load_jcb_manual_csv(jcb_path)
    period_start = min(t.used_at for t in txs)
    period_end = max(t.used_at for t in txs)
    logging.info("分析対象期間: %s 〜 %s", period_start, period_end)

    rows = build_diff_sample(takenaka_path, jcb_path, period_start, period_end)

    df = pd.DataFrame(rows, columns=list(OUTPUT_COLUMNS))
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.OUTPUT_DIR / f"差額サンプル_{date.today().strftime('%Y%m%d')}.csv"
    df.to_csv(out_path, index=False, encoding=config.OUTPUT_ENCODING)

    # 簡易サマリー
    print(f"\n差額サンプル: {len(rows)}件")
    gray_count = sum(1 for r in rows if r["種別"].startswith("グレー"))
    sus_count = sum(1 for r in rows if r["種別"].startswith("要確認"))
    plus_count = sum(1 for r in rows if r["差額(円)"] > 0)
    minus_count = sum(1 for r in rows if r["差額(円)"] < 0)
    print(f"  グレー（発注表のみ）: {gray_count}件")
    print(f"  要確認（JCBのみ） : {sus_count}件")
    print(f"  プラス差: {plus_count}件 / マイナス差: {minus_count}件")
    print(f"\n出力ファイル: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
