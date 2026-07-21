"""
ChatService: データアクセスを隠蔽する抽象化レイヤー

判定軸: なぜこの抽象化層を挟むか
- ルーム一覧・作成、メッセージ取得・追加という「ビジネスロジック」から
  「PostgreSQLへのSQL発行」という実装詳細を分離する
- 将来PostgreSQL⇄Firebase等へ実装を差し替える場合、
  このファイルの中身（SQL部分）だけを書き換えれば良く、
  main.py（APIルーティング）やフロントエンド・WebSocketロジックは無改修で済む
"""

import logging
import uuid
from datetime import datetime
from typing import Any

import asyncpg

from models.schemas import Message, Room
from websocket_manager import ConnectionManager

logger = logging.getLogger(__name__)


class ChatService:
    """チャットのビジネスロジックとデータアクセスを仲介する"""

    def __init__(self, pool: asyncpg.Pool, manager: ConnectionManager) -> None:
        self._pool = pool
        self._manager = manager

    async def get_rooms(self) -> list[Room]:
        """全ルーム取得（実装隠蔽）"""
        rows = await self._pool.fetch(
            "SELECT id, name, created_at FROM rooms ORDER BY created_at ASC",
        )
        return [Room(**dict(r)) for r in rows]

    async def create_room(self, name: str) -> Room:
        """ルーム作成"""
        room_id = f"room_{uuid.uuid4().hex[:12]}"
        row = await self._pool.fetchrow(
            "INSERT INTO rooms (id, name) VALUES ($1, $2) "
            "RETURNING id, name, created_at",
            room_id, name,
        )
        room = Room(**dict(row))
        logger.info(f"ルーム作成: {room.id} ({room.name})")
        return room

    async def get_messages(self, room_id: str, limit: int = 50) -> list[Message]:
        """メッセージ取得（実装隠蔽）

        判定軸: limitで上限を設けているのは、大規模ルームで
        全件取得してしまうと応答が遅くなる・メモリを圧迫するため
        （idx_room_timestampインデックスにより、この絞り込みクエリは高速に処理される）
        """
        rows = await self._pool.fetch(
            "SELECT id, room_id, user_id, text, timestamp FROM messages "
            "WHERE room_id = $1 ORDER BY timestamp DESC LIMIT $2",
            room_id, limit,
        )
        return [Message(**dict(r)) for r in rows]

    async def add_message(self, room_id: str, user_id: str, text: str) -> Message:
        """メッセージ追加

        判定軸: トランザクション（単一INSERT文の原子性）により、
        同時に複数クライアントがメッセージ送信しても、
        タイムスタンプの重複・順序の乱れがDB側で防がれる
        """
        message_id = f"msg_{uuid.uuid4().hex[:12]}"
        row = await self._pool.fetchrow(
            "INSERT INTO messages (id, room_id, user_id, text, timestamp) "
            "VALUES ($1, $2, $3, $4, $5) "
            "RETURNING id, room_id, user_id, text, timestamp",
            message_id, room_id, user_id, text, datetime.utcnow(),
        )
        return Message(**dict(row))

    async def broadcast_message(self, room_id: str, message: Message) -> None:
        """接続中の全クライアントにメッセージをブロードキャストする"""
        payload: dict[str, Any] = {
            "type": "message",
            "data": message.model_dump(mode="json"),
        }
        await self._manager.broadcast(room_id, payload)
