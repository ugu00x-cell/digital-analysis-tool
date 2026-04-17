"""
消込ツールのCLIエントリポイント。

使い方:
    python -m card_reconciliation.main \\
        --bakuraku path/to/bakuraku.csv \\
        --orders path/to/orders.csv \\
        [--output-dir card_reconciliation/output]

引数を省略した場合、--bakuraku と --orders は INPUT_DIR 内の
それぞれ「bakuraku_*.csv」「orders_*.csv」から自動検出します。
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from card_reconciliation import config
from card_reconciliation.services.loader import load_bakuraku_csv, load_order_csv
from card_reconciliation.services.matcher import match_transactions
from card_reconciliation.services.reporter import build_summary, write_results_csv


def _setup_logging() -> None:
    """ロガーの初期設定（CLAUDE.mdのフォーマットに準拠）。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("app.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


logger = logging.getLogger(__name__)


def _auto_detect(input_dir: Path, pattern: str) -> Path | None:
    """指定パターンに合うCSVが1つだけあれば返す（複数は最新を選ぶ）。"""
    candidates = sorted(input_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _build_arg_parser() -> argparse.ArgumentParser:
    """CLI引数パーサを組み立てる。"""
    parser = argparse.ArgumentParser(
        description="バク楽クレカ明細×発注表の消込ツール",
    )
    parser.add_argument(
        "--bakuraku",
        type=Path,
        default=None,
        help="バク楽CSVのパス（省略時は input/ 内の bakuraku_*.csv を自動検出）",
    )
    parser.add_argument(
        "--orders",
        type=Path,
        default=None,
        help="発注表CSVのパス（省略時は input/ 内の orders_*.csv を自動検出）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=config.OUTPUT_DIR,
        help=f"出力先ディレクトリ（デフォルト: {config.OUTPUT_DIR}）",
    )
    return parser


def _resolve_input_paths(
    bakuraku: Path | None,
    orders: Path | None,
) -> tuple[Path, Path]:
    """引数と自動検出から、バク楽/発注表CSVのパスを確定する。"""
    if bakuraku is None:
        bakuraku = _auto_detect(config.INPUT_DIR, "bakuraku_*.csv")
    if orders is None:
        orders = _auto_detect(config.INPUT_DIR, "orders_*.csv")

    if bakuraku is None or not bakuraku.exists():
        raise FileNotFoundError(
            f"バク楽CSVが見つかりません。--bakuraku で明示するか、"
            f"{config.INPUT_DIR} に bakuraku_*.csv を置いてください。"
        )
    if orders is None or not orders.exists():
        raise FileNotFoundError(
            f"発注表CSVが見つかりません。--orders で明示するか、"
            f"{config.INPUT_DIR} に orders_*.csv を置いてください。"
        )

    return bakuraku, orders


def run(bakuraku_path: Path, orders_path: Path, output_dir: Path) -> Path:
    """
    消込処理を実行し、出力CSVのパスを返す（ライブラリとしても使えるよう分離）。

    Args:
        bakuraku_path: バク楽CSVのパス
        orders_path: 発注表CSVのパス
        output_dir: 出力先ディレクトリ

    Returns:
        書き出した消込結果CSVのパス
    """
    transactions = load_bakuraku_csv(bakuraku_path)
    orders = load_order_csv(orders_path)
    results = match_transactions(transactions, orders)

    output_path = write_results_csv(results, output_dir)
    summary = build_summary(results, transactions_count=len(transactions))

    # コンソールに見やすく表示
    print("")
    print(summary)
    print(f"\n出力ファイル: {output_path}")
    return output_path


def main() -> int:
    """CLIのメインエントリ。終了コードを返す。"""
    _setup_logging()
    args = _build_arg_parser().parse_args()

    try:
        bakuraku_path, orders_path = _resolve_input_paths(args.bakuraku, args.orders)
        run(bakuraku_path, orders_path, args.output_dir)
    except FileNotFoundError as exc:
        logger.error("入力ファイルエラー: %s", exc)
        return 1
    except KeyError as exc:
        logger.error("CSVの列構成エラー: %s", exc)
        return 2
    except Exception as exc:
        logger.exception("想定外のエラーが発生しました: %s", exc)
        return 99

    return 0


if __name__ == "__main__":
    sys.exit(main())
