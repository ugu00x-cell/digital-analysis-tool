"""DB操作 - 送信進捗の管理（途中再開用）"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from utils.db import _conn

logger = logging.getLogger(__name__)


def create_session(total: int) -> str:
    """新しい送信セッションを作成する

    Args:
        total: 送信対象の総件数

    Returns:
        セッションID
    """
    conn = _conn()
    sid = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO send_progress "
        "(session_id, total, current_index, status, started_at) "
        "VALUES (?, ?, 0, 'running', ?)",
        (sid, total, now),
    )
    conn.commit()
    conn.close()
    logger.info("セッション作成: %s (全%d件)", sid, total)
    return sid


def update_progress(sid: str, index: int) -> None:
    """進捗を更新する"""
    conn = _conn()
    conn.execute(
        "UPDATE send_progress SET current_index = ? "
        "WHERE session_id = ?",
        (index, sid),
    )
    conn.commit()
    conn.close()


def finish_session(sid: str, status: str = "completed") -> None:
    """セッションを完了にする"""
    conn = _conn()
    conn.execute(
        "UPDATE send_progress SET status = ? WHERE session_id = ?",
        (status, sid),
    )
    conn.commit()
    conn.close()
    logger.info("セッション終了: %s (%s)", sid, status)


def get_incomplete_session() -> Optional[dict]:
    """未完了セッションを取得する"""
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM send_progress WHERE status = 'running' "
        "ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def clear_sessions() -> None:
    """全セッションをクリアする"""
    conn = _conn()
    conn.execute("DELETE FROM send_progress")
    conn.commit()
    conn.close()
