"""
ロギング設定モジュール

アプリケーション全体で統一的なロギングを使用する。
"""

import logging
from pathlib import Path

from shared.config import LOG_LEVEL


def setup_logger(name: str) -> logging.Logger:
    """
    ロガーをセットアップする

    Args:
        name: ロガー名（通常は __name__ を渡す）

    Returns:
        ログ設定済みのロガーインスタンス
    """
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)

    # ハンドラが既に設定されていれば、スキップ
    if logger.hasHandlers():
        return logger

    # フォーマッター
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # コンソールハンドラ
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # ファイルハンドラ
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "ai_news_monitor.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(LOG_LEVEL)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
