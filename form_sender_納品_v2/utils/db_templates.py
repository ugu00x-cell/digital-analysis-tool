"""DB操作 - 送信テンプレートのCRUD"""

import logging
from datetime import datetime
from typing import Optional

from utils.db import _conn

logger = logging.getLogger(__name__)


def save_template(name: str, body: str, tid: Optional[int] = None) -> int:
    """テンプレートを保存する

    Args:
        name: テンプレート名
        body: 本文
        tid: 更新時のID

    Returns:
        保存されたテンプレートのID
    """
    conn = _conn()
    now = datetime.now().isoformat()

    if tid:
        conn.execute(
            "UPDATE templates SET name = ?, body = ? WHERE id = ?",
            (name, body, tid),
        )
        result_id = tid
    else:
        cur = conn.execute(
            "INSERT INTO templates (name, body, created_at) VALUES (?, ?, ?)",
            (name, body, now),
        )
        result_id = cur.lastrowid

    conn.commit()
    conn.close()
    logger.info("テンプレート保存: ID=%d, name=%s", result_id, name)
    return result_id


def get_templates() -> list[dict]:
    """全テンプレートを取得する"""
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM templates ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_template(tid: int) -> None:
    """テンプレートを削除する"""
    conn = _conn()
    conn.execute("DELETE FROM templates WHERE id = ?", (tid,))
    conn.commit()
    conn.close()
    logger.info("テンプレート削除: ID=%d", tid)
