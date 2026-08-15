"""
消込ツールのCLIエントリポイント。

使い方:
    python -m card_reconciliation \\
        --statements path/to/statements.csv \\
        --orders     path/to/orders.csv \\
        [--output-dir card_reconciliation/output]

引数省略時は、config.py の CREDIT_STATEMENT_FORMAT / ORDER_FORMAT に応じて
input/ 内から自動検出します（検索パターンは FORMAT_FILE_PATTERNS を参照）。

フォーマット切替は config.py の以下で管理します:
    CREDIT_STATEMENT_FORMAT: "bakuraku" / "jcb_manual" / "amazon_history"
    ORDER_FORMAT:            "amazon_orders" / "takenaka_korea"
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Callable

from card_reconciliation import config
from card_reconciliation.models.transaction import Order, Transaction
from card_reconciliation.services.loader import (
    load_amazon_history_as_statements,
    load_bakuraku_csv,
    load_combined_statements,
    load_jcb_manual_csv,
    load_order_csv,
    load_takenaka_order_csv,
)
from card_reconciliation.services.matcher import match_transactions
from card_reconciliation.services.reporter import build_summary, write_results_csv


# --- フォーマット別のファイル名パターンと ローダー関数のマップ ---
ORDER_LOADERS: dict[str, Callable[[Path], list[Order]]] = {
    "amazon_orders": load_order_csv,
    "takenaka_korea": load_takenaka_order_csv,
}

STATEMENT_LOADERS: dict[str, Callable[[Path], list[Transaction]]] = {
    "bakuraku": load_bakuraku_csv,
    "jcb_manual": load_jcb_manual_csv,
    "amazon_history": load_amazon_history_as_statements,
    "bakuraku_and_jcb": load_combined_statements,
}

ORDER_FILE_PATTERNS: dict[str, str] = {
    "amazon_orders": "orders_*.csv",
    "takenaka_korea": "takenaka_*.csv",
}

STATEMENT_FILE_PATTERNS: dict[str, str] = {
    "bakuraku": "bakuraku_*.csv",
    "jcb_manual": "jcb_manual_*.csv",
    "amazon_history": "amazon_*.csv",
    # 統合モードはローダ内で両方自動検出するが、存在チェック用に代表パターンを指定
    "bakuraku_and_jcb": "jcb_manual_*.csv",
}


def _setup_logging() -> None:
    """ロガーの初期設定（CLAUDE.mdのフォーマットに準拠）。"""
    # Windows(cp932)で絵文字が出せずUnicodeEncodeErrorが出るのを防ぐ
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("app.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


logger = logging.getLogger(__name__)


def _auto_detect(input_dir: Path, pattern: str) -> Path | None:
    """指定パターンに合うCSVを最終更新日時で最新を返す。"""
    candidates = sorted(
        input_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True
    )
    return candidates[0] if candidates else None


def _build_arg_parser() -> argparse.ArgumentParser:
    """CLI引数パーサを組み立てる。"""
    parser = argparse.ArgumentParser(
        description="クレカ明細×発注表 消込ツール",
    )
    parser.add_argument(
        "--statements",
        type=Path,
        default=None,
        help="クレカ明細CSVのパス（省略時は config.CREDIT_STATEMENT_FORMAT に応じて自動検出）",
    )
    parser.add_argument(
        "--orders",
        type=Path,
        default=None,
        help="発注表CSVのパス（省略時は config.ORDER_FORMAT に応じて自動検出）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=config.OUTPUT_DIR,
        help=f"出力先ディレクトリ（デフォルト: {config.OUTPUT_DIR}）",
    )
    return parser


def _resolve_input_paths(
    statements: Path | None,
    orders: Path | None,
) -> tuple[Path, Path]:
    """引数と自動検出から、明細/発注表CSVのパスを確定する。"""
    if statements is None:
        pattern = STATEMENT_FILE_PATTERNS.get(config.CREDIT_STATEMENT_FORMAT)
        if pattern is None:
            raise ValueError(f"未知の明細フォーマット: {config.CREDIT_STATEMENT_FORMAT}")
        statements = _auto_detect(config.INPUT_DIR, pattern)
    if orders is None:
        pattern = ORDER_FILE_PATTERNS.get(config.ORDER_FORMAT)
        if pattern is None:
            raise ValueError(f"未知の発注表フォーマット: {config.ORDER_FORMAT}")
        orders = _auto_detect(config.INPUT_DIR, pattern)

    if statements is None or not statements.exists():
        raise FileNotFoundError(
            f"明細CSVが見つかりません（format={config.CREDIT_STATEMENT_FORMAT}）。"
            f"--statements で明示するか、{config.INPUT_DIR} に "
            f"{STATEMENT_FILE_PATTERNS.get(config.CREDIT_STATEMENT_FORMAT)} を置いてください。"
        )
    if orders is None or not orders.exists():
        raise FileNotFoundError(
            f"発注表CSVが見つかりません（format={config.ORDER_FORMAT}）。"
            f"--orders で明示するか、{config.INPUT_DIR} に "
            f"{ORDER_FILE_PATTERNS.get(config.ORDER_FORMAT)} を置いてください。"
        )

    return statements, orders


def _load_statements(path: Path) -> list[Transaction]:
    """config.CREDIT_STATEMENT_FORMAT に応じたローダーで明細を読む。"""
    loader = STATEMENT_LOADERS.get(config.CREDIT_STATEMENT_FORMAT)
    if loader is None:
        raise ValueError(
            f"未知の明細フォーマット: {config.CREDIT_STATEMENT_FORMAT}。"
            f"有効: {list(STATEMENT_LOADERS.keys())}"
        )
    return loader(path)


def _load_orders(path: Path) -> list[Order]:
    """config.ORDER_FORMAT に応じたローダーで発注表を読む。"""
    loader = ORDER_LOADERS.get(config.ORDER_FORMAT)
    if loader is None:
        raise ValueError(
            f"未知の発注表フォーマット: {config.ORDER_FORMAT}。"
            f"有効: {list(ORDER_LOADERS.keys())}"
        )
    return loader(path)


def run(statements_path: Path, orders_path: Path, output_dir: Path) -> Path:
    """消込処理を実行し、出力CSVのパスを返す。"""
    transactions = _load_statements(statements_path)
    orders = _load_orders(orders_path)
    results = match_transactions(transactions, orders)

    output_path = write_results_csv(results, output_dir)
    summary = build_summary(results, transactions_count=len(transactions))

    print("")
    print(summary)
    print(f"\n出力ファイル: {output_path}")
    return output_path


def main() -> int:
    """CLIのメインエントリ。終了コードを返す。"""
    _setup_logging()
    args = _build_arg_parser().parse_args()

    try:
        statements_path, orders_path = _resolve_input_paths(args.statements, args.orders)
        run(statements_path, orders_path, args.output_dir)
    except FileNotFoundError as exc:
        logger.error("入力ファイルエラー: %s", exc)
        return 1
    except KeyError as exc:
        logger.error("CSVの列構成エラー: %s", exc)
        return 2
    except ValueError as exc:
        logger.error("設定エラー: %s", exc)
        return 3
    except Exception as exc:
        logger.exception("想定外のエラーが発生しました: %s", exc)
        return 99

    return 0


if __name__ == "__main__":
    sys.exit(main())
