"""DB操作 - 差出人プロファイルのCRUD"""

import logging
from typing import Optional

from utils.db import _conn

logger = logging.getLogger(__name__)


def save_profile(data: dict) -> int:
    """プロファイルを保存する（新規 or 更新）

    Args:
        data: プロファイル辞書（idがあれば更新）

    Returns:
        保存されたプロファイルのID
    """
    conn = _conn()
    cols = [
        "name", "last_name", "first_name", "last_kana",
        "first_kana", "company", "email", "phone", "postal", "address",
    ]

    if data.get("id"):
        # 更新
        sets = ", ".join(f"{c} = ?" for c in cols)
        vals = [data.get(c, "") for c in cols] + [data["id"]]
        conn.execute(f"UPDATE profiles SET {sets} WHERE id = ?", vals)
        pid = data["id"]
    else:
        # 新規
        placeholders = ", ".join(["?"] * len(cols))
        vals = [data.get(c, "") for c in cols]
        cur = conn.execute(
            f"INSERT INTO profiles ({', '.join(cols)}) VALUES ({placeholders})",
            vals,
        )
        pid = cur.lastrowid

    conn.commit()
    conn.close()
    logger.info("プロファイル保存: ID=%d", pid)
    return pid


def get_profiles() -> list[dict]:
    """全プロファイルを取得する"""
    conn = _conn()
    rows = conn.execute("SELECT * FROM profiles ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_profile(pid: int) -> Optional[dict]:
    """ID指定でプロファイルを取得する"""
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM profiles WHERE id = ?", (pid,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_profile(pid: int) -> None:
    """プロファイルを削除する"""
    conn = _conn()
    conn.execute("DELETE FROM profiles WHERE id = ?", (pid,))
    conn.commit()
    conn.close()
    logger.info("プロファイル削除: ID=%d", pid)
