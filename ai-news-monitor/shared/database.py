"""
データベース操作モジュール

SQLite を使用した記事情報の永続化。
重複チェック・履歴管理を実装。
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from shared.config import DB_PATH
from shared.logger import setup_logger
from shared.models import NewsItem

logger = setup_logger(__name__)


class Database:
    """SQLite データベース操作クラス"""

    def __init__(self, db_path: str = DB_PATH):
        """
        初期化

        Args:
            db_path: SQLiteデータベースファイルのパス
        """
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self) -> None:
        """データベースとテーブルを初期化"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as conn:
            cursor = conn.cursor()

            # ニュース記事テーブル
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS news_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    url TEXT UNIQUE NOT NULL,
                    published_at TEXT NOT NULL,
                    keywords TEXT,
                    raw_text TEXT NOT NULL,
                    author TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(url),
                    INDEX idx_published_at (published_at),
                    INDEX idx_source (source)
                )
                """
            )

            # 通知履歴テーブル
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    news_item_ids TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    slack_message_ts TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    @contextmanager
    def _connect(self):
        """
        データベース接続をコンテキストマネージャで管理

        Yields:
            sqlite3.Connection
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def insert_news_item(self, item: NewsItem) -> Optional[int]:
        """
        ニュース記事を挿入

        重複チェック済みで、同じURLの記事は重複挿入を防ぐ。

        Args:
            item: NewsItem インスタンス

        Returns:
            挿入されたアイテムID（重複の場合はNone）
        """
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO news_items (
                        title, source, url, published_at, keywords,
                        raw_text, author
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.title,
                        item.source,
                        item.url,
                        item.published_at.isoformat(),
                        json.dumps(item.keywords, ensure_ascii=False),
                        item.raw_text,
                        item.author,
                    ),
                )
                conn.commit()
                item_id = cursor.lastrowid
                logger.debug(f"Inserted news item: {item.title[:50]} (ID: {item_id})")
                return item_id

        except sqlite3.IntegrityError:
            logger.debug(f"Duplicate URL (skipped): {item.url}")
            return None
        except Exception as e:
            logger.error(f"Error inserting news item: {e}")
            return None

    def insert_news_items_batch(self, items: List[NewsItem]) -> tuple[int, int]:
        """
        複数のニュース記事をバッチ挿入

        Args:
            items: NewsItem リスト

        Returns:
            (成功件数, 失敗件数)
        """
        success_count = 0
        error_count = 0

        for item in items:
            result = self.insert_news_item(item)
            if result:
                success_count += 1
            else:
                error_count += 1

        logger.info(f"Batch insert: {success_count} success, {error_count} errors")
        return success_count, error_count

    def get_news_items_since(self, hours: int = 24) -> List[NewsItem]:
        """
        指定時間内のニュース記事を取得

        Args:
            hours: 過去何時間分か（デフォルト24時間）

        Returns:
            NewsItem リスト
        """
        try:
            with self._connect() as conn:
                cursor = conn.cursor()

                # SQLite の datetime 関数でフィルタリング
                cursor.execute(
                    """
                    SELECT *
                    FROM news_items
                    WHERE datetime(published_at) > datetime('now', ?)
                    ORDER BY published_at DESC
                    """,
                    (f"-{hours} hours",),
                )

                rows = cursor.fetchall()
                items = []

                for row in rows:
                    keywords = json.loads(row["keywords"]) if row["keywords"] else []
                    item = NewsItem(
                        title=row["title"],
                        source=row["source"],
                        url=row["url"],
                        published_at=datetime.fromisoformat(row["published_at"]),
                        keywords=keywords,
                        raw_text=row["raw_text"],
                        author=row["author"],
                    )
                    items.append(item)

                logger.debug(f"Retrieved {len(items)} news items from past {hours} hours")
                return items

        except Exception as e:
            logger.error(f"Error retrieving news items: {e}")
            return []

    def get_all_urls(self) -> set[str]:
        """
        データベースに保存されているすべてのURL を取得（重複チェック用）

        Returns:
            URL のセット
        """
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT url FROM news_items")
                rows = cursor.fetchall()
                return {row["url"] for row in rows}

        except Exception as e:
            logger.error(f"Error retrieving URLs: {e}")
            return set()

    def log_notification(self, news_item_ids: List[int], status: str = "sent") -> bool:
        """
        通知履歴をログ記録

        Args:
            news_item_ids: 通知したニュースID のリスト
            status: ステータス（sent / failed）

        Returns:
            成功したかどうか
        """
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO notifications (timestamp, news_item_ids, status)
                    VALUES (?, ?, ?)
                    """,
                    (
                        datetime.now().isoformat(),
                        json.dumps(news_item_ids),
                        status,
                    ),
                )
                conn.commit()
                logger.debug(f"Notification logged: {len(news_item_ids)} items, status={status}")
                return True

        except Exception as e:
            logger.error(f"Error logging notification: {e}")
            return False

    def delete_old_records(self, days: int = 30) -> int:
        """
        指定日数以上前の記事を削除（オプション機能）

        Args:
            days: 何日以上前の記事を削除するか

        Returns:
            削除された行数
        """
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    DELETE FROM news_items
                    WHERE datetime(created_at) < datetime('now', ?)
                    """,
                    (f"-{days} days",),
                )
                conn.commit()
                deleted_count = cursor.rowcount
                logger.info(f"Deleted {deleted_count} old records (older than {days} days)")
                return deleted_count

        except Exception as e:
            logger.error(f"Error deleting old records: {e}")
            return 0


# シングルトンパターン
_db_instance: Optional[Database] = None


def get_database() -> Database:
    """データベースインスタンスを取得（シングルトン）"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
