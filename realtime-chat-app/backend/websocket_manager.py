"""
WebSocket接続管理モジュール

判定軸: なぜWebSocketか
- チャットはリアルタイム性が必須（HTTPポーリングでは数秒の遅延と無駄なリクエストが発生する）
- 双方向通信により、サーバーからクライアントへの即時プッシュ（ブロードキャスト）が自然に書ける
- 接続を維持する分、通信効率はポーリングより良い（毎回のHTTPヘッダ往復が不要）
"""

import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """ルームごとのWebSocket接続を管理する

    判定軸: 接続管理をルームIDで分離しているのは、
    同時接続数が増えてもブロードキャスト対象を「そのルームの接続」だけに
    絞れるようにするため（将来のスケーラビリティ考慮）
    """

    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = {}

    async def connect(self, room_id: str, websocket: WebSocket) -> None:
        """クライアントを受け入れ、ルームの接続集合に追加する"""
        await websocket.accept()
        self._rooms.setdefault(room_id, set()).add(websocket)
        logger.info(f"WebSocket接続: room={room_id}, count={len(self._rooms[room_id])}")

    def disconnect(self, room_id: str, websocket: WebSocket) -> None:
        """クライアントをルームの接続集合から除去する"""
        connections = self._rooms.get(room_id)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            del self._rooms[room_id]
        logger.info(f"WebSocket切断: room={room_id}")

    async def broadcast(self, room_id: str, payload: dict[str, Any]) -> None:
        """ルーム内の全接続クライアントにJSONを送信する

        送信失敗した接続は切断済みとみなして除去する
        （1クライアントの切断が他クライアントへの配信を止めないようにするため）
        """
        connections = list(self._rooms.get(room_id, set()))
        for ws in connections:
            try:
                await ws.send_json(payload)
            except Exception as e:
                logger.warning(f"送信失敗のため接続を除去: {e}")
                self.disconnect(room_id, ws)
