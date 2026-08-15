"""
データモデル定義

Pydantic を使用した型安全なデータモデルを定義する。
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    """ニュース記事のデータモデル"""

    title: str = Field(..., description="ニュースタイトル")
    source: str = Field(..., description="情報ソース（twitter / rss）")
    url: str = Field(..., description="記事URL")
    published_at: datetime = Field(..., description="公開日時")
    keywords: List[str] = Field(default_factory=list, description="マッチしたキーワード一覧")
    raw_text: str = Field(..., description="元テキスト（ツイート本文またはrss description）")
    author: Optional[str] = Field(None, description="著者またはアカウント名")

    class Config:
        """Pydantic設定"""

        json_encoders = {datetime: lambda v: v.isoformat()}


class NotificationPayload(BaseModel):
    """Slack通知のペイロード"""

    channel: str = Field(..., description="通知先チャンネル（Slack Webhook URL）")
    items: List[NewsItem] = Field(..., description="通知する記事一覧")
    timestamp: datetime = Field(default_factory=datetime.now, description="通知タイムスタンプ")
    summary: Optional[str] = Field(None, description="要約テキスト（オプション）")

    class Config:
        """Pydantic設定"""

        json_encoders = {datetime: lambda v: v.isoformat()}


class CollectorResult(BaseModel):
    """情報収集結果"""

    success_count: int = Field(default=0, description="収集成功件数")
    error_count: int = Field(default=0, description="エラー件数")
    items: List[NewsItem] = Field(default_factory=list, description="収集したニュース")
    errors: List[str] = Field(default_factory=list, description="エラーメッセージ一覧")
    timestamp: datetime = Field(default_factory=datetime.now, description="実行タイムスタンプ")

    class Config:
        """Pydantic設定"""

        json_encoders = {datetime: lambda v: v.isoformat()}
