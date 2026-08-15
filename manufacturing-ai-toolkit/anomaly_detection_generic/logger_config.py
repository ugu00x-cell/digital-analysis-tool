"""
共通ロギング設定モジュール

Windows 環境の cp932 問題を回避するため、
StreamHandler に utf-8 エンコーディングを明示する。
各モジュールでは `from logger_config import get_logger` を使う。
"""

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """utf-8 対応のロガーを返す。

    Args:
        name: ロガー名（通常は __name__ を渡す）

    Returns:
        設定済みの Logger インスタンス
    """
    logger = logging.getLogger(name)

    # 重複してハンドラーが追加されないようにする
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

    # ファイルハンドラー（utf-8 明示）
    fh = logging.FileHandler('app.log', encoding='utf-8')
    fh.setFormatter(fmt)

    # コンソールハンドラー（stdout を utf-8 で再設定）
    sh = logging.StreamHandler(stream=open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1, closefd=False))
    sh.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(sh)

    return logger
