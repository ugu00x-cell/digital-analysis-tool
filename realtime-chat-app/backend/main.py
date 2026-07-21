"""
リアルタイムチャットAPI エントリポイント

REST API（ルーム/メッセージ）とWebSocket（リアルタイム配信）を提供する。
ビジネスロジック・データアクセスはChatServiceに委譲し、
このファイルはルーティングとWebSocketの接続ライフサイクル管理のみを担う。
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from database import close_pool, get_pool, init_pool
from models.schemas import Message, MessageCreate, Room, RoomCreate
from services.chat_service import ChatService
from websocket_manager import ConnectionManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

manager = ConnectionManager()
chat_service: ChatService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """起動時にDBプールを初期化し、終了時にgraceful shutdownする"""
    global chat_service
    await init_pool()
    chat_service = ChatService(get_pool(), manager)
    logger.info("リアルタイムチャットAPI 起動完了")
    yield
    await close_pool()


app = FastAPI(
    title="リアルタイムチャットAPI",
    description="Next.jsフロントエンド向けのチャットルーム・メッセージ・WebSocket API",
    version="1.0.0",
    lifespan=lifespan,
)

# Next.js開発サーバー(localhost:3000)からのアクセスを許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _service() -> ChatService:
    """初期化済みのChatServiceを取得する"""
    if chat_service is None:
        raise HTTPException(status_code=503, detail="サービス初期化中です")
    return chat_service


@app.get("/api/rooms", response_model=list[Room], summary="チャットルーム一覧取得")
async def list_rooms() -> list[Room]:
    """全チャットルームを取得する"""
    return await _service().get_rooms()


@app.post("/api/rooms", response_model=Room, summary="チャットルーム作成")
async def create_room(body: RoomCreate) -> Room:
    """新しいチャットルームを作成する"""
    return await _service().create_room(body.name)


@app.get(
    "/api/rooms/{room_id}/messages",
    response_model=list[Message],
    summary="ルームの過去メッセージ取得",
)
async def get_messages(room_id: str) -> list[Message]:
    """指定ルームの直近50件のメッセージを取得する（新しい順）

    判定軸: 無効なルームIDへのアクセスは、
    メッセージ0件の正常系として扱う（チャット履歴の取得自体は失敗ではないため）
    """
    return await _service().get_messages(room_id, limit=50)


@app.post(
    "/api/rooms/{room_id}/messages",
    response_model=Message,
    summary="メッセージ送信（REST）",
)
async def post_message(room_id: str, body: MessageCreate) -> Message:
    """メッセージを送信し、DB保存後にWebSocket接続中の全クライアントへ配信する"""
    service = _service()
    message = await service.add_message(room_id, body.user_id, body.text)
    await service.broadcast_message(room_id, message)
    return message


@app.websocket("/ws/rooms/{room_id}")
async def room_websocket(
    websocket: WebSocket, room_id: str, user_id: str = Query(...),
) -> None:
    """ルームのリアルタイム接続

    - 接続時: 他クライアントへ入室を通知
    - メッセージ受信時: DB保存後、全クライアントへブロードキャスト
    - 切断時: 他クライアントへ退室を通知
    """
    service = _service()
    await manager.connect(room_id, websocket)
    await manager.broadcast(room_id, {"type": "user_joined", "user_id": user_id})

    try:
        while True:
            data = await websocket.receive_json()
            text = str(data.get("text", "")).strip()
            if not text:
                continue
            message = await service.add_message(room_id, user_id, text)
            await service.broadcast_message(room_id, message)
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)
        await manager.broadcast(room_id, {"type": "user_left", "user_id": user_id})


@app.get("/health", summary="ヘルスチェック")
async def health() -> dict:
    """サービスの稼働状態を返す"""
    return {"status": "ok", "service": "realtime-chat-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
