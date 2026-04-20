"""SQLiteデータベース管理 - プロファイル・テンプレート・ログ・進捗の永続化"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "db" / "form_sender.db"


def _conn() -> sqlite3.Connection:
    """DB接続を取得する（WALモード）"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """全テーブルを初期化する"""
    conn = _conn()
    cur = conn.cursor()

    # 差出人プロファイル
    cur.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            last_name TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            last_kana TEXT DEFAULT '',
            first_kana TEXT DEFAULT '',
            company TEXT DEFAULT '',
            email TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            postal TEXT DEFAULT '',
            address TEXT DEFAULT ''
        )
    """)

    # 送信テンプレート
    cur.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # 送信済みURL（重複防止）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sent_urls (
            url TEXT PRIMARY KEY,
            sent_at TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)

    # 送信ログ（詳細）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS send_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            company_name TEXT NOT NULL,
            status TEXT NOT NULL,
            error_reason TEXT DEFAULT '',
            retry_count INTEGER DEFAULT 0,
            ai_used_flag INTEGER DEFAULT 0,
            sent_at TEXT NOT NULL
        )
    """)

    # 送信進捗（途中再開用）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS send_progress (
            session_id TEXT PRIMARY KEY,
            total INTEGER NOT NULL,
            current_index INTEGER DEFAULT 0,
            status TEXT DEFAULT 'running',
            started_at TEXT NOT NULL
        )
    """)

    # 送信設定
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # フォーム構造キャッシュ（学習用）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS form_cache (
            domain TEXT PRIMARY KEY,
            form_url TEXT NOT NULL,
            field_mapping TEXT NOT NULL,
            success_count INTEGER DEFAULT 0,
            fail_count INTEGER DEFAULT 0,
            last_status TEXT DEFAULT '',
            updated_at TEXT NOT NULL
        )
    """)

    # マイグレーション: form_cacheにhtml_signature列を追加
    _migrate_form_cache(cur)

    conn.commit()
    conn.close()
    logger.info("DB初期化完了: %s", DB_PATH)


def _migrate_form_cache(cur) -> None:
    """form_cacheテーブルのマイグレーションを実行する"""
    # html_signature列の存在チェック
    cur.execute("PRAGMA table_info(form_cache)")
    columns = {row[1] for row in cur.fetchall()}
    if "html_signature" not in columns:
        cur.execute(
            "ALTER TABLE form_cache ADD COLUMN html_signature TEXT DEFAULT ''"
        )
        logger.info("マイグレーション: form_cacheにhtml_signature列を追加")
