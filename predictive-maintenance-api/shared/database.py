"""
SQLiteデータベース管理モジュール

振動データと解析結果の永続化を担当する
"""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator

from shared.config import DB_PATH

logger = logging.getLogger(__name__)


def _ensure_dir() -> None:
    """DB格納ディレクトリを作成する"""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """SQLiteコネクションのコンテキストマネージャ

    Yields:
        sqlite3.Connection
    """
    _ensure_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """テーブルを初期化する（存在しなければ作成）"""
    with get_connection() as conn:
        # 振動データテーブル
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vibration_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                x REAL NOT NULL,
                y REAL NOT NULL,
                z REAL NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_vibration_device_time
            ON vibration_data (device_id, timestamp)
        """)

        # 解析結果テーブル
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                is_anomaly INTEGER NOT NULL,
                max_z_score REAL NOT NULL,
                mean_rms REAL NOT NULL,
                peak_frequency_hz REAL NOT NULL,
                envelope_peak_hz REAL NOT NULL,
                threshold REAL NOT NULL,
                sample_count INTEGER NOT NULL,
                analyzed_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_analysis_device
            ON analysis_results (device_id, analyzed_at DESC)
        """)

    logger.info(f"DB初期化完了: {DB_PATH}")


def insert_vibration(
    device_id: str,
    timestamp: datetime,
    x: float,
    y: float,
    z: float,
) -> None:
    """振動データ1件を挿入する"""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO vibration_data (device_id, timestamp, x, y, z) "
            "VALUES (?, ?, ?, ?, ?)",
            (device_id, timestamp.isoformat(), x, y, z),
        )


def insert_vibration_batch(
    records: list[tuple[str, datetime, float, float, float]],
) -> int:
    """振動データを一括挿入する

    Args:
        records: [(device_id, timestamp, x, y, z), ...]

    Returns:
        挿入件数
    """
    with get_connection() as conn:
        conn.executemany(
            "INSERT INTO vibration_data (device_id, timestamp, x, y, z) "
            "VALUES (?, ?, ?, ?, ?)",
            [(r[0], r[1].isoformat(), r[2], r[3], r[4]) for r in records],
        )
    return len(records)


def fetch_vibration(
    device_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict]:
    """振動データを取得する

    Args:
        device_id: デバイスID
        start: 開始時刻（省略時は全期間）
        end: 終了時刻（省略時は全期間）

    Returns:
        振動データのリスト
    """
    query = "SELECT * FROM vibration_data WHERE device_id = ?"
    params: list = [device_id]

    if start:
        query += " AND timestamp >= ?"
        params.append(start.isoformat())
    if end:
        query += " AND timestamp <= ?"
        params.append(end.isoformat())

    query += " ORDER BY timestamp ASC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def save_analysis_result(result: dict) -> None:
    """解析結果を保存する"""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO analysis_results "
            "(device_id, is_anomaly, max_z_score, mean_rms, "
            "peak_frequency_hz, envelope_peak_hz, threshold, "
            "sample_count, analyzed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                result["device_id"],
                int(result["is_anomaly"]),
                result["max_z_score"],
                result["mean_rms"],
                result["peak_frequency_hz"],
                result["envelope_peak_hz"],
                result["threshold"],
                result["sample_count"],
                result["analyzed_at"],
            ),
        )


def get_latest_analysis(device_id: str) -> dict | None:
    """最新の解析結果を取得する"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM analysis_results "
            "WHERE device_id = ? ORDER BY analyzed_at DESC LIMIT 1",
            (device_id,),
        ).fetchone()
    return dict(row) if row else None


def get_device_data_count(device_id: str) -> int:
    """デバイスのデータ件数を取得する"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM vibration_data WHERE device_id = ?",
            (device_id,),
        ).fetchone()
    return row["cnt"]


def get_last_received(device_id: str) -> str | None:
    """デバイスの最終受信時刻を取得する"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT MAX(timestamp) as last_ts FROM vibration_data "
            "WHERE device_id = ?",
            (device_id,),
        ).fetchone()
    return row["last_ts"] if row else None
