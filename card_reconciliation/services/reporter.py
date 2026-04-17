"""消込結果をCSVに書き出し、サマリーを文字列で返すモジュール。"""
from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from card_reconciliation import config
from card_reconciliation.models.transaction import MatchResult

logger = logging.getLogger(__name__)


# 出力CSVの列名（後から変えたい場合はここを書き換えるだけで済ませる）
OUTPUT_COLUMNS: tuple[str, ...] = (
    "利用日時",
    "金額",
    "当初取引内容",
    "バク楽ステータス",
    "マッチした注文日",
    "商品名A",
    "消込ステータス",
    "備考",
)


def _result_to_row(result: MatchResult) -> dict[str, object]:
    """MatchResult 1件を、出力CSV用の dict に変換する。"""
    tx = result.transaction
    order = result.order

    return {
        "利用日時": tx.used_at.isoformat() if tx else "",
        "金額": tx.amount if tx else "",
        "当初取引内容": tx.store if tx else "",
        "バク楽ステータス": tx.status if tx else "",
        "マッチした注文日": order.ordered_at.isoformat() if order else "",
        "商品名A": order.product if order else "",
        "消込ステータス": result.status_label,
        "備考": result.note,
    }


def write_results_csv(
    results: list[MatchResult],
    output_dir: Path,
    run_date: date | None = None,
) -> Path:
    """
    消込結果をCSVに書き出し、書き出したファイルパスを返す。

    Args:
        results: マッチング結果のリスト
        output_dir: 出力先ディレクトリ
        run_date: ファイル名に使う日付（未指定なら今日）

    Returns:
        書き出したCSVのパス
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    target_date = run_date or date.today()
    filename = f"{config.OUTPUT_FILENAME_PREFIX}{target_date.strftime('%Y%m%d')}.csv"
    path = output_dir / filename

    rows = [_result_to_row(r) for r in results]
    df = pd.DataFrame(rows, columns=list(OUTPUT_COLUMNS))
    df.to_csv(path, index=False, encoding=config.OUTPUT_ENCODING)

    logger.info("消込結果CSVを書き出しました: %s (%d件)", path, len(rows))
    return path


def build_summary(results: list[MatchResult], transactions_count: int) -> str:
    """
    消込サマリーを人間向けの文字列にして返す。

    Args:
        results: マッチング結果のリスト
        transactions_count: バク楽の確定明細の件数（対象件数）

    Returns:
        サマリー文字列（複数行）
    """
    matched = sum(1 for r in results if r.status_label == config.STATUS_MATCHED)
    recalc = sum(1 for r in results if r.status_label == config.STATUS_MATCHED_RECALC)
    suspicious = sum(1 for r in results if r.status_label == config.STATUS_SUSPICIOUS)
    gray = sum(1 for r in results if r.status_label == config.STATUS_GRAY)

    lines = [
        "=== 消込サマリー ===",
        f"対象件数（バク楽）: {transactions_count}件",
        f"{config.STATUS_MATCHED}: {matched}件",
        f"{config.STATUS_MATCHED_RECALC}: {recalc}件",
        f"{config.STATUS_SUSPICIOUS}: {suspicious}件",
        f"{config.STATUS_GRAY}: {gray}件",
    ]
    return "\n".join(lines)
