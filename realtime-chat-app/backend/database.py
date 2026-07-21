"""
PostgreSQL接続管理モジュール

asyncpgのコネクションプールを一元管理する。
判定軸: PostgreSQLを選ぶ理由
- 外部キー制約でルーム/ユーザー/メッセージの整合性をDB側で保証できる
  （Firebase等のJSON型DBでは参照整合性チェックをアプリ側で実装する必要がある）
- インデックス（idx_room_timestamp）で大量メッセージ時の検索性能を確保できる
"""

import logging
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://chat_user:chat_password@localhost:5432/chat_db",
)

_pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    """コネクションプールを初期化する"""
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    logger.info("PostgreSQLコネクションプール初期化完了")


async def close_pool() -> None:
    """コネクションプールを閉じる（graceful shutdown）"""
    if _pool is not None:
        await _pool.close()
        logger.info("PostgreSQLコネクションプールを終了しました")


def get_pool() -> asyncpg.Pool:
    """初期化済みのコネクションプールを取得する

    Raises:
        RuntimeError: プール未初期化の場合
    """
    if _pool is None:
        raise RuntimeError("コネクションプールが初期化されていません")
    return _pool
