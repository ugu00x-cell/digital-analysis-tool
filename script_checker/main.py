"""スカッと動画 台本品質チェッカー CLIエントリポイント

使い方:
    py main.py input/台本.txt
    py main.py input/台本.md
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from services.checker import run_check_fix_loop

# .envファイルからAPIキーを読み込む
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def read_script(path: Path) -> str:
    """台本ファイルを読み込む

    Args:
        path: 台本ファイルのパス

    Returns:
        台本テキスト

    Raises:
        FileNotFoundError: ファイルが存在しない場合
    """
    if not path.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {path}")
    text = path.read_text(encoding="utf-8")
    logger.info("台本読み込み完了: %s（%d文字）", path.name, len(text))
    return text


def save_output(text: str, original_name: str) -> Path:
    """修正版台本を出力フォルダに保存する

    Args:
        text: 修正版台本テキスト
        original_name: 元ファイル名（拡張子なし）

    Returns:
        保存先のパス
    """
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{original_name}_fixed_{timestamp}.txt"
    output_path = output_dir / filename

    output_path.write_text(text, encoding="utf-8")
    logger.info("修正版保存: %s", output_path)
    return output_path


def save_check_log(reports: list, original_name: str) -> Path:
    """チェック結果ログを保存する

    Args:
        reports: CheckReportのリスト
        original_name: 元ファイル名（拡張子なし）

    Returns:
        保存先のパス
    """
    log_dir = Path("check_results")
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{original_name}_check_{timestamp}.txt"
    log_path = log_dir / filename

    # 全ループの結果を結合
    log_text = "\n\n".join(r.to_log_text() for r in reports)
    log_path.write_text(log_text, encoding="utf-8")
    logger.info("チェックログ保存: %s", log_path)
    return log_path


def main() -> None:
    """メイン処理：引数解析→チェック→修正→保存"""
    parser = argparse.ArgumentParser(
        description="スカッと動画 台本品質チェッカー"
    )
    parser.add_argument(
        "input_file",
        type=str,
        help="チェックする台本ファイルのパス",
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)

    try:
        # 台本読み込み
        script = read_script(input_path)

        # チェック＆修正ループ実行
        fixed_script, reports = run_check_fix_loop(script)

        # 結果の表示
        final_report = reports[-1]
        logger.info("=" * 50)
        logger.info(
            "最終結果: %d/%d 合格",
            final_report.passed_count,
            len(final_report.items),
        )

        # ファイル保存
        stem = input_path.stem
        save_output(fixed_script, stem)
        save_check_log(reports, stem)

        # 最終チェック結果を表示
        print("\n" + final_report.to_log_text())

    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error("予期しないエラー: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
