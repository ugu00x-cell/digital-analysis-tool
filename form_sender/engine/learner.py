"""自動学習エンジン - 送信結果のDB管理・フォーム構造キャッシュ"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import DB_DIR, DB_PATH

logger = logging.getLogger(__name__)


def init_db() -> None:
    """データベースとテーブルを初期化する"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # 送信結果テーブル
    cur.execute("""
        CREATE TABLE IF NOT EXISTS send_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            url TEXT NOT NULL,
            status TEXT NOT NULL,
            error_detail TEXT DEFAULT '',
            sent_at TEXT NOT NULL
        )
    """)

    # フォーム構造キャッシュテーブル
    cur.execute("""
        CREATE TABLE IF NOT EXISTS form_cache (
            domain TEXT PRIMARY KEY,
            form_url TEXT NOT NULL,
            field_mapping TEXT NOT NULL,
            success_count INTEGER DEFAULT 0,
            fail_count INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    logger.info("データベース初期化完了: %s", DB_PATH)


def save_result(
    company: str, url: str, status: str, error: str = ""
) -> None:
    """送信結果を記録する

    Args:
        company: 企業名
        url: 送信先URL
        status: 送信ステータス（success/captcha/no_form/timeout/error）
        error: エラー詳細
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO send_results (company_name, url, status, error_detail, sent_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (company, url, status, error, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    logger.info("送信結果記録: %s → %s", company, status)


def save_form_cache(
    domain: str, form_url: str, mapping: dict, success: bool
) -> None:
    """フォーム構造をキャッシュに保存・更新する

    Args:
        domain: ドメイン名
        form_url: フォームページのURL
        mapping: フィールドマッピング辞書
        success: 送信成功したかどうか
    """
    conn = sqlite3.connect(str(DB_PATH))
    mapping_json = json.dumps(mapping, ensure_ascii=False)
    now = datetime.now().isoformat()

    # UPSERT（存在すれば更新、なければ挿入）
    conn.execute(
        """INSERT INTO form_cache (domain, form_url, field_mapping, success_count, fail_count, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(domain) DO UPDATE SET
            field_mapping = excluded.field_mapping,
            success_count = success_count + ?,
            fail_count = fail_count + ?,
            updated_at = excluded.updated_at""",
        (domain, form_url, mapping_json,
         1 if success else 0, 0 if success else 1, now,
         1 if success else 0, 0 if success else 1),
    )
    conn.commit()
    conn.close()


def get_form_cache(domain: str) -> Optional[dict]:
    """キャッシュ済みのフォーム構造を取得する

    Args:
        domain: ドメイン名

    Returns:
        キャッシュデータ辞書、未キャッシュならNone
    """
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.execute(
        "SELECT form_url, field_mapping, success_count, fail_count "
        "FROM form_cache WHERE domain = ?",
        (domain,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "form_url": row[0],
        "field_mapping": json.loads(row[1]),
        "success_count": row[2],
        "fail_count": row[3],
    }


def get_stats() -> dict:
    """ダッシュボード用の集計データを取得する

    Returns:
        集計結果の辞書
    """
    conn = sqlite3.connect(str(DB_PATH))

    # 送信結果の集計
    cur = conn.execute(
        "SELECT status, COUNT(*) FROM send_results GROUP BY status"
    )
    status_counts = dict(cur.fetchall())

    # 学習済みサイト数
    cur = conn.execute("SELECT COUNT(*) FROM form_cache")
    cached_sites = cur.fetchone()[0]

    # 今日の送信数
    today = datetime.now().strftime("%Y-%m-%d")
    cur = conn.execute(
        "SELECT COUNT(*) FROM send_results WHERE sent_at LIKE ?",
        (f"{today}%",),
    )
    today_count = cur.fetchone()[0]

    conn.close()

    total = sum(status_counts.values())
    success = status_counts.get("success", 0)

    return {
        "total": total,
        "success": success,
        "success_rate": (success / total * 100) if total > 0 else 0,
        "status_counts": status_counts,
        "cached_sites": cached_sites,
        "today_count": today_count,
    }


def get_all_results() -> list[dict]:
    """全送信結果を取得する（新しい順）

    Returns:
        送信結果のリスト
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT * FROM send_results ORDER BY sent_at DESC"
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
