"""DB操作 - 送信ログ・送信済みURL・送信設定の管理"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from utils.db import _conn

logger = logging.getLogger(__name__)

MAX_LOG_ROWS = 100000  # ログ最大件数
LOG_RETENTION_DAYS = 365  # ログ保持日数


# === 送信済みURL ===

def is_url_sent(url: str) -> bool:
    """URLが送信済みかチェックする"""
    conn = _conn()
    row = conn.execute(
        "SELECT 1 FROM sent_urls WHERE url = ?", (url,)
    ).fetchone()
    conn.close()
    return row is not None


def mark_url_sent(url: str, status: str) -> None:
    """URLを送信済みとして記録する"""
    conn = _conn()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO sent_urls (url, sent_at, status) "
        "VALUES (?, ?, ?)",
        (url, now, status),
    )
    conn.commit()
    conn.close()


def get_sent_urls() -> set[str]:
    """送信済みURL一覧をsetで返す"""
    conn = _conn()
    rows = conn.execute("SELECT url FROM sent_urls").fetchall()
    conn.close()
    return {r["url"] for r in rows}


# === 送信ログ ===

def save_log(
    url: str, company: str, status: str,
    error: str = "", retry: int = 0, ai_used: bool = False,
) -> None:
    """送信ログを記録する"""
    conn = _conn()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO send_logs "
        "(url, company_name, status, error_reason, retry_count, "
        "ai_used_flag, sent_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (url, company, status, error, retry, int(ai_used), now),
    )
    conn.commit()
    conn.close()


def get_logs(status_filter: Optional[str] = None) -> list[dict]:
    """送信ログを取得する（新しい順）"""
    conn = _conn()
    if status_filter:
        rows = conn.execute(
            "SELECT * FROM send_logs WHERE status = ? "
            "ORDER BY sent_at DESC",
            (status_filter,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM send_logs ORDER BY sent_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_log_stats() -> dict:
    """ログ統計を取得する"""
    conn = _conn()

    total = conn.execute("SELECT COUNT(*) FROM send_logs").fetchone()[0]
    success = conn.execute(
        "SELECT COUNT(*) FROM send_logs WHERE status = 'success'"
    ).fetchone()[0]
    ai_used = conn.execute(
        "SELECT COUNT(*) FROM send_logs WHERE ai_used_flag = 1"
    ).fetchone()[0]
    ai_success = conn.execute(
        "SELECT COUNT(*) FROM send_logs "
        "WHERE ai_used_flag = 1 AND status = 'success'"
    ).fetchone()[0]

    # 今日の送信数
    today = datetime.now().strftime("%Y-%m-%d")
    today_count = conn.execute(
        "SELECT COUNT(*) FROM send_logs WHERE sent_at LIKE ?",
        (f"{today}%",),
    ).fetchone()[0]

    # ステータス別集計
    rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM send_logs GROUP BY status"
    ).fetchall()
    by_status = {r["status"]: r["cnt"] for r in rows}

    conn.close()
    return {
        "total": total,
        "success": success,
        "success_rate": (success / total * 100) if total > 0 else 0,
        "ai_used": ai_used,
        "ai_success": ai_success,
        "ai_rate": (ai_success / ai_used * 100) if ai_used > 0 else 0,
        "today_count": today_count,
        "by_status": by_status,
    }


def cleanup_old_logs() -> int:
    """古いログを削除する（1年超過＋10万件超過）"""
    conn = _conn()
    cutoff = (datetime.now() - timedelta(days=LOG_RETENTION_DAYS)).isoformat()

    # 1年超過分を削除
    cur = conn.execute(
        "DELETE FROM send_logs WHERE sent_at < ?", (cutoff,)
    )
    deleted = cur.rowcount

    # 10万件超過分を削除（古い順）
    count = conn.execute("SELECT COUNT(*) FROM send_logs").fetchone()[0]
    if count > MAX_LOG_ROWS:
        excess = count - MAX_LOG_ROWS
        conn.execute(
            "DELETE FROM send_logs WHERE id IN "
            "(SELECT id FROM send_logs ORDER BY sent_at ASC LIMIT ?)",
            (excess,),
        )
        deleted += excess

    conn.commit()
    conn.close()
    if deleted > 0:
        logger.info("古いログ削除: %d件", deleted)
    return deleted


# === 送信設定 ===

def get_setting(key: str, default: str = "") -> str:
    """設定値を取得する"""
    conn = _conn()
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    ).fetchone()
    conn.close()
    return row["value"] if row else default


def save_setting(key: str, value: str) -> None:
    """設定値を保存する"""
    conn = _conn()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()
    conn.close()


# === 同一ドメイン制限 ===

def is_domain_sent_today(domain: str) -> bool:
    """今日すでにそのドメインに送信済みかチェックする"""
    conn = _conn()
    today = datetime.now().strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT 1 FROM send_logs WHERE url LIKE ? AND sent_at LIKE ? "
        "AND status = 'success' LIMIT 1",
        (f"%{domain}%", f"{today}%"),
    ).fetchone()
    conn.close()
    return row is not None
