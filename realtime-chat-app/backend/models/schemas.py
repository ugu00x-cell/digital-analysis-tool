"""
共通Pydanticスキーマ

REST APIとWebSocketの両方で共有するリクエスト/レスポンス型
"""

from datetime import datetime

from pydantic import BaseModel, Field


class Room(BaseModel):
    """チャットルーム"""

    id: str
    name: str
    created_at: datetime


class RoomCreate(BaseModel):
    """ルーム作成リクエスト"""

    name: str = Field(..., min_length=1, max_length=255)


class Message(BaseModel):
    """チャットメッセージ"""

    id: str
    room_id: str
    user_id: str
    text: str
    timestamp: datetime


class MessageCreate(BaseModel):
    """メッセージ送信リクエスト"""

    user_id: str = Field(..., min_length=1, max_length=50)
    text: str = Field(..., min_length=1)
